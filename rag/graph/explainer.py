"""证据路径解释器 - 生成可解释的查询证据链."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceNode:
    """证据节点."""

    node_id: str
    node_type: str  # Document, Volume, Page, Edition, etc.
    properties: Dict[str, Any]
    label: str  # 显示标签


@dataclass
class EvidenceRelation:
    """证据关系."""

    relation_type: str
    properties: Dict[str, Any]
    label: str  # 显示标签


@dataclass
class EvidencePath:
    """证据路径."""

    nodes: List[EvidenceNode]
    relations: List[EvidenceRelation]
    confidence: float
    explanation: str


class EvidenceExplainer:
    """证据路径解释器."""

    def __init__(self):
        """初始化解释器."""
        self.relation_templates = {
            "HAS_VOLUME": "{source} 包含 {target}",
            "HAS_PAGE": "{source} 包含 {target}",
            "SIMILAR_TO": "{source} 与 {target} 相似（相似度: {similarity_score:.2%}）",
            "BELONGS_TO_EDITION": "{source} 属于 {target}（置信度: {confidence:.2%}）",
            "STORED_IN": "{source} 存储于 {target}",
            "HAS_LAYOUT": "{source} 具有版式 {target}",
            "HAS_SEAL": "{source} 包含钤印 {target}",
            "MENTIONS": "{source} 提及 {target}（{mention_count} 次）",
            "RELATED_TO": "{source} 与 {target} 有 {relation_type} 关系",
            "CITES": "{source} 引用 {target}",
        }

    def explain_path(
        self,
        path_data: Dict[str, Any],
        query_context: Optional[str] = None,
    ) -> EvidencePath:
        """解释查询路径.

        Args:
            path_data: Neo4j 返回的路径数据
            query_context: 查询上下文描述

        Returns:
            证据路径对象
        """
        nodes = []
        relations = []

        # 解析节点
        for node_data in path_data.get("nodes", []):
            node = self._parse_node(node_data)
            nodes.append(node)

        # 解析关系
        for rel_data in path_data.get("relationships", []):
            relation = self._parse_relation(rel_data)
            relations.append(relation)

        # 计算整体置信度
        confidence = self._calculate_confidence(relations)

        # 生成解释文本
        explanation = self._generate_explanation(
            nodes, relations, query_context)

        return EvidencePath(
            nodes=nodes,
            relations=relations,
            confidence=confidence,
            explanation=explanation,
        )

    def explain_edition_inference(
        self,
        target_page_id: str,
        similar_pages: List[Dict[str, Any]],
        layout_matches: List[Dict[str, Any]],
        seal_matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """解释版本推断过程.

        Args:
            target_page_id: 目标页面 ID
            similar_pages: 相似页面列表
            layout_matches: 版式匹配列表
            seal_matches: 钤印匹配列表

        Returns:
            推断结果和证据链
        """
        evidence_chains = []

        # 1. 相似页面证据
        if similar_pages:
            for sp in similar_pages:
                chain = {
                    "type": "similarity",
                    "path": f"{target_page_id} --[SIMILAR_TO({sp['similarity']:.2%})]-> {sp['page_id']} --[BELONGS_TO_EDITION]-> {sp['edition']}",
                    "confidence": sp["similarity"],
                    "explanation": f"目标页面与 {sp['page_id']} 相似度为 {sp['similarity']:.2%}，后者属于 {sp['edition']}",
                }
                evidence_chains.append(chain)

        # 2. 版式匹配证据
        if layout_matches:
            for lm in layout_matches:
                chain = {
                    "type": "layout",
                    "path": f"{target_page_id} --[HAS_LAYOUT]-> {lm['layout_id']} <--[HAS_LAYOUT]-- {lm['page_id']} --[BELONGS_TO_EDITION]-> {lm['edition']}",
                    "confidence": 0.8,
                    "explanation": f"目标页面与 {lm['page_id']} 具有相同版式（{lm['layout_desc']}），后者属于 {lm['edition']}",
                }
                evidence_chains.append(chain)

        # 3. 钤印匹配证据
        if seal_matches:
            for sm in seal_matches:
                chain = {
                    "type": "seal",
                    "path": f"{target_page_id} --[HAS_SEAL]-> {sm['seal_id']} <--[HAS_SEAL]-- {sm['page_id']} --[BELONGS_TO_EDITION]-> {sm['edition']}",
                    "confidence": 0.9,
                    "explanation": f"目标页面与 {sm['page_id']} 包含相同钤印（{sm['seal_text']}），后者属于 {sm['edition']}",
                }
                evidence_chains.append(chain)

        # 统计各版本的证据数量
        edition_votes = {}
        for chain in evidence_chains:
            # 从 path 中提取版本名称（简化处理）
            edition = chain["path"].split("->")[-1].strip()
            if edition not in edition_votes:
                edition_votes[edition] = {
                    "count": 0,
                    "total_confidence": 0.0,
                    "evidence_types": set(),
                }
            edition_votes[edition]["count"] += 1
            edition_votes[edition]["total_confidence"] += chain["confidence"]
            edition_votes[edition]["evidence_types"].add(chain["type"])

        # 计算最终推断
        if edition_votes:
            best_edition = max(
                edition_votes.items(),
                key=lambda x: (x[1]["count"], x[1]["total_confidence"]),
            )
            final_confidence = min(
                best_edition[1]["total_confidence"] / best_edition[1]["count"],
                0.99,
            )

            return {
                "inferred_edition": best_edition[0],
                "confidence": final_confidence,
                "evidence_count": best_edition[1]["count"],
                "evidence_types": list(best_edition[1]["evidence_types"]),
                "evidence_chains": evidence_chains,
                "summary": self._generate_inference_summary(
                    target_page_id,
                    best_edition[0],
                    final_confidence,
                    evidence_chains,
                ),
            }
        else:
            return {
                "inferred_edition": None,
                "confidence": 0.0,
                "evidence_count": 0,
                "evidence_types": [],
                "evidence_chains": [],
                "summary": f"无法为 {target_page_id} 推断版本（缺少证据）",
            }

    def explain_entity_relation(
        self,
        entity1_id: str,
        entity2_id: str,
        paths: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """解释实体关系路径.

        Args:
            entity1_id: 实体 1 ID
            entity2_id: 实体 2 ID
            paths: 关系路径列表

        Returns:
            关系解释
        """
        if not paths:
            return {
                "relation_found": False,
                "explanation": f"{entity1_id} 与 {entity2_id} 之间未发现直接关系",
            }

        # 选择最短路径
        shortest_path = min(paths, key=lambda p: len(p.get("nodes", [])))

        # 解析路径
        path_steps = []
        nodes = shortest_path.get("nodes", [])
        relations = shortest_path.get("relationships", [])

        for i, rel in enumerate(relations):
            source = nodes[i]
            target = nodes[i + 1]
            step = {
                "source": source.get("entity_text", source.get("entity_id")),
                "relation": rel.get("relation_type", "RELATED_TO"),
                "target": target.get("entity_text", target.get("entity_id")),
                "description": rel.get("description", ""),
            }
            path_steps.append(step)

        # 生成解释
        explanation_parts = []
        for step in path_steps:
            if step["description"]:
                explanation_parts.append(
                    f"{step['source']} --[{step['relation']}: {step['description']}]--> {step['target']}"
                )
            else:
                explanation_parts.append(
                    f"{step['source']} --[{step['relation']}]--> {step['target']}"
                )

        return {
            "relation_found": True,
            "path_length": len(path_steps),
            "path_steps": path_steps,
            "explanation": " → ".join(explanation_parts),
            "summary": f"{entity1_id} 与 {entity2_id} 通过 {len(path_steps)} 步关系相连",
        }

    def explain_recommendation(
        self,
        target_id: str,
        recommendations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """解释推荐结果.

        Args:
            target_id: 目标对象 ID
            recommendations: 推荐列表

        Returns:
            带解释的推荐列表
        """
        explained_recommendations = []

        for rec in recommendations:
            reason = rec.get("reason", "unknown")
            score = rec.get("score", 0.0)

            explanation = self._get_recommendation_explanation(
                target_id,
                rec.get("item_id"),
                reason,
                score,
            )

            explained_recommendations.append(
                {
                    **rec,
                    "explanation": explanation,
                    "confidence": score,
                }
            )

        return explained_recommendations

    # ==================== 辅助方法 ====================

    def _parse_node(self, node_data: Dict[str, Any]) -> EvidenceNode:
        """解析节点数据."""
        node_type = node_data.get("labels", ["Unknown"])[0]
        properties = node_data.get("properties", {})

        # 生成显示标签
        label = self._generate_node_label(node_type, properties)

        return EvidenceNode(
            node_id=properties.get("id", "unknown"),
            node_type=node_type,
            properties=properties,
            label=label,
        )

    def _parse_relation(self, rel_data: Dict[str, Any]) -> EvidenceRelation:
        """解析关系数据."""
        relation_type = rel_data.get("type", "UNKNOWN")
        properties = rel_data.get("properties", {})

        # 生成显示标签
        label = self._generate_relation_label(relation_type, properties)

        return EvidenceRelation(
            relation_type=relation_type,
            properties=properties,
            label=label,
        )

    def _generate_node_label(
        self,
        node_type: str,
        properties: Dict[str, Any],
    ) -> str:
        """生成节点显示标签."""
        if node_type == "Document":
            return f"文献: {properties.get('title', 'Unknown')}"
        elif node_type == "Volume":
            return f"卷 {properties.get('volume_number', '?')}: {properties.get('volume_title', '')}"
        elif node_type == "Page":
            return f"第 {properties.get('page_number', '?')} 页"
        elif node_type == "Edition":
            return f"{properties.get('edition_name', properties.get('edition_type', 'Unknown'))}"
        elif node_type == "Collection":
            return f"{properties.get('institution', 'Unknown')}"
        elif node_type == "Layout":
            return f"版式（{properties.get('column_count', '?')}栏）"
        elif node_type == "Seal":
            return f"钤印: {properties.get('seal_text', 'Unknown')}"
        elif node_type == "Entity":
            return f"{properties.get('entity_text', 'Unknown')}（{properties.get('entity_type', '')}）"
        else:
            return f"{node_type}: {properties.get('id', 'Unknown')}"

    def _generate_relation_label(
        self,
        relation_type: str,
        properties: Dict[str, Any],
    ) -> str:
        """生成关系显示标签."""
        template = self.relation_templates.get(
            relation_type, "{relation_type}")

        # 填充模板
        try:
            return template.format(
                relation_type=relation_type,
                source="{source}",
                target="{target}",
                **properties,
            )
        except KeyError:
            return relation_type

    def _calculate_confidence(self, relations: List[EvidenceRelation]) -> float:
        """计算路径整体置信度."""
        if not relations:
            return 1.0

        confidences = []
        for rel in relations:
            if "confidence" in rel.properties:
                confidences.append(rel.properties["confidence"])
            elif "similarity_score" in rel.properties:
                confidences.append(rel.properties["similarity_score"])
            else:
                confidences.append(0.9)  # 默认置信度

        # 使用最小置信度作为整体置信度
        return min(confidences) if confidences else 0.9

    def _generate_explanation(
        self,
        nodes: List[EvidenceNode],
        relations: List[EvidenceRelation],
        query_context: Optional[str] = None,
    ) -> str:
        """生成路径解释文本."""
        if not nodes or not relations:
            return "空路径"

        explanation_parts = []

        if query_context:
            explanation_parts.append(f"查询: {query_context}\n")

        explanation_parts.append("证据路径:")

        for i, rel in enumerate(relations):
            source_node = nodes[i]
            target_node = nodes[i + 1]

            step = f"  {i + 1}. {source_node.label} --[{rel.label}]--> {target_node.label}"
            explanation_parts.append(step)

        return "\n".join(explanation_parts)

    def _generate_inference_summary(
        self,
        target_page_id: str,
        inferred_edition: str,
        confidence: float,
        evidence_chains: List[Dict[str, Any]],
    ) -> str:
        """生成版本推断总结."""
        summary_parts = [
            f"版本推断结果: {target_page_id} 可能属于 {inferred_edition}",
            f"置信度: {confidence:.2%}",
            f"证据数量: {len(evidence_chains)}",
            "",
            "证据来源:",
        ]

        # 按类型分组证据
        evidence_by_type = {}
        for chain in evidence_chains:
            etype = chain["type"]
            if etype not in evidence_by_type:
                evidence_by_type[etype] = []
            evidence_by_type[etype].append(chain)

        type_names = {
            "similarity": "相似页面",
            "layout": "版式匹配",
            "seal": "钤印匹配",
        }

        for etype, chains in evidence_by_type.items():
            summary_parts.append(
                f"  - {type_names.get(etype, etype)}: {len(chains)} 条")

        return "\n".join(summary_parts)

    def _get_recommendation_explanation(
        self,
        target_id: str,
        item_id: str,
        reason: str,
        score: float,
    ) -> str:
        """生成推荐解释."""
        reason_templates = {
            "similar": f"与 {target_id} 视觉相似（相似度: {score:.2%}）",
            "same_edition": f"与 {target_id} 属于同一版本",
            "shared_entity": f"与 {target_id} 提及相同的实体",
            "same_author": f"与 {target_id} 作者相同",
            "same_category": f"与 {target_id} 类别相同",
            "citation": f"与 {target_id} 存在引用关系",
        }

        return reason_templates.get(reason, f"推荐原因: {reason}（评分: {score:.2f}）")
