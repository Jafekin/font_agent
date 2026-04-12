"""GraphRAG 图谱构建器：从 rag/data/ 加载 PageData，写入 Neo4j 知识图谱。

数据流:
  NaiveDataLoader → PageData → Document / Edition / Collection / Page / Layout / Entity
"""

from __future__ import annotations

import hashlib
import json
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
# LLM 实体抽取
# ---------------------------------------------------------------------------
_ENTITY_EXTRACTION_PROMPT = """\
你是一位古籍文献分析助手。请从以下古籍文本中抽取命名实体，仅输出 JSON，不要输出任何其他内容。

输出格式（严格遵守）：
{{"entities": [{{"text": "实体文字", "type": "PERSON|PLACE|WORK|DYNASTY"}}, ...]}}

实体类型说明：
- PERSON：人名（作者、注释者、历史人物等）
- PLACE：地名（地点、政区、山川等）
- WORK：书名或篇名
- DYNASTY：朝代或时期

文本：
{text}
"""


def _extract_entities_with_llm(
    text: str, page_id: str, page_dir: Optional[Path] = None
) -> List[Tuple[str, str]]:
    """调用 LLM 从文本中提取命名实体，返回 (文字, 类型) 列表。

    如果 page_dir 下已有 entities.json 缓存，直接读取缓存，不调用 LLM。
    提取完成后将结果写入 page_dir/entities.json 供后续复用。
    """
    from rag.naive.pipeline import get_openai_client

    # ---- 读缓存 ----
    cache_path = page_dir / "entities.json" if page_dir else None
    if cache_path and cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            result = [(item["text"], item["type"]) for item in cached]
            logger.debug("页面 %s 使用实体缓存（%d 条）", page_id, len(result))
            return result
        except Exception as exc:
            logger.warning("页面 %s 读取实体缓存失败，重新提取: %s", page_id, exc)

    if not text or not text.strip():
        return []

    # 截断过长文本，避免超出 token 限制
    truncated = text[:3000]
    prompt = _ENTITY_EXTRACTION_PROMPT.format(text=truncated)

    try:
        client = get_openai_client()
        resp = client.chat.completions.create(
            model="ernie-4.5-turbo-vl",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1024,
        )
        raw = resp.choices[0].message.content or ""
        # 只保留 JSON 部分（模型有时会在前后加说明文字）
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("页面 %s 实体抽取：LLM 返回非 JSON 内容", page_id)
            return []
        json_str = raw[start:end]
        result = []
        try:
            data = json.loads(json_str)
            items = data.get("entities", [])
        except json.JSONDecodeError:
            # LLM 返回格式不合规（缺逗号、非法转义等），用正则逐条提取
            logger.debug("页面 %s JSON 解析失败，回退到正则提取", page_id)
            _ENTITY_RE = re.compile(
                r'"text"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"\s*,\s*"type"\s*:\s*"([^"]+)"'
                r'|"type"\s*:\s*"([^"]+)"\s*,\s*"text"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
            )
            items = []
            for m in _ENTITY_RE.finditer(json_str):
                if m.group(1):
                    items.append({"text": m.group(1), "type": m.group(2)})
                else:
                    items.append({"text": m.group(4), "type": m.group(3)})
        for item in items:
            t = str(item.get("text", "")).strip()
            etype = str(item.get("type", "")).strip().upper()
            if t and etype in {"PERSON", "PLACE", "WORK", "DYNASTY"}:
                result.append((t, etype))

        # ---- 写缓存 ----
        if cache_path:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(
                        [{"text": t, "type": e} for t, e in result],
                        f, ensure_ascii=False, indent=2,
                    )
            except Exception as exc:
                logger.warning("页面 %s 写入实体缓存失败: %s", page_id, exc)

        return result
    except Exception as exc:
        logger.warning("页面 %s 实体抽取失败: %s", page_id, exc)
        return []


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
            coll_id = hashlib.md5(
                e.holding_institution.encode()).hexdigest()[:10]
            if coll_id not in created_collections:
                catalog_main = e.catalog_id_main or None
                coll = Collection(
                    collection_id=coll_id,
                    institution=e.holding_institution,
                    call_number=catalog_main,
                )
                self.client.merge_node(
                    "Collection", "collection_id", coll.to_dict())
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
        has_annotation = len(page.ocr_lines) > line_count * \
            1.5 if line_count else False
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
            for entity_text, entity_type in _extract_entities_with_llm(
                page.full_text, page.page_id, page.page_dir
            ):
                eid = _entity_id(entity_text, entity_type)
                if eid not in created_entities:
                    ent = Entity(
                        entity_id=eid,
                        entity_text=entity_text,
                        entity_type=entity_type,
                    )
                    self.client.merge_node(
                        "Entity", "entity_id", ent.to_dict())
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
