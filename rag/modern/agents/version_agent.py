"""版本判定Agent - 判断古籍版本类型."""
import logging
import re
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class VersionAgent(BaseAgent):
    """版本判定Agent，专注于判断版本类型和时代."""

    def __init__(self, llm_client):
        super().__init__(llm_client, "VersionAgent")

    def build_prompt(
        self,
        image_path: str,
        retrieved_context: List[Dict[str, Any]],
        previous_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建版本判定Prompt."""

        # 提取检索到的版本信息
        context_versions = []
        for ctx in retrieved_context[:5]:  # 只用Top-5
            metadata = ctx.get("metadata", {})
            edition_type = metadata.get("edition_type", "")
            dynasty = metadata.get("dynasty", "")
            if edition_type or dynasty:
                context_versions.append(f"- {dynasty} {edition_type}")

        context_text = "\n".join(context_versions) if context_versions else "（无相似版本参考）"

        prompt = f"""你是古籍版本鉴定专家。请仔细观察图片，判断这部古籍的版本类型和时代。

## 检索到的相似版本参考
{context_text}

## 判定任务
请从以下维度进行判定，**只输出结论，不要输出推理过程**：

### 1. 版本类型
从以下类型中选择最匹配的一项：
- 刻本（宋刻、元刻、明刻、清刻）
- 活字本（木活字、铜活字、泥活字）
- 写本（手抄本）
- 石印本
- 影印本
- 其他

### 2. 时代判定
格式：朝代 + 具体年号（如有）
示例：明嘉靖四年（1525）、宋淳熙年间、清康熙刻本

### 3. 版本特征
列出3-5个关键特征（字体、刻工、纸张、墨色等）

### 4. 置信度
给出判定的置信度：高/中/低

## 输出格式（严格按此格式）
```
版本类型: [类型]
时代: [朝代年号]
关键特征:
- [特征1]
- [特征2]
- [特征3]
置信度: [高/中/低]
```

请开始判定："""

        return prompt

    def parse_output(self, llm_output: str) -> Dict[str, Any]:
        """解析版本判定结果."""

        result = {
            "version_type": None,
            "dynasty": None,
            "era": None,
            "key_features": [],
            "confidence": "中"
        }

        # 提取版本类型
        version_match = re.search(r"版本类型[:：]\s*(.+)", llm_output)
        if version_match:
            result["version_type"] = version_match.group(1).strip()

        # 提取时代
        era_match = re.search(r"时代[:：]\s*(.+)", llm_output)
        if era_match:
            era_text = era_match.group(1).strip()
            result["era"] = era_text

            # 提取朝代
            dynasty_match = re.search(r"(宋|元|明|清|唐|汉|魏晋|南北朝)", era_text)
            if dynasty_match:
                result["dynasty"] = dynasty_match.group(1)

        # 提取关键特征
        features_section = re.search(r"关键特征[:：]\s*\n((?:[-•]\s*.+\n?)+)", llm_output)
        if features_section:
            features_text = features_section.group(1)
            features = re.findall(r"[-•]\s*(.+)", features_text)
            result["key_features"] = [f.strip() for f in features]

        # 提取置信度
        confidence_match = re.search(r"置信度[:：]\s*(高|中|低)", llm_output)
        if confidence_match:
            result["confidence"] = confidence_match.group(1)

        return result
