"""OCR 工具函数."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Tuple

from PIL import Image


def calculate_image_hash(image_path: Path, algorithm: str = "md5") -> str:
    """计算图片文件的哈希值.

    Args:
        image_path: 图片路径
        algorithm: 哈希算法（md5/sha256）

    Returns:
        哈希值字符串
    """
    hash_func = hashlib.md5() if algorithm == "md5" else hashlib.sha256()

    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def get_image_info(image_path: Path) -> dict:
    """获取图片基本信息.

    Args:
        image_path: 图片路径

    Returns:
        包含图片信息的字典
    """
    with Image.open(image_path) as img:
        return {
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "mode": img.mode,
            "size_bytes": image_path.stat().st_size,
        }


def validate_image_file(image_path: Path, max_size_mb: int = 10) -> Tuple[bool, str]:
    """验证图片文件是否有效.

    Args:
        image_path: 图片路径
        max_size_mb: 最大文件大小（MB）

    Returns:
        (是否有效, 错误信息)
    """
    if not image_path.exists():
        return False, "文件不存在"

    if not image_path.is_file():
        return False, "不是有效的文件"

    # 检查文件大小
    size_mb = image_path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"文件过大: {size_mb:.2f}MB (最大 {max_size_mb}MB)"

    # 检查是否为有效图片
    try:
        with Image.open(image_path) as img:
            img.verify()
        return True, ""
    except Exception as e:
        return False, f"无效的图片文件: {e}"


def batch_validate_images(
    image_paths: List[Path],
    max_size_mb: int = 10,
) -> Tuple[List[Path], List[Tuple[Path, str]]]:
    """批量验证图片文件.

    Args:
        image_paths: 图片路径列表
        max_size_mb: 最大文件大小（MB）

    Returns:
        (有效文件列表, 无效文件及原因列表)
    """
    valid_files = []
    invalid_files = []

    for path in image_paths:
        is_valid, error_msg = validate_image_file(path, max_size_mb)
        if is_valid:
            valid_files.append(path)
        else:
            invalid_files.append((path, error_msg))

    return valid_files, invalid_files


def format_confidence(confidence: float, precision: int = 2) -> str:
    """格式化置信度为百分比字符串.

    Args:
        confidence: 置信度（0-1）
        precision: 小数位数

    Returns:
        格式化的百分比字符串
    """
    return f"{confidence * 100:.{precision}f}%"


def estimate_processing_time(image_count: int, avg_time_per_image: float = 3.0) -> str:
    """估算批量处理时间.

    Args:
        image_count: 图片数量
        avg_time_per_image: 每张图片平均处理时间（秒）

    Returns:
        格式化的时间字符串
    """
    total_seconds = image_count * avg_time_per_image

    if total_seconds < 60:
        return f"{total_seconds:.0f} 秒"
    elif total_seconds < 3600:
        minutes = total_seconds / 60
        return f"{minutes:.1f} 分钟"
    else:
        hours = total_seconds / 3600
        return f"{hours:.1f} 小时"
