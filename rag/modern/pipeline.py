"""现代RAG主流程 - 多阶段推理编排."""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import time

from .config import ModernRAGConfig
from .encoders import VisionEncoder, TextEncoder
from .retrievers import HybridRetriever
from .agents import VersionAgent, CatalogAgent

logger = logging.getLogger(__name__)


class ModernRAGPipeline:
    """现代RAG流程，采用多阶段推理架构."""

    def __init__(self, config: Optional[ModernRAGConfig] = None):
        """初始化流程.

        Args:
            config: 配置对象
        """
        self.config = config or ModernRAGConfig()

        # 延迟加载组件
        self._vision_encoder = None
        self._text_encoder = None
        self._retriever = None
        self._llm_client = None
        self._agents = {}

        logger.info("现代RAG流程初始化完成")

    def _get_vision_encoder(self) -> VisionEncoder:
        """获取视觉编码器."""
        if self._vision_encoder is None:
            self._vision_encoder = VisionEncoder(
                model_name=self.config.model.vision_model,
                device=self.config.model.vision_device
            )
        return self._vision_encoder

    def _get_text_encoder(self) -> TextEncoder:
        """获取文本编码器."""
        if self._text_encoder is None:
            self._text_encoder = TextEncoder(
                model_name=self.config.model.text_model,
                device=self.config.model.text_device
            )
        return self._text_encoder

    def _get_retriever(self) -> HybridRetriever:
        """获取混合检索器."""
        if self._retriever is None:
            self._retriever = HybridRetriever(
                index_dir=self.config.index_dir,
                vector_weight=self.config.retriever.fusion_weights["vector"],
                text_weight=self.config.retriever.fusion_weights["text"],
                graph_weight=self.config.retriever.fusion_weights["graph"]
            )
        return self._retriever

    def _get_llm_client(self):
        """获取LLM客户端."""
        if self._llm_client is None:
            from openai import OpenAI
            self._llm_client = OpenAI(
                api_key=self.config.model.llm_api_key,
                base_url=self.config.model.llm_base_url
            )
        return self._llm_client

    def _get_agent(self, agent_name: str):
        """获取Agent实例."""
        if agent_name not in self._agents:
            llm_client = self._get_llm_client()

            if agent_name == "version":
                self._agents[agent_name] = VersionAgent(llm_client)
            elif agent_name == "catalog":
                self._agents[agent_name] = CatalogAgent(llm_client)
            else:
                raise ValueError(f"未知的Agent: {agent_name}")

        return self._agents[agent_name]

    def run(
        self,
        image_path: str,
        ocr_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行完整的RAG流程.

        Args:
            image_path: 图像路径
            ocr_text: OCR文本（可选）
            metadata: 元数据（可选）

        Returns:
            分析结果字典
        """
        start_time = time.time()
        logger.info(f"开始处理: {image_path}")

        result = {
            "image_path": image_path,
            "success": False,
            "stages": {},
            "retrieval": {},
            "final_output": {},
            "timing": {}
        }

        try:
            # ============ Stage 1: 特征提取 ============
            stage_start = time.time()
            logger.info("[Stage 1] 特征提取")

            vision_encoder = self._get_vision_encoder()
            image_embedding = vision_encoder.encode_image(image_path)

            text_embedding = None
            if ocr_text:
                text_encoder = self._get_text_encoder()
                text_embedding = text_encoder.encode_text(ocr_text)

            result["timing"]["feature_extraction"] = time.time() - stage_start
            logger.info(
                f"[Stage 1] 完成，耗时 {result['timing']['feature_extraction']:.2f}s")

            # ============ Stage 2: 混合检索 ============
            stage_start = time.time()
            logger.info("[Stage 2] 混合检索")

            retriever = self._get_retriever()
            retrieved_results = retriever.hybrid_retrieve(
                query_embedding=image_embedding,
                query_text=ocr_text,
                query_metadata=metadata,
                top_k=self.config.retriever.hybrid_top_k
            )

            # 转换为字典格式
            retrieved_context = []
            for r in retrieved_results:
                retrieved_context.append({
                    "doc_id": r.doc_id,
                    "score": r.score,
                    "source": r.source,
                    "metadata": r.metadata,
                    "image_path": r.image_path,
                    "ocr_text": r.ocr_text
                })

            result["retrieval"] = {
                "num_results": len(retrieved_results),
                "top_scores": [r.score for r in retrieved_results[:3]],
                "sources": [r.source for r in retrieved_results]
            }

            result["timing"]["retrieval"] = time.time() - stage_start
            logger.info(
                f"[Stage 2] 完成，检索到 {len(retrieved_results)} 条结果，耗时 {result['timing']['retrieval']:.2f}s")

            # ============ Stage 3: 多阶段推理 ============
            if not self.config.pipeline.enable_multi_stage:
                logger.info("多阶段推理已禁用，跳过")
            else:
                # Stage 3.1: 版本判定
                stage_start = time.time()
                logger.info("[Stage 3.1] 版本判定")

                version_agent = self._get_agent("version")
                version_result = version_agent.run(
                    image_path=image_path,
                    retrieved_context=retrieved_context,
                    previous_results=None
                )

                result["stages"]["version"] = version_result
                result["timing"]["version_detection"] = time.time() - \
                    stage_start
                logger.info(
                    f"[Stage 3.1] 完成，耗时 {result['timing']['version_detection']:.2f}s")

                # Stage 3.2: 综合编目
                stage_start = time.time()
                logger.info("[Stage 3.2] 综合编目")

                catalog_agent = self._get_agent("catalog")
                catalog_result = catalog_agent.run(
                    image_path=image_path,
                    retrieved_context=retrieved_context,
                    previous_results={"version": version_result}
                )

                result["stages"]["catalog"] = catalog_result
                result["timing"]["catalog_generation"] = time.time() - \
                    stage_start
                logger.info(
                    f"[Stage 3.2] 完成，耗时 {result['timing']['catalog_generation']:.2f}s")

                # ============ Stage 4: 结果整合 ============
                result["final_output"] = {
                    "title": catalog_result.get("title"),
                    "author": catalog_result.get("author"),
                    "edition": catalog_result.get("edition"),
                    "version_type": version_result.get("version_type"),
                    "dynasty": version_result.get("dynasty"),
                    "layout": catalog_result.get("layout"),
                    "institution": catalog_result.get("institution"),
                    "transcription": catalog_result.get("transcription"),
                    "confidence": catalog_result.get("confidence", "中"),
                    "key_features": version_result.get("key_features", [])
                }

            result["success"] = True
            result["timing"]["total"] = time.time() - start_time

            logger.info(f"处理完成，总耗时 {result['timing']['total']:.2f}s")

        except Exception as e:
            logger.error(f"处理失败: {e}", exc_info=True)
            result["success"] = False
            result["error"] = str(e)
            result["timing"]["total"] = time.time() - start_time

        return result

    def batch_run(
        self,
        image_paths: List[str],
        ocr_texts: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """批量处理.

        Args:
            image_paths: 图像路径列表
            ocr_texts: OCR文本列表（可选）
            metadatas: 元数据列表（可选）

        Returns:
            结果列表
        """
        if ocr_texts is None:
            ocr_texts = [None] * len(image_paths)
        if metadatas is None:
            metadatas = [None] * len(image_paths)

        results = []
        for i, (img_path, ocr_text, metadata) in enumerate(zip(image_paths, ocr_texts, metadatas), 1):
            logger.info(f"批量处理进度: {i}/{len(image_paths)}")
            result = self.run(img_path, ocr_text, metadata)
            results.append(result)

        return results


def main():
    """命令行入口."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="现代RAG流程")
    parser.add_argument("--image", type=str, required=True, help="图像路径")
    parser.add_argument("--ocr-text", type=str, help="OCR文本")
    parser.add_argument("--edition-type", type=str, help="版本类型（如：刻本）")
    parser.add_argument("--dynasty", type=str, help="朝代（如：明）")
    parser.add_argument("--institution", type=str, help="馆藏机构")
    parser.add_argument("--volume-number", type=str, help="卷号")
    parser.add_argument("--output", type=str,
                        default="result.json", help="输出文件")
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    query_metadata = {
        "edition_type": args.edition_type,
        "dynasty": args.dynasty,
        "institution": args.institution,
        "volume_number": args.volume_number,
    }
    query_metadata = {k: v for k, v in query_metadata.items() if v}

    # 运行流程
    pipeline = ModernRAGPipeline()
    result = pipeline.run(
        image_path=args.image,
        ocr_text=args.ocr_text,
        metadata=query_metadata if query_metadata else None,
    )

    # 保存结果
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {args.output}")
    print(f"处理状态: {'成功' if result['success'] else '失败'}")
    print(f"总耗时: {result['timing']['total']:.2f}s")


if __name__ == "__main__":
    main()
