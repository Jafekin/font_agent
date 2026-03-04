"""OCR 输出管理器."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFont

from .models import OCRResult


class OCROutputManager:
    """管理 OCR 结果的输出和存储."""

    def __init__(self, base_dir: Path):
        """初始化输出管理器.

        Args:
            base_dir: 输出根目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_output_structure(self, image_name: str) -> Dict[str, Path]:
        """为单个图片创建输出目录结构.

        目录结构:
        outputs/
        └── {image_name}/
            ├── raw/          # 原始 JSON 响应
            ├── text/         # 纯文本输出
            ├── overlay/      # 标注图片
            └── metadata.json # 元数据

        Args:
            image_name: 图片名称（不含扩展名）

        Returns:
            包含各目录路径的字典
        """
        output_root = self.base_dir / image_name
        paths = {
            "root": output_root,
            "raw": output_root / "raw",
            "text": output_root / "text",
            "overlay": output_root / "overlay",
        }

        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)

        return paths

    def save_json(
        self,
        result: OCRResult,
        output_path: Path,
        pretty: bool = True,
    ) -> Path:
        """保存 JSON 格式的识别结果.

        Args:
            result: OCR 识别结果
            output_path: 输出文件路径
            pretty: 是否格式化输出

        Returns:
            保存的文件路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = result.to_dict()
        indent = 2 if pretty else None

        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=indent),
            encoding="utf-8",
        )
        return output_path

    def save_raw_json(
        self,
        raw_response: Dict[str, Any],
        output_path: Path,
    ) -> Path:
        """保存原始 API 响应.

        Args:
            raw_response: API 原始响应
            output_path: 输出文件路径

        Returns:
            保存的文件路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(
            json.dumps(raw_response, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def save_text(
        self,
        result: OCRResult,
        output_path: Path,
        separator: str = "\n",
    ) -> Path:
        """保存纯文本格式的识别结果.

        Args:
            result: OCR 识别结果
            output_path: 输出文件路径
            separator: 文本行分隔符

        Returns:
            保存的文件路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        text = result.get_full_text(separator=separator)
        output_path.write_text(text, encoding="utf-8")
        return output_path

    def save_overlay_image(
        self,
        image_path: Path,
        result: OCRResult,
        output_path: Path,
        *,
        line_color: str = "red",
        line_width: int = 2,
        text_color: str = "yellow",
        show_text: bool = True,
        font_size: int = 20,
    ) -> Path:
        """在图片上绘制识别框和文本.

        Args:
            image_path: 原始图片路径
            result: OCR 识别结果
            output_path: 输出图片路径
            line_color: 边框颜色
            line_width: 边框宽度
            text_color: 文本颜色
            show_text: 是否显示识别文本
            font_size: 字体大小

        Returns:
            保存的图片路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 加载图片
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)

        # 尝试加载字体
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/PingFang.ttc", font_size)
        except Exception:
            font = ImageFont.load_default()

        # 绘制每个文本行
        for line in result.text_lines:
            polygon = line.position
            if len(polygon) >= 3:
                # 绘制多边形边框
                flat = [tuple(pt) for pt in polygon]
                draw.line(flat + [flat[0]], fill=line_color, width=line_width)

                # 绘制文本标签
                if show_text and flat and line.text:
                    draw.text(flat[0], line.text[:10],
                              fill=text_color, font=font)

        # 保存图片
        image.save(output_path, quality=95)
        return output_path

    def save_metadata(
        self,
        image_path: Path,
        result: OCRResult,
        output_path: Path,
        **extra_info,
    ) -> Path:
        """保存元数据信息.

        Args:
            image_path: 原始图片路径
            result: OCR 识别结果
            output_path: 输出文件路径
            **extra_info: 额外的元数据信息

        Returns:
            保存的文件路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        metadata = {
            "source_image": str(image_path),
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "line_count": result.get_text_count(),
                "average_confidence": result.get_average_confidence(),
                "is_vertical": result.is_vertical_text(),
                "image_size": {
                    "width": result.width,
                    "height": result.height,
                },
            },
            **extra_info,
        }

        output_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def save_all(
        self,
        image_path: Path,
        result: OCRResult,
        image_name: Optional[str] = None,
    ) -> Dict[str, Path]:
        """保存所有格式的输出.

        Args:
            image_path: 原始图片路径
            result: OCR 识别结果
            image_name: 自定义输出名称（默认使用图片名）

        Returns:
            包含所有输出文件路径的字典
        """
        if image_name is None:
            image_name = image_path.stem

        # 创建目录结构
        paths = self.create_output_structure(image_name)

        # 保存各种格式
        saved_files = {
            "json": self.save_json(
                result,
                paths["root"] / f"{image_name}.json",
            ),
            "raw_json": self.save_raw_json(
                result.raw_data,
                paths["raw"] / f"{image_name}_raw.json",
            ),
            "text": self.save_text(
                result,
                paths["text"] / f"{image_name}.txt",
            ),
            "overlay": self.save_overlay_image(
                image_path,
                result,
                paths["overlay"] / f"{image_name}_overlay{image_path.suffix}",
            ),
            "metadata": self.save_metadata(
                image_path,
                result,
                paths["root"] / "metadata.json",
            ),
        }

        return saved_files
