"""Agent基类."""
import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent基类，定义统一接口."""

    def __init__(self, llm_client, name: str):
        """初始化Agent.

        Args:
            llm_client: LLM客户端
            name: Agent名称
        """
        self.llm_client = llm_client
        self.name = name
        logger.info(f"初始化Agent: {name}")

    @abstractmethod
    def build_prompt(
        self,
        image_path: str,
        retrieved_context: List[Dict[str, Any]],
        previous_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建Prompt.

        Args:
            image_path: 图像路径
            retrieved_context: 检索到的上下文
            previous_results: 前序Agent的结果

        Returns:
            Prompt文本
        """
        pass

    @abstractmethod
    def parse_output(self, llm_output: str) -> Dict[str, Any]:
        """解析LLM输出.

        Args:
            llm_output: LLM原始输出

        Returns:
            结构化结果
        """
        pass

    def run(
        self,
        image_path: str,
        retrieved_context: List[Dict[str, Any]],
        previous_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行Agent推理.

        Args:
            image_path: 图像路径
            retrieved_context: 检索到的上下文
            previous_results: 前序Agent的结果

        Returns:
            推理结果
        """
        logger.info(f"[{self.name}] 开始推理")

        # 构建Prompt
        prompt = self.build_prompt(image_path, retrieved_context, previous_results)

        # 调用LLM
        try:
            from PIL import Image
            image = Image.open(image_path)

            # 调用LLM（假设使用OpenAI兼容接口）
            import base64
            import io

            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            response = self.llm_client.chat.completions.create(
                model="ernie-4.5-turbo-vl",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                stream=False,
            )

            llm_output = response.choices[0].message.content

        except Exception as e:
            logger.error(f"[{self.name}] LLM调用失败: {e}")
            return {"error": str(e), "agent": self.name}

        # 解析输出
        result = self.parse_output(llm_output)
        result["agent"] = self.name
        result["raw_output"] = llm_output

        logger.info(f"[{self.name}] 推理完成")
        return result
