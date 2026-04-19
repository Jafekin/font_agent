"""LangChain tool wrappers for NaiveRAG and GraphRAG skills."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from ocr.client import KandiangujiOCRClient
from ocr.config import get_default_config
from rag.graph.client import Neo4jClient
from rag.graph.recognizer import ImageRecognizer
from rag.naive.pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class NaiveRAGToolInput(BaseModel):
    """Arguments accepted by the NaiveRAG skill tool."""

    image_path: str = Field(description="待检索图片的本地路径")
    script_type: str = Field(description="目标文字类型，例如汉文古籍、甲骨文")
    hint: str = Field(default="", description="用户提供的辅助提示")
    k: int = Field(default=3, ge=1, le=10, description="返回的相似参考数量")


class GraphRAGToolInput(BaseModel):
    """Arguments accepted by the GraphRAG skill tool."""

    image_path: str = Field(description="待检索图片的本地路径")
    top_k: int = Field(default=5, ge=1, le=10, description="最终返回候选页面数")
    naive_k: int = Field(default=8, ge=1, le=20, description="NaiveRAG 种子检索数量")
    bfs_depth: int = Field(default=1, ge=1, le=3, description="GraphRAG BFS 扩展深度")
    text_limit: int = Field(default=8, ge=1, le=20, description="GraphRAG 全文检索数量")


class NaiveRAGSkill:
    """Wrap the existing NaiveRAG pipeline as a LangChain tool."""

    name = "naive_rag_skill"
    description = (
        "适合做图像相似页检索与参考文本召回。"
        "输入图片路径、script_type 和 hint，返回相似参考页及文字上下文。"
    )

    def __init__(self, index_path: str | None = None) -> None:
        self.pipeline = RAGPipeline(index_path=index_path)

    def run(
        self,
        image_path: str,
        script_type: str,
        hint: str = "",
        k: int = 3,
    ) -> Dict[str, Any]:
        return self.pipeline.run(
            image_path=image_path,
            script_type=script_type,
            hint=hint,
            k=k,
        )

    def as_tool(
        self,
        on_result: Callable[[Dict[str, Any]], None],
    ):
        from langchain_core.tools import StructuredTool

        def _tool(
            image_path: str,
            script_type: str,
            hint: str = "",
            k: int = 3,
        ) -> str:
            payload = self.run(image_path=image_path, script_type=script_type, hint=hint, k=k)
            on_result(payload)
            refs = payload.get("retrieved_references") or []
            text_info = payload.get("retrieved_text_info") or []
            summary = {
                "success": payload.get("success", False),
                "pipeline_mode": payload.get("pipeline_mode"),
                "num_references": payload.get("num_references", 0),
                "references": refs[:5],
                "text_preview": text_info[:3],
                "error": payload.get("error"),
            }
            return json.dumps(summary, ensure_ascii=False)

        return StructuredTool.from_function(
            func=_tool,
            name=self.name,
            description=self.description,
            args_schema=NaiveRAGToolInput,
        )


class GraphRAGSkill:
    """Wrap GraphRAG recognition as a LangChain tool."""

    name = "graph_rag_skill"
    description = (
        "适合做版本判定、实体关系、图谱扩展和结构化候选页识别。"
        "输入图片路径，返回图谱候选页面、文献信息、版本信息与证据链。"
    )

    def __init__(
        self,
        *,
        index_path: str | None = None,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "password",
        neo4j_database: str = "neo4j",
    ) -> None:
        self.index_path = index_path
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.neo4j_database = neo4j_database

    def _build_ocr_client(self) -> Optional[KandiangujiOCRClient]:
        try:
            return KandiangujiOCRClient(get_default_config())
        except Exception as exc:
            logger.info("OCR client unavailable for GraphRAG skill: %s", exc)
            return None

    def run(
        self,
        image_path: str,
        top_k: int = 5,
        naive_k: int = 8,
        bfs_depth: int = 1,
        text_limit: int = 8,
    ) -> Dict[str, Any]:
        path = Path(image_path)
        if not path.exists():
            return {"success": False, "error": f"图片不存在: {image_path}", "results": []}

        try:
            with Neo4jClient(
                uri=self.neo4j_uri,
                username=self.neo4j_user,
                password=self.neo4j_password,
                database=self.neo4j_database,
            ) as client:
                if not client.verify_connectivity():
                    return {"success": False, "error": "无法连接到 Neo4j", "results": []}

                recognizer = ImageRecognizer(
                    neo4j_client=client,
                    index_path=self.index_path,
                    ocr_client=self._build_ocr_client(),
                )
                results = recognizer.recognize(
                    image_path=path,
                    top_k=top_k,
                    naive_k=naive_k,
                    bfs_depth=bfs_depth,
                    text_limit=text_limit,
                )
        except Exception as exc:
            logger.warning("GraphRAG skill execution failed: %s", exc)
            return {"success": False, "error": str(exc), "results": []}

        return {
            "success": True,
            "results": [asdict(item) for item in results],
            "num_references": len(results),
        }

    def as_tool(
        self,
        on_result: Callable[[Dict[str, Any]], None],
    ):
        from langchain_core.tools import StructuredTool

        def _tool(
            image_path: str,
            top_k: int = 5,
            naive_k: int = 8,
            bfs_depth: int = 1,
            text_limit: int = 8,
        ) -> str:
            payload = self.run(
                image_path=image_path,
                top_k=top_k,
                naive_k=naive_k,
                bfs_depth=bfs_depth,
                text_limit=text_limit,
            )
            on_result(payload)
            results = payload.get("results") or []
            preview = []
            for item in results[:3]:
                preview.append(
                    {
                        "page_id": item.get("page_id"),
                        "title": (item.get("document") or {}).get("title"),
                        "edition_id": (item.get("edition") or {}).get("edition_id"),
                        "score": ((item.get("score") or {}).get("final")),
                        "evidence": (item.get("evidence") or [])[:2],
                    }
                )
            summary = {
                "success": payload.get("success", False),
                "num_references": payload.get("num_references", 0),
                "results_preview": preview,
                "error": payload.get("error"),
            }
            return json.dumps(summary, ensure_ascii=False)

        return StructuredTool.from_function(
            func=_tool,
            name=self.name,
            description=self.description,
            args_schema=GraphRAGToolInput,
        )


def resolve_neo4j_settings() -> Dict[str, str]:
    """Read Neo4j connection settings from env with safe defaults."""
    return {
        "neo4j_uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "neo4j_user": os.getenv("NEO4J_USER", "neo4j"),
        "neo4j_password": os.getenv("NEO4J_PASSWORD", "password"),
        "neo4j_database": os.getenv("NEO4J_DATABASE", "neo4j"),
    }
