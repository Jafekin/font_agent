"""文本编码器 - 使用古汉语BERT提取文本特征."""
import logging
from typing import List, Union
import numpy as np
import torch

logger = logging.getLogger(__name__)


class TextEncoder:
    """文本编码器，专门处理古汉语文本."""

    def __init__(self, model_name: str = "SIKU-BERT/sikubert", device: str = "cuda"):
        """初始化文本编码器.

        Args:
            model_name: 模型名称
            device: 设备 (cuda/cpu)
        """
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model = None
        self.tokenizer = None
        self.model_name = model_name

        logger.info(f"初始化文本编码器: {model_name} on {self.device}")

    def _lazy_load(self):
        """延迟加载模型."""
        if self.model is not None:
            return

        try:
            from transformers import AutoTokenizer, AutoModel

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()

            logger.info("文本编码器加载成功")
        except Exception as e:
            logger.warning(f"加载SikuBERT失败，回退到RoBERTa: {e}")
            # 回退到通用中文模型
            self.tokenizer = AutoTokenizer.from_pretrained("hfl/chinese-roberta-wwm-ext")
            self.model = AutoModel.from_pretrained("hfl/chinese-roberta-wwm-ext").to(self.device)
            self.model.eval()

    def encode_text(self, text: str, max_length: int = 512) -> np.ndarray:
        """编码单个文本.

        Args:
            text: 输入文本
            max_length: 最大长度

        Returns:
            文本特征向量 (768-dim)
        """
        self._lazy_load()

        # Tokenize
        inputs = self.tokenizer(
            text,
            max_length=max_length,
            padding=True,
            truncation=True,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 编码
        with torch.no_grad():
            outputs = self.model(**inputs)
        # 使用[CLS] token的表示
        text_features = outputs.last_hidden_state[:, 0, :]
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        return text_features.cpu().numpy()[0]

    def encode_texts_batch(self, texts: List[str], max_length: int = 512) -> np.ndarray:
        """批量编码文本.

        Args:
            texts: 文本列表
            max_length: 最大长度

        Returns:
            文本特征矩阵 (N, 768)
        """
        self._lazy_load()

        # Tokenize
        inputs = self.tokenizer(
            texts,
            max_length=max_length,
            padding=True,
            truncation=True,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 编码
        with torch.no_grad():
            outputs = self.model(**inputs)
            text_features = outputs.last_hidden_state[:, 0, :]
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        return text_features.cpu().numpy()

    def extract_keywords(self, text: str, top_k: int = 10) -> List[tuple]:
        """提取关键词（基于TF-IDF）.

        Args:
            text: 输入文本
            top_k: 返回前K个关键词

        Returns:
            关键词列表 [(词, 分数), ...]
        """
        # 简单实现：基于字频
        from collections import Counter
        import re

        # 移除标点
        text = re.sub(r'[^\u4e00-\u9fa5]', '', text)

        # 统计字频
        char_freq = Counter(text)

        # 返回Top-K
        return char_freq.most_common(top_k)
