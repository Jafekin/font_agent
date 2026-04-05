"""编目Agent - 生成完整的编目报告."""
import logging
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CatalogAgent(BaseAgent):
    """编目Agent，整合所有信息生成最终报告."""

    def __init__(self, llm_client):
        super().__init__(llm_client, "CatalogAgent")

    def build_prompt(
        self,
        image_path: str,
        retrieved_context: List[Dict[str, Any]],
        previous_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建编目Prompt."""

        # 提取前序Agent的结果
        version_info = ""
        if previous_results and "version" in previous_results:
            v = previous_results["version"]
            version_info = f"""
## 版本判定结果
- 版本类型: {v.get('version_type', '未知')}
- 时代: {v.get('era', '未知')}
- 关键特征: {', '.join(v.get('key_features', []))}
"""

        # 提取检索到的文本信息
        context_texts = []
        for ctx in retrieved_context[:3]:
            text_info = ctx.get("ocr_text", "")
            if text_info:
                context_texts.append(f"参考文本片段：{text_info[:100]}...")

        context_text = "\n".join(context_texts) if context_texts else "（无文本参考）"

        prompt = f"""你是古籍编目专家。请基于图片和已有信息，生成规范的编目报告。

{version_info}

## 检索到的相似古籍文本
{context_text}

## 编目任务
请按以下结构输出编目信息（**只输出有把握的信息，不确定的留空或标注"待考"**）：

### 1. 题名
格式：书名 + 卷数
示例：史记一百三十卷

### 2. 著者
格式：（朝代）姓名 + 角色
示例：（汉）司马迁撰　（南朝宋）裴骃集解

### 3. 版本
格式：朝代 + 年号 + 刻印者 + 版本类型
示例：明嘉靖四年（1525）王延喆刻本

### 4. 版式
格式：行数×字数，边栏类型
示例：半叶10行行20字，白口，左右双边

### 5. 现藏单位
示例：国家图书馆、北京大学图书馆

### 6. 本页释文
转录本页可见文字（不确定的字用□标注）

## 输出格式（JSON）
```json
{{
  "title": "书名卷数",
  "author": "著者信息",
  "edition": "版本信息",
  "layout": "版式信息",
  "institution": "现藏单位",
  "transcription": "本页释文",
  "confidence": "整体置信度(高/中/低)"
}}
```

请开始编目："""

        return prompt

    def parse_output(self, llm_output: str) -> Dict[str, Any]:
        """解析编目结果."""

        import json
        import re

        # 尝试提取JSON
        json_match = re.search(r"```json\s*\n(.*?)\n```", llm_output, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return result
            except json.JSONDecodeError:
                logger.warning("JSON解析失败，使用正则提取")

        # 回退到正则提取
        result = {
            "title": None,
            "author": None,
            "edition": None,
            "layout": None,
            "institution": None,
            "transcription": None,
            "confidence": "中"
        }

        # 简单提取（实际应该更健壮）
        for key in result.keys():
            pattern = rf'"{key}":\s*"([^"]*)"'
            match = re.search(pattern, llm_output)
            if match:
                result[key] = match.group(1)

        return result
