"""图谱构建器 - 从 metadata.json 构建知识图谱."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Collection, Document, Edition, Layout, Page, Volume
from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphBuilder:
    """知识图谱构建器."""

    def __init__(self, neo4j_client: Neo4jClient):
        """初始化构建器.

        Args:
            neo4j_client: Neo4j 客户端实例
        """
        self.client = neo4j_client

    def build_from_metadata(
        self,
        metadata_path: Path,
        embeddings_path: Optional[Path] = None,
    ) -> Dict[str, int]:
        """从 metadata.json 构建图谱.

        Args:
            metadata_path: metadata.json 文件路径
            embeddings_path: embeddings.npy 文件路径（可选）

        Returns:
            构建统计信息
        """
        logger.info(f"开始从 {metadata_path} 构建图谱")

        # 加载 metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata_list = json.load(f)

        logger.info(f"加载了 {len(metadata_list)} 条元数据")

        stats = {
            "documents": 0,
            "volumes": 0,
            "pages": 0,
            "layouts": 0,
            "editions": 0,
            "collections": 0,
            "relationships": 0,
        }

        # 用于去重和缓存
        created_docs = set()
        created_volumes = set()
        created_layouts = {}  # layout_signature -> layout_id
        created_editions = set()
        created_collections = set()

        # 遍历每条元数据
        for idx, item in enumerate(metadata_list, 1):
            if idx % 10 == 0:
                logger.info(f"处理进度: {idx}/{len(metadata_list)}")

            try:
                # 提取基本信息
                doc_id = self._extract_doc_id(item)
                volume_id = self._extract_volume_id(item)
                page_id = item.get("id", f"page_{idx}")

                # 1. 创建 Document
                if doc_id and doc_id not in created_docs:
                    doc = self._create_document_from_metadata(item, doc_id)
                    self.client.create_document(doc.to_dict())
                    created_docs.add(doc_id)
                    stats["documents"] += 1

                # 2. 创建 Volume
                if volume_id and volume_id not in created_volumes:
                    volume = self._create_volume_from_metadata(item, volume_id)
                    self.client.create_volume(volume.to_dict())
                    created_volumes.add(volume_id)
                    stats["volumes"] += 1

                    # 创建 Document-Volume 关系
                    if doc_id:
                        self.client.create_has_volume_relation(
                            doc_id,
                            volume_id,
                            sequence=self._extract_volume_number(item),
                        )
                        stats["relationships"] += 1

                # 3. 创建 Page
                page = self._create_page_from_metadata(item, page_id)
                self.client.create_page(page.to_dict())
                stats["pages"] += 1

                # 创建 Volume-Page 关系
                if volume_id:
                    self.client.create_has_page_relation(
                        volume_id,
                        page_id,
                        sequence=page.page_number,
                    )
                    stats["relationships"] += 1

                # 4. 创建 Layout（如果有版式信息）
                layout_info = self._extract_layout_info(item)
                if layout_info:
                    layout_sig = self._get_layout_signature(layout_info)
                    if layout_sig not in created_layouts:
                        layout_id = f"layout_{hashlib.md5(layout_sig.encode()).hexdigest()[:8]}"
                        layout = Layout(layout_id=layout_id, **layout_info)
                        self.client.create_layout(layout.to_dict())
                        created_layouts[layout_sig] = layout_id
                        stats["layouts"] += 1
                    else:
                        layout_id = created_layouts[layout_sig]

                    # 创建 Page-Layout 关系
                    self.client.create_has_layout_relation(page_id, layout_id)
                    stats["relationships"] += 1

                # 5. 创建 Edition（如果有版本信息）
                edition_info = self._extract_edition_info(item)
                if edition_info:
                    edition_id = edition_info.get("edition_id")
                    if edition_id and edition_id not in created_editions:
                        edition = Edition(**edition_info)
                        self.client.create_edition(edition.to_dict())
                        created_editions.add(edition_id)
                        stats["editions"] += 1

                    # 创建 Page-Edition 关系
                    if edition_id:
                        self.client.create_belongs_to_edition_relation(
                            page_id,
                            edition_id,
                            confidence=0.9,
                            identified_by="auto",
                        )
                        stats["relationships"] += 1

                # 6. 创建 Collection（如果有馆藏信息）
                collection_info = self._extract_collection_info(item)
                if collection_info:
                    collection_id = collection_info.get("collection_id")
                    if collection_id and collection_id not in created_collections:
                        collection = Collection(**collection_info)
                        self.client.create_collection(collection.to_dict())
                        created_collections.add(collection_id)
                        stats["collections"] += 1

                    # 创建 Document-Collection 关系
                    if doc_id and collection_id:
                        self.client.create_stored_in_relation(
                            doc_id,
                            collection_id,
                            completeness="完整",
                        )
                        stats["relationships"] += 1

            except Exception as e:
                logger.error(f"处理第 {idx} 条元数据时出错: {e}")
                continue

        logger.info(f"图谱构建完成: {stats}")
        return stats

    def build_similarity_relations(
        self,
        embeddings_path: Path,
        ids_path: Path,
        top_k: int = 10,
        threshold: float = 0.8,
    ) -> int:
        """构建页面相似关系.

        Args:
            embeddings_path: embeddings.npy 文件路径
            ids_path: ids.json 文件路径
            top_k: 每个页面保留的最相似页面数
            threshold: 相似度阈值

        Returns:
            创建的关系数量
        """
        import numpy as np

        logger.info("开始构建相似关系")

        # 加载嵌入向量和 ID
        embeddings = np.load(embeddings_path)
        with open(ids_path, "r", encoding="utf-8") as f:
            ids = json.load(f)

        logger.info(f"加载了 {len(embeddings)} 个嵌入向量")

        # 计算相似度矩阵（分批处理避免内存溢出）
        batch_size = 100
        relation_count = 0

        for i in range(0, len(embeddings), batch_size):
            batch_end = min(i + batch_size, len(embeddings))
            batch_embeddings = embeddings[i:batch_end]

            # 计算当前批次与所有向量的相似度
            similarities = np.dot(batch_embeddings, embeddings.T)

            # 对每个向量找出 Top-K 相似
            for j, sim_scores in enumerate(similarities):
                page_idx = i + j
                page_id = ids[page_idx]

                # 获取 Top-K（排除自己）
                top_indices = np.argsort(sim_scores)[::-1][1: top_k + 1]

                for similar_idx in top_indices:
                    similarity_score = float(sim_scores[similar_idx])

                    if similarity_score >= threshold:
                        similar_page_id = ids[similar_idx]

                        try:
                            self.client.create_similar_to_relation(
                                page_id,
                                similar_page_id,
                                similarity_score,
                                similarity_type="visual",
                            )
                            relation_count += 1
                        except Exception as e:
                            logger.warning(f"创建相似关系失败: {e}")

            if (i // batch_size + 1) % 10 == 0:
                logger.info(f"已处理 {batch_end}/{len(embeddings)} 个向量")

        logger.info(f"创建了 {relation_count} 个相似关系")
        return relation_count

    # ==================== 辅助方法 ====================

    def _extract_doc_id(self, item: Dict[str, Any]) -> Optional[str]:
        """从元数据提取文献 ID."""
        # 尝试从不同字段提取
        if "document_id" in item:
            return item["document_id"]
        if "doc_id" in item:
            return item["doc_id"]

        # 从文件路径推断
        image_path = item.get("image_path", "")
        if image_path:
            parts = Path(image_path).parts
            if len(parts) >= 2:
                return f"doc_{parts[-2]}"

        return None

    def _extract_volume_id(self, item: Dict[str, Any]) -> Optional[str]:
        """从元数据提取卷次 ID."""
        if "volume_id" in item:
            return item["volume_id"]

        # 从文件路径推断
        image_path = item.get("image_path", "")
        if image_path:
            parts = Path(image_path).parts
            if len(parts) >= 2:
                return f"vol_{parts[-2]}_{self._extract_volume_number(item):03d}"

        return None

    def _extract_volume_number(self, item: Dict[str, Any]) -> int:
        """从元数据提取卷号."""
        if "volume_number" in item:
            return item["volume_number"]

        # 从文件名推断（假设格式为 vol1_p1.jpg）
        image_path = item.get("image_path", "")
        if image_path:
            filename = Path(image_path).stem
            if "vol" in filename.lower():
                try:
                    vol_part = filename.lower().split("vol")[1].split("_")[0]
                    return int(vol_part)
                except (IndexError, ValueError):
                    pass

        return 1

    def _create_document_from_metadata(
        self,
        item: Dict[str, Any],
        doc_id: str,
    ) -> Document:
        """从元数据创建 Document 对象."""
        return Document(
            doc_id=doc_id,
            title=item.get("title", "未知文献"),
            author=item.get("author"),
            dynasty=item.get("dynasty"),
            category=item.get("category"),
            description=item.get("description"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def _create_volume_from_metadata(
        self,
        item: Dict[str, Any],
        volume_id: str,
    ) -> Volume:
        """从元数据创建 Volume 对象."""
        return Volume(
            volume_id=volume_id,
            volume_number=self._extract_volume_number(item),
            volume_title=item.get("volume_title"),
            page_count=item.get("page_count"),
            description=item.get("volume_description"),
        )

    def _create_page_from_metadata(
        self,
        item: Dict[str, Any],
        page_id: str,
    ) -> Page:
        """从元数据创建 Page 对象."""
        image_path = item.get("image_path", "")

        # 计算图片哈希
        image_hash = None
        if image_path and Path(image_path).exists():
            try:
                with open(image_path, "rb") as f:
                    image_hash = hashlib.md5(f.read()).hexdigest()
            except Exception:
                pass

        return Page(
            page_id=page_id,
            page_number=item.get("page_number", 1),
            image_path=image_path,
            image_hash=image_hash,
            ocr_text=item.get("ocr_text"),
            ocr_confidence=item.get("ocr_confidence"),
            text_direction=item.get("text_direction", "vertical"),
            width=item.get("width"),
            height=item.get("height"),
            created_at=datetime.now(),
        )

    def _extract_layout_info(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从元数据提取版式信息."""
        layout_fields = [
            "column_count",
            "line_count",
            "chars_per_line",
            "border_type",
            "border_color",
            "has_fish_tail",
            "has_annotation",
            "annotation_position",
        ]

        layout_info = {}
        for field in layout_fields:
            if field in item:
                layout_info[field] = item[field]

        return layout_info if layout_info else None

    def _get_layout_signature(self, layout_info: Dict[str, Any]) -> str:
        """生成版式签名（用于去重）."""
        sig_parts = [
            str(layout_info.get("column_count", "")),
            str(layout_info.get("line_count", "")),
            str(layout_info.get("border_type", "")),
            str(layout_info.get("border_color", "")),
        ]
        return "_".join(sig_parts)

    def _extract_edition_info(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从元数据提取版本信息."""
        if "edition_id" not in item and "edition_type" not in item:
            return None

        return {
            "edition_id": item.get("edition_id", f"ed_{item.get('edition_type', 'unknown')}"),
            "edition_type": item.get("edition_type", "未知"),
            "edition_name": item.get("edition_name"),
            "publisher": item.get("publisher"),
            "publish_year": item.get("publish_year"),
            "publish_place": item.get("publish_place"),
            "description": item.get("edition_description"),
        }

    def _extract_collection_info(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从元数据提取馆藏信息."""
        if "institution" not in item and "collection_id" not in item:
            return None

        institution = item.get("institution", "未知机构")
        collection_id = item.get(
            "collection_id",
            f"coll_{hashlib.md5(institution.encode()).hexdigest()[:8]}",
        )

        return {
            "collection_id": collection_id,
            "institution": institution,
            "call_number": item.get("call_number"),
            "location": item.get("location"),
            "acquisition_date": item.get("acquisition_date"),
            "condition": item.get("condition"),
            "notes": item.get("collection_notes"),
        }
