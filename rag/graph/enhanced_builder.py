"""增强的图谱构建器 - 支持从 outputs/ 目录构建知识图谱."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .data_loader import OutputsDataLoader
from .models import Collection, Document, Edition, Entity, Layout, Page, Seal, Volume
from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class EnhancedGraphBuilder:
    """增强的知识图谱构建器，支持从 outputs/ 目录构建."""

    def __init__(self, neo4j_client: Neo4jClient):
        """初始化构建器.

        Args:
            neo4j_client: Neo4j 客户端实例
        """
        self.client = neo4j_client

    def build_from_outputs(
        self,
        outputs_dir: Path,
        extract_entities: bool = True,
    ) -> Dict[str, int]:
        """从 outputs/ 目录构建图谱.

        Args:
            outputs_dir: outputs 目录路径
            extract_entities: 是否提取实体

        Returns:
            构建统计信息
        """
        logger.info(f"开始从 {outputs_dir} 构建图谱")

        # 加载数据
        loader = OutputsDataLoader(outputs_dir)
        pages_data = loader.load_all_pages()

        logger.info(f"加载了 {len(pages_data)} 个页面")

        stats = {
            "documents": 0,
            "volumes": 0,
            "pages": 0,
            "layouts": 0,
            "editions": 0,
            "collections": 0,
            "entities": 0,
            "relationships": 0,
        }

        # 用于去重和缓存
        created_docs = set()
        created_volumes = set()
        created_layouts = {}
        created_editions = set()
        created_collections = set()
        created_entities = {}

        # 遍历每个页面
        for idx, page_data in enumerate(pages_data, 1):
            if idx % 10 == 0:
                logger.info(f"处理进度: {idx}/{len(pages_data)}")

            try:
                page_id = page_data["page_id"]

                # 1. 创建 Document
                doc_id = self._get_or_create_document(
                    page_data, created_docs, stats
                )

                # 2. 创建 Volume
                volume_id = self._get_or_create_volume(
                    page_data, doc_id, created_volumes, stats
                )

                # 3. 创建 Page
                self._create_page(page_data, stats)

                # 创建 Volume-Page 关系
                if volume_id:
                    self.client.create_has_page_relation(
                        volume_id,
                        page_id,
                        sequence=page_data.get("page_number", 1),
                    )
                    stats["relationships"] += 1

                # 4. 创建 Layout（从 OCR 统计信息推断）
                layout_id = self._get_or_create_layout(
                    page_data, created_layouts, stats
                )
                if layout_id:
                    self.client.create_has_layout_relation(page_id, layout_id)
                    stats["relationships"] += 1

                # 5. 创建 Edition
                edition_id = self._get_or_create_edition(
                    page_data, created_editions, stats
                )
                if edition_id:
                    self.client.create_belongs_to_edition_relation(
                        page_id,
                        edition_id,
                        confidence=0.95,
                        identified_by="auto_from_outputs",
                    )
                    stats["relationships"] += 1

                # 6. 创建 Collection
                collection_id = self._get_or_create_collection(
                    page_data, doc_id, created_collections, stats
                )

                # 7. 提取并创建实体
                if extract_entities:
                    self._extract_and_create_entities(
                        page_data, page_id, loader, created_entities, stats
                    )

            except Exception as e:
                logger.error(f"处理第 {idx} 个页面时出错: {e}", exc_info=True)
                continue

        logger.info(f"图谱构建完成: {stats}")
        return stats

    def _get_or_create_document(
        self,
        page_data: Dict[str, Any],
        created_docs: set,
        stats: Dict[str, int],
    ) -> Optional[str]:
        """获取或创建文献节点."""
        doc_title = page_data.get("document_title", "史记")
        author = page_data.get("author", "司马迁")
        dynasty = page_data.get("dynasty")

        # 生成文献 ID
        doc_id = f"doc_{hashlib.md5(doc_title.encode()).hexdigest()[:8]}"

        if doc_id not in created_docs:
            doc = Document(
                doc_id=doc_id,
                title=doc_title,
                author=author,
                dynasty=dynasty,
                category="史部",
                description=f"{doc_title}，{author}撰",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            self.client.create_document(doc.to_dict())
            created_docs.add(doc_id)
            stats["documents"] += 1

        return doc_id

    def _get_or_create_volume(
        self,
        page_data: Dict[str, Any],
        doc_id: Optional[str],
        created_volumes: set,
        stats: Dict[str, int],
    ) -> Optional[str]:
        """获取或创建卷次节点."""
        volume_number = page_data.get("volume_number")
        volume_title = page_data.get("volume_title")

        if not volume_number:
            return None

        volume_id = f"{doc_id}_vol_{volume_number:03d}"

        if volume_id not in created_volumes:
            volume = Volume(
                volume_id=volume_id,
                volume_number=volume_number,
                volume_title=volume_title,
                description=f"{volume_title or f'第{volume_number}卷'}",
            )
            self.client.create_volume(volume.to_dict())
            created_volumes.add(volume_id)
            stats["volumes"] += 1

            # 创建 Document-Volume 关系
            if doc_id:
                self.client.create_has_volume_relation(
                    doc_id, volume_id, sequence=volume_number
                )
                stats["relationships"] += 1

        return volume_id

    def _create_page(
        self,
        page_data: Dict[str, Any],
        stats: Dict[str, int],
    ):
        """创建页面节点."""
        page_id = page_data["page_id"]
        image_path = page_data.get("image_path", "")

        # 计算图片哈希
        image_hash = None
        if image_path and Path(image_path).exists():
            try:
                with open(image_path, "rb") as f:
                    image_hash = hashlib.md5(f.read()).hexdigest()
            except Exception:
                pass

        page = Page(
            page_id=page_id,
            page_number=page_data.get("page_number", 1),
            image_path=image_path,
            image_hash=image_hash,
            ocr_text=page_data.get("ocr_text", ""),
            ocr_confidence=page_data.get("ocr_confidence", 0.0),
            text_direction=page_data.get("text_direction", "vertical"),
            width=page_data.get("width"),
            height=page_data.get("height"),
            created_at=datetime.now(),
        )
        self.client.create_page(page.to_dict())
        stats["pages"] += 1

    def _get_or_create_layout(
        self,
        page_data: Dict[str, Any],
        created_layouts: Dict[str, str],
        stats: Dict[str, int],
    ) -> Optional[str]:
        """获取或创建版式节点."""
        line_count = page_data.get("line_count")
        text_direction = page_data.get("text_direction")

        if not line_count:
            return None

        # 从文本行推断列数（简单估算）
        column_count = self._estimate_column_count(page_data)

        layout_info = {
            "column_count": column_count,
            "line_count": line_count,
            "border_color": None,  # 需要图像分析
            "border_type": None,
        }

        layout_sig = f"{column_count}_{line_count}"

        if layout_sig not in created_layouts:
            layout_id = f"layout_{hashlib.md5(layout_sig.encode()).hexdigest()[:8]}"
            layout = Layout(
                layout_id=layout_id,
                column_count=column_count,
                line_count=line_count,
            )
            self.client.create_layout(layout.to_dict())
            created_layouts[layout_sig] = layout_id
            stats["layouts"] += 1
        else:
            layout_id = created_layouts[layout_sig]

        return layout_id

    def _estimate_column_count(self, page_data: Dict[str, Any]) -> int:
        """估算列数（基于文本行的 X 坐标聚类）."""
        text_lines = page_data.get("text_lines", [])
        if not text_lines:
            return 1

        # 提取每行的 X 坐标（取中心点）
        x_coords = []
        for line in text_lines:
            position = line.get("position", [])
            if len(position) >= 2:
                x1 = position[0][0]
                x2 = position[1][0]
                x_center = (x1 + x2) / 2
                x_coords.append(x_center)

        if not x_coords:
            return 1

        # 简单聚类：按 X 坐标排序，找间隔
        x_coords.sort()
        clusters = 1
        threshold = 100  # 像素阈值

        for i in range(1, len(x_coords)):
            if x_coords[i] - x_coords[i - 1] > threshold:
                clusters += 1

        return clusters

    def _get_or_create_edition(
        self,
        page_data: Dict[str, Any],
        created_editions: set,
        stats: Dict[str, int],
    ) -> Optional[str]:
        """获取或创建版本节点."""
        edition_type = page_data.get("edition_type")
        edition_name = page_data.get("edition_name")
        publisher = page_data.get("publisher")
        publish_year = page_data.get("publish_year")

        if not edition_type:
            return None

        edition_id = f"ed_{hashlib.md5(edition_name.encode() if edition_name else edition_type.encode()).hexdigest()[:8]}"

        if edition_id not in created_editions:
            edition = Edition(
                edition_id=edition_id,
                edition_type=edition_type,
                edition_name=edition_name,
                publisher=publisher,
                publish_year=publish_year,
                description=f"{edition_name or edition_type}",
            )
            self.client.create_edition(edition.to_dict())
            created_editions.add(edition_id)
            stats["editions"] += 1

        return edition_id

    def _get_or_create_collection(
        self,
        page_data: Dict[str, Any],
        doc_id: Optional[str],
        created_collections: set,
        stats: Dict[str, int],
    ) -> Optional[str]:
        """获取或创建馆藏节点."""
        institution = page_data.get("institution")
        catalog_number = page_data.get("catalog_number")
        completeness = page_data.get("completeness")

        if not institution:
            return None

        collection_id = f"coll_{hashlib.md5(institution.encode()).hexdigest()[:8]}"

        if collection_id not in created_collections:
            collection = Collection(
                collection_id=collection_id,
                institution=institution,
                call_number=catalog_number,
                notes=completeness,
            )
            self.client.create_collection(collection.to_dict())
            created_collections.add(collection_id)
            stats["collections"] += 1

            # 创建 Document-Collection 关系
            if doc_id:
                self.client.create_stored_in_relation(
                    doc_id,
                    collection_id,
                    completeness=completeness or "完整",
                )
                stats["relationships"] += 1

        return collection_id

    def _extract_and_create_entities(
        self,
        page_data: Dict[str, Any],
        page_id: str,
        loader: OutputsDataLoader,
        created_entities: Dict[str, str],
        stats: Dict[str, int],
    ):
        """提取并创建实体节点."""
        ocr_text = page_data.get("ocr_text", "")
        if not ocr_text:
            return

        entities = loader.extract_entities_from_text(ocr_text)

        for entity_data in entities:
            entity_text = entity_data["entity_text"]
            entity_type = entity_data["entity_type"]

            # 生成实体 ID
            entity_key = f"{entity_text}_{entity_type}"
            entity_id = f"ent_{hashlib.md5(entity_key.encode()).hexdigest()[:8]}"

            # 创建实体节点（如果不存在）
            if entity_key not in created_entities:
                entity = Entity(
                    entity_id=entity_id,
                    entity_text=entity_text,
                    entity_type=entity_type,
                    normalized_name=entity_text,
                )
                self.client.create_entity(entity.to_dict())
                created_entities[entity_key] = entity_id
                stats["entities"] += 1

            # 创建 Page-Entity 关系
            self.client.create_mentions_relation(
                page_id,
                entity_id,
                mention_count=1,
                context=ocr_text[:100],
            )
            stats["relationships"] += 1

    def build_similarity_relations_from_embeddings(
        self,
        embeddings_path: Path,
        ids_path: Path,
        top_k: int = 10,
        threshold: float = 0.8,
    ) -> int:
        """从嵌入向量构建相似关系.

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

        # 归一化
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        embeddings = embeddings / norms

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
                            logger.debug(f"创建相似关系失败: {e}")

            if (i // batch_size + 1) % 10 == 0:
                logger.info(f"已处理 {batch_end}/{len(embeddings)} 个向量")

        logger.info(f"创建了 {relation_count} 个相似关系")
        return relation_count
