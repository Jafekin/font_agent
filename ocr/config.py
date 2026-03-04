"""OCR 模块配置管理."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class OCRConfig:
    """OCR 客户端配置."""

    # API 认证
    token: str
    email: str

    # 网络配置
    base_url: str = "https://ocr.kandianguji.com"
    timeout: int = 60
    chunk_size: int = 1024 * 256

    # 输出配置
    output_dir: Optional[Path] = None
    save_json: bool = True
    save_txt: bool = True
    save_overlay: bool = True

    # OCR 参数默认值
    char_ocr: bool = False
    det_mode: str = "auto"
    image_size: int = 0
    return_position: bool = True
    return_choices: bool = False
    version: str = "default"
    det_layout: bool = False
    only_plain_text: bool = False
    return_layout: bool = False
    auto_insert_space: bool = False
    hp_line_words_angel: str = "left2right"
    sp_line_words_angel: str = "top2bottom"

    @classmethod
    def from_env(cls, output_dir: Optional[Path] = None) -> OCRConfig:
        """从环境变量加载配置."""
        # token = os.getenv("KANDIANGUJI_TOKEN", "")
        # email = os.getenv("KANDIANGUJI_EMAIL", "")

        token = "6a750d32-b0eb-48ac-bdf8-897923e9555d"
        email = "17324018120"

        if not token or not email:
            raise ValueError(
                "请设置环境变量 KANDIANGUJI_TOKEN 和 KANDIANGUJI_EMAIL"
            )

        return cls(
            token=token,
            email=email,
            output_dir=output_dir or Path("ocr/outputs"),
        )

    def get_output_dir(self, base_path: Optional[Path] = None) -> Path:
        """获取输出目录路径."""
        if base_path:
            return base_path
        if self.output_dir:
            return self.output_dir
        return Path("ocr/outputs")


# 默认配置实例
DEFAULT_CONFIG: Optional[OCRConfig] = None


def get_default_config() -> OCRConfig:
    """获取默认配置（懒加载）."""
    global DEFAULT_CONFIG
    if DEFAULT_CONFIG is None:
        DEFAULT_CONFIG = OCRConfig.from_env()
    return DEFAULT_CONFIG
