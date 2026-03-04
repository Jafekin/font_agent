"""OCR 模块 - 看典古籍 OCR API 客户端.

优化后的模块结构：
- client.py: API 客户端
- config.py: 配置管理
- models.py: 数据模型
- output.py: 输出管理
- exceptions.py: 异常定义
- utils.py: 工具函数

使用示例：

基础用法：
    from ocr import KandiangujiOCRClient, OCRConfig

    # 使用环境变量配置
    client = KandiangujiOCRClient()
    result = client.recognize_image("test.jpg")
    print(result.get_full_text())

自定义配置：
    config = OCRConfig(
        token="your-token",
        email="your-email",
        output_dir=Path("custom_output"),
    )
    client = KandiangujiOCRClient(config)

完整工作流：
    from ocr import KandiangujiOCRClient, OCROutputManager
    from pathlib import Path

    # 初始化
    client = KandiangujiOCRClient()
    output_mgr = OCROutputManager(Path("outputs"))

    # 识别图片
    image_path = Path("ancient_text.jpg")
    result = client.recognize_image(image_path)

    # 保存所有格式的输出
    saved_files = output_mgr.save_all(image_path, result)
    print(f"已保存: {saved_files}")

    # 查看统计信息
    print(f"识别行数: {result.get_text_count()}")
    print(f"平均置信度: {result.get_average_confidence():.2%}")
    print(f"是否竖排: {result.is_vertical_text()}")
"""

from .client import KandiangujiOCRClient, encode_image_to_base64
from .config import OCRConfig, get_default_config
from .exceptions import (
    OCRAPIError,
    OCRAuthError,
    OCRConfigError,
    OCRError,
    OCRFileError,
    OCRTimeoutError,
    OCRValidationError,
)
from .models import OCRResult, PDFTaskStatus, TextLine, WordInfo
from .output import OCROutputManager

__version__ = "2.0.0"

__all__ = [
    # 客户端
    "KandiangujiOCRClient",
    "encode_image_to_base64",
    # 配置
    "OCRConfig",
    "get_default_config",
    # 数据模型
    "OCRResult",
    "PDFTaskStatus",
    "TextLine",
    "WordInfo",
    # 输出管理
    "OCROutputManager",
    # 异常
    "OCRError",
    "OCRAPIError",
    "OCRAuthError",
    "OCRConfigError",
    "OCRFileError",
    "OCRTimeoutError",
    "OCRValidationError",
]
