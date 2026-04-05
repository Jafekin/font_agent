"""视觉编码器 - 使用Chinese-CLIP提取图像特征."""
import logging
from pathlib import Path
from typing import Union, List
import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)


class VisionEncoder:
    """视觉编码器，支持全局和局部特征提取."""

    def __init__(self, model_name: str = "OFA-Sys/chinese-clip-vit-large-patch14-336px", device: str = "cuda"):
        """初始化视觉编码器.

        Args:
            model_name: 模型名称
            device: 设备 (cuda/cpu)
        """
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model = None
        self.processor = None
        self.model_name = model_name

        logger.info(f"初始化视觉编码器: {model_name} on {self.device}")

    def _lazy_load(self):
        """延迟加载模型."""
        if self.model is not None:
            return

        try:
            from transformers import ChineseCLIPModel, ChineseCLIPProcessor

            self.processor = ChineseCLIPProcessor.from_pretrained(self.model_name)
            self.model = ChineseCLIPModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()

            logger.info("视觉编码器加载成功")
        except Exception as e:
            logger.error(f"加载视觉编码器失败: {e}")
            raise

    def encode_image(self, image: Union[str, Path, Image.Image]) -> np.ndarray:
        """编码单张图像.

        Args:
            image: 图像路径或PIL Image对象

        Returns:
            图像特征向量 (768-dim)
        """
        self._lazy_load()

        # 加载图像
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        # 预处理
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 编码
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            # 兼容部分版本返回 BaseModelOutputWithPooling 而非张量
            if not isinstance(image_features, torch.Tensor):
                image_features = image_features.pooler_output
            # 归一化
            image_features = image_features / torch.norm(image_features, dim=-1, keepdim=True)

        return image_features.cpu().numpy()[0]

    def encode_images_batch(self, images: List[Union[str, Path, Image.Image]]) -> np.ndarray:
        """批量编码图像.

        Args:
            images: 图像列表

        Returns:
            图像特征矩阵 (N, 768)
        """
        self._lazy_load()

        # 加载图像
        pil_images = []
        for img in images:
            if isinstance(img, (str, Path)):
                pil_images.append(Image.open(img).convert("RGB"))
            else:
                pil_images.append(img)

        # 预处理
        inputs = self.processor(images=pil_images, return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 编码
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            # 兼容部分版本返回 BaseModelOutputWithPooling 而非张量
            if not isinstance(image_features, torch.Tensor):
                image_features = image_features.pooler_output
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        return image_features.cpu().numpy()

    def extract_local_features(self, image: Union[str, Path, Image.Image], regions: List[tuple]) -> List[np.ndarray]:
        """提取局部区域特征（用于版心、印章等）.

        Args:
            image: 图像路径或PIL Image对象
            regions: 区域列表 [(x1, y1, x2, y2), ...]

        Returns:
            局部特征列表
        """
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        local_features = []
        for region in regions:
            x1, y1, x2, y2 = region
            cropped = image.crop((x1, y1, x2, y2))
            feature = self.encode_image(cropped)
            local_features.append(feature)

        return local_features
