"""Agentic pipeline that lets a LangChain agent choose RAG skills."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PIL import Image

from rag.naive.pipeline import (
    _get_setting_or_env,
    analyze_with_llm,
)
from rag.naive.prompt import get_prompt

from .tools import GraphRAGSkill, NaiveRAGSkill, resolve_neo4j_settings

logger = logging.getLogger(__name__)

_AGENT_SYSTEM_PROMPT = """
你是古文字识别系统里的 RAG 路由 Agent。

你的职责：
1. 根据图片识别任务的目标，自主决定调用 `naive_rag_skill`、`graph_rag_skill` 或两者。
2. `naive_rag_skill` 更适合做相似页召回与参考文本补全。
3. `graph_rag_skill` 更适合做版本判定、实体关系、同版本页面扩展和结构化候选识别。
4. 如果任务包含版本、作者、馆藏、文献编目信息、相似版本判断，优先调用 `graph_rag_skill`。
5. 如果任务只需要基础参考上下文，也可以只调 `naive_rag_skill`。
6. 尽量少调用但保证结果充分；通常 1 到 2 个工具足够。
7. 最终回答只需简短说明你使用了哪些技能以及为什么。
"""


class AgenticRAGPipeline:
    """Hybrid pipeline: agent chooses between NaiveRAG and GraphRAG skills."""

    def __init__(
        self,
        index_path: str | None = None,
        *,
        model: str = "ernie-4.5-turbo-32k",
    ) -> None:
        self.index_path = index_path
        self.model = model
        neo4j_settings = resolve_neo4j_settings()
        self.naive_skill = NaiveRAGSkill(index_path=index_path)
        self.graph_skill = GraphRAGSkill(index_path=index_path, **neo4j_settings)

    def _build_agent(self, state: Dict[str, Any]):
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=self.model,
            temperature=0,
            api_key=_get_setting_or_env("OPENAI_API_KEY", "OPENAI_API_KEY"),
            base_url=_get_setting_or_env("OPENAI_BASE_URL", "OPENAI_BASE_URL"),
        )
        tools = [
            self.naive_skill.as_tool(lambda payload: state.__setitem__("naive", payload)),
            self.graph_skill.as_tool(lambda payload: state.__setitem__("graph", payload)),
        ]
        return create_agent(
            model=llm,
            tools=tools,
            system_prompt=_AGENT_SYSTEM_PROMPT,
        )

    def _run_agent(
        self,
        image_path: str,
        script_type: str,
        hint: str,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            agent = self._build_agent(state)
            return agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "请为下面的古文字识别任务选择合适的 RAG 技能。\n"
                                f"image_path={image_path}\n"
                                f"script_type={script_type}\n"
                                f"hint={hint or '（无）'}\n"
                                "请先决定要调用哪些技能，再给出简短结论。"
                            ),
                        }
                    ]
                }
            )
        except Exception as exc:
            logger.warning("LangChain agent routing failed, fallback to heuristic: %s", exc)
            state["naive"] = self.naive_skill.run(
                image_path=image_path,
                script_type=script_type,
                hint=hint,
                k=3,
            )
            if hint or script_type in {"汉文古籍", "敦煌文书", "汉文"}:
                state["graph"] = self.graph_skill.run(image_path=image_path)
            return {"messages": [{"role": "assistant", "content": "fallback: heuristic routing"}]}

    @staticmethod
    def _extract_agent_summary(agent_result: Dict[str, Any]) -> str:
        messages = agent_result.get("messages") or []
        if not messages:
            return ""
        last = messages[-1]
        content = getattr(last, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(last, dict):
            raw_content = last.get("content")
            if isinstance(raw_content, str):
                return raw_content
            if isinstance(raw_content, list):
                return "\n".join(
                    item.get("text", "") for item in raw_content if isinstance(item, dict)
                )
        return str(last)

    @staticmethod
    def _build_graph_context(graph_payload: Dict[str, Any]) -> List[str]:
        contexts: List[str] = []
        for item in (graph_payload.get("results") or [])[:5]:
            document = item.get("document") or {}
            edition = item.get("edition") or {}
            collection = item.get("collection") or {}
            layout = item.get("layout") or {}
            evidence = "；".join(item.get("evidence") or [])
            contexts.append(
                (
                    f"候选页 {item.get('page_id')}："
                    f"题名={document.get('title') or '未知'}；"
                    f"朝代={document.get('dynasty') or '未知'}；"
                    f"著者={document.get('authors') or '未知'}；"
                    f"版本={edition.get('version_type') or edition.get('edition_id') or '未知'}；"
                    f"馆藏={collection.get('institution') or '未知'}；"
                    f"版式行数={layout.get('line_count') or '未知'}；"
                    f"证据={evidence or '无'}"
                )
            )
        return contexts

    def _build_final_prompt(
        self,
        *,
        script_type: str,
        hint: str,
        agent_summary: str,
        naive_payload: Optional[Dict[str, Any]],
        graph_payload: Optional[Dict[str, Any]],
    ) -> str:
        naive_context = []
        if naive_payload:
            naive_context = list(naive_payload.get("retrieved_text_info") or [])

        merged_context = naive_context + self._build_graph_context(graph_payload or {})
        prompt = get_prompt(script_type, hint or "", merged_context)
        prompt += "\n\n# Agent 路由说明\n"
        prompt += agent_summary or "本次未返回显式路由说明。"
        prompt += "\n\n# 额外要求\n"
        prompt += (
            "请综合图片本身与以上检索证据完成识别。"
            "若 GraphRAG 候选给出了明确题名、版本、馆藏或作者，请优先吸收这些结构化信息；"
            "若检索结果之间冲突，请保留不确定性并说明依据。"
        )
        return prompt

    def run(
        self,
        image_path: str,
        script_type: str,
        hint: Optional[str] = None,
        k: int = 3,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        del k, metadata_filters

        state: Dict[str, Any] = {}
        agent_result = self._run_agent(
            image_path=image_path,
            script_type=script_type,
            hint=hint or "",
            state=state,
        )
        agent_summary = self._extract_agent_summary(agent_result)

        naive_payload = state.get("naive")
        graph_payload = state.get("graph")

        if not naive_payload and not graph_payload:
            naive_payload = self.naive_skill.run(
                image_path=image_path,
                script_type=script_type,
                hint=hint or "",
                k=3,
            )
            state["naive"] = naive_payload

        prompt = self._build_final_prompt(
            script_type=script_type,
            hint=hint or "",
            agent_summary=agent_summary,
            naive_payload=naive_payload,
            graph_payload=graph_payload,
        )

        try:
            with Image.open(image_path) as image_obj:
                analysis = analyze_with_llm(
                    image=image_obj,
                    script_type=script_type,
                    hint=hint or "",
                    prompt_text=prompt,
                )
        except Exception as exc:
            logger.error("Final LLM analysis failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "analysis": None,
                "retrieved_references": [],
                "retrieved_text_info": [],
            }

        references: List[str] = []
        scores: List[float] = []
        text_info: List[str] = []
        citations: List[Dict[str, Any]] = []
        selected_tools: List[str] = []

        if naive_payload and naive_payload.get("success", False):
            selected_tools.append("naive_rag_skill")
            references.extend(naive_payload.get("retrieved_references") or [])
            scores.extend(float(x) for x in (naive_payload.get("retrieval_scores") or []))
            text_info.extend(naive_payload.get("retrieved_text_info") or [])
            citations.extend(naive_payload.get("citations") or [])

        if graph_payload and graph_payload.get("success", False):
            selected_tools.append("graph_rag_skill")
            for item in graph_payload.get("results") or []:
                references.append(item.get("page_id", ""))
                final_score = (item.get("score") or {}).get("final")
                if final_score is not None:
                    scores.append(float(final_score))
            text_info.extend(self._build_graph_context(graph_payload))

        references = [ref for ref in references if ref]

        return {
            "success": True,
            "analysis": analysis,
            "retrieved_references": references,
            "retrieved_text_info": text_info,
            "num_references": len(references),
            "retrieval_scores": scores,
            "citations": citations,
            "pipeline_mode": "agentic_hybrid",
            "selected_tools": selected_tools,
            "agent_summary": agent_summary,
            "tool_payloads": {
                "naive": naive_payload,
                "graph": graph_payload,
            },
        }
