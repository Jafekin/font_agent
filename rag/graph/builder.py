"""GraphRAG 图谱构建器：从 rag/data/ 加载 PageData，写入 Neo4j 知识图谱。

数据流:
  NaiveDataLoader → PageData → Document / Edition / Collection / Page / Layout / Entity
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from rag.naive.data_loader import NaiveDataLoader, PageData

from .client import Neo4jClient
from .models import Collection, Document, Edition, Entity, Layout, Page

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 简单正则实体抽取（人名用"·"分隔的汉字串；地名匹配常见地名词缀）
# ---------------------------------------------------------------------------
_PERSON_PATTERN = re.compile(
    r"(?:司马迁|班固|刘向|左丘明|孔子|孟子|荀子|韩非|庄子|[A-Z\u4e00-\u9fa5]{2,4}(?:撰|著|编|注|疏|校))"
)
_PLACE_PATTERN = re.compile(
    r"[京都郡县州府国]{0,1}[\u4e00-\u9fa5]{1,3}(?:京|都|郡|县|州|府|国|城|关|山|水|湖|江|河|海)"
)


def _extract_entities(text: str) -> List[Tuple[str, str]]:
    """从 OCR 文本中提取 (文字, 类型) 对，类型为 PERSON 或 PLACE。"""
    entities: List[Tuple[str, str]] = []
    for m in _PERSON_PATTERN.finditer(text):
        name = m.group().rstrip("撰著编注疏校")
        if len(name) >= 2:
            entities.append((name, "PERSON"))
    for m in _PLACE_PATTERN.finditer(text):
        entities.append((m.group(), "PLACE"))
    return entities


def _entity_id(text: str, etype: str) -> str:
    return hashlib.md5(f"{etype}:{text}".encode()).hexdigest()[:12]


def _layout_id(line_count: int, has_annotation: bool) -> str:
    return f"layout_{line_count}_{int(has_annotation)}"


# ---------------------------------------------------------------------------
# 主构建器
# ---------------------------------------------------------------------------
class GraphBuilder:
    """从 NaiveDataLoader 加载数据并写入 Neo4j 知识图谱。"""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------
    def build(
        self,
        data_dir: str | Path,
        *,
        extract_entities: bool = True,
        embeddings_path: Optional[str | Path] = None,
        ids_path: Optional[str | Path] = None,
        similarity_threshold: float = 0.88,
        similarity_top_k: int = 10,
    ) -> Dict[str, int]:
        """完整构建流程。

        Args:
            data_dir: rag/data/ 目录路径
            extract_entities: 是否从 OCR 文本提取命名实体
            embeddings_path: embeddings.npy 路径（用于构建 SIMILAR_TO 关系）
            ids_path: ids.json 路径
            similarity_threshold: 相似度阈值
            similarity_top_k: 每页保留的相似关系数量

        Returns:
            各类型节点/关系计数字典
        """
        loader = NaiveDataLoader(data_dir)
        pages = loader.scan_pages()
        logger.info("加载 %d 页，开始构建图谱…", len(pages))

        stats: Dict[str, int] = {
            "documents": 0, "editions": 0, "collections": 0,
            "pages": 0, "layouts": 0, "entities": 0,
            "similar_relations": 0,
        }

        created_docs: Set[str] = set()
        created_editions: Set[str] = set()
        created_collections: Set[str] = set()
        created_layouts: Set[str] = set()
        created_entities: Set[str] = set()

        for i, page in enumerate(pages, 1):
            if i % 50 == 0:
                logger.info("进度 %d/%d", i, len(pages))
            try:
                self._ingest_page(
                    page,
                    created_docs, created_editions, created_collections,
                    created_layouts, created_entities,
                    extract_entities, stats,
                )
            except Exception as exc:
                logger.warning("跳过页面 %s: %s", page.page_id, exc)

        if embeddings_path and ids_path:
            stats["similar_relations"] = self._build_similarity(
                Path(embeddings_path), Path(ids_path),
                similarity_threshold, similarity_top_k,
            )

        logger.info("图谱构建完成: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # 单页写入
    # ------------------------------------------------------------------
    def _ingest_page(
        self,
        page: PageData,
        created_docs: Set[str],
        created_editions: Set[str],
        created_collections: Set[str],
        created_layouts: Set[str],
        created_entities: Set[str],
        extract_entities: bool,
        stats: Dict[str, int],
    ) -> None:
        e = page.edition

        # ---- Document ----
        doc_id = f"doc_{e.edition_dir or 'unknown'}"
        if doc_id not in created_docs:
            doc = Document(
                doc_id=doc_id,
                title=e.edition_dir or "未知文献",
                dynasty=e.printing_info.dynasty_period,
                authors=list(e.authors),
                annotators=list(e.annotators),
                total_juan=e.total_juan,
            )
            self.client.merge_node("Document", "doc_id", doc.to_dict())
            created_docs.add(doc_id)
            stats["documents"] += 1

        # ---- Edition ----
        edition_id = f"edition_{e.version_type or 'unknown'}_{e.edition_dir or 'x'}"
        if edition_id not in created_editions:
            catalog = (
                f"{e.catalog_id_secondary}{e.catalog_id_main}"
                if e.catalog_id_secondary else e.catalog_id_main
            ) or None
            edition = Edition(
                edition_id=edition_id,
                version_type=e.version_type or "",
                annotation_system=e.annotation_system,
                dynasty=e.printing_info.dynasty_period,
                printer=e.printing_info.printer,
                extant_juan=e.extant_juan,
                catalog_id=catalog,
            )
            self.client.merge_node("Edition", "edition_id", edition.to_dict())
            # Document -[:HAS_EDITION]-> Edition
            self.client.merge_relation(
                "Document", "doc_id", doc_id,
                "HAS_EDITION",
                "Edition", "edition_id", edition_id,
            )
            created_editions.add(edition_id)
            stats["editions"] += 1

        # ---- Collection ----
        if e.holding_institution:
            coll_id = hashlib.md5(e.holding_institution.encode()).hexdigest()[:10]
            if coll_id not in created_collections:
                catalog_main = e.catalog_id_main or None
                coll = Collection(
                    collection_id=coll_id,
                    institution=e.holding_institution,
                    call_number=catalog_main,
                )
                self.client.merge_node("Collection", "collection_id", coll.to_dict())
                self.client.merge_relation(
                    "Document", "doc_id", doc_id,
                    "STORED_IN",
                    "Collection", "collection_id", coll_id,
                )
                created_collections.add(coll_id)
                stats["collections"] += 1

        # ---- Page ----
        image_path = str(page.overlay_image or page.source_image or "")
        pg = Page(
            page_id=page.page_id,
            image_path=image_path,
            ocr_text=page.full_text[:2000] if page.full_text else None,
            ocr_confidence=page.ocr_stats.average_confidence or None,
            is_vertical=page.ocr_stats.is_vertical,
            width=page.ocr_stats.image_width or None,
            height=page.ocr_stats.image_height or None,
        )
        self.client.merge_node("Page", "page_id", pg.to_dict())
        # Edition -[:HAS_PAGE]-> Page
        self.client.merge_relation(
            "Edition", "edition_id", edition_id,
            "HAS_PAGE",
            "Page", "page_id", page.page_id,
        )
        stats["pages"] += 1

        # ---- Layout ----
        line_count = page.ocr_stats.line_count
        has_annotation = len(page.ocr_lines) > line_count * 1.5 if line_count else False
        lid = _layout_id(line_count, has_annotation)
        if lid not in created_layouts:
            layout = Layout(
                layout_id=lid,
                line_count=line_count or None,
                has_annotation=has_annotation,
            )
            self.client.merge_node("Layout", "layout_id", layout.to_dict())
            created_layouts.add(lid)
            stats["layouts"] += 1
        self.client.merge_relation(
            "Page", "page_id", page.page_id,
            "HAS_LAYOUT",
            "Layout", "layout_id", lid,
        )

        # ---- Entities ----
        if extract_entities and page.full_text:
            for entity_text, entity_type in _extract_entities(page.full_text):
                eid = _entity_id(entity_text, entity_type)
                if eid not in created_entities:
                    ent = Entity(
                        entity_id=eid,
                        entity_text=entity_text,
                        entity_type=entity_type,
                    )
                    self.client.merge_node("Entity", "entity_id", ent.to_dict())
                    created_entities.add(eid)
                    stats["entities"] += 1
                self.client.merge_relation(
                    "Page", "page_id", page.page_id,
                    "MENTIONS",
                    "Entity", "entity_id", eid,
                )

    # ------------------------------------------------------------------
    # 相似关系构建
    # ------------------------------------------------------------------
    def _build_similarity(
        self,
        embeddings_path: Path,
        ids_path: Path,
        threshold: float,
        top_k: int,
    ) -> int:
        """从 embeddings.npy / ids.json 构建 SIMILAR_TO 关系。"""
        import json
        if not embeddings_path.exists() or not ids_path.exists():
            logger.warning("embeddings 或 ids 文件不存在，跳过相似关系构建。")
            return 0

        emb = np.load(embeddings_path).astype("float32")
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0] = 1
        emb = emb / norms

        with open(ids_path, "r", encoding="utf-8") as f:
            ids: List[str] = json.load(f)

        if len(ids) != len(emb):
            logger.error("ids 与 embeddings 数量不匹配，跳过。")
            return 0

        n = len(ids)
        total = 0
        batch = 100
        for start in range(0, n, batch):
            end = min(start + batch, n)
            scores = emb[start:end] @ emb.T  # (batch, n)
            for local_i, global_i in enumerate(range(start, end)):
                row = scores[local_i]
                row[global_i] = -1  # 排除自身
                best = np.argsort(row)[::-1][:top_k]
                for j in best:
                    s = float(row[j])
                    if s < threshold:
                        break
                    self.client.merge_relation(
                        "Page", "page_id", ids[global_i],
                        "SIMILAR_TO",
                        "Page", "page_id", ids[j],
                        rel_props={"score": round(s, 4)},
                    )
                    total += 1
            logger.debug("相似关系进度 %d/%d", end, n)

        logger.info("构建 SIMILAR_TO 关系 %d 条。", total)
        return total
