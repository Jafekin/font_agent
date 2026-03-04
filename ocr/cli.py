#!/usr/bin/env python3
"""OCR 命令行工具.

使用示例：
    # 识别单张图片
    python -m ocr.cli recognize test.jpg

    # 识别并保存所有格式
    python -m ocr.cli recognize test.jpg --save-all

    # 批量识别
    python -m ocr.cli batch images/*.jpg --output-dir outputs

    # 查询 Token 状态
    python -m ocr.cli status
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List

from .client import KandiangujiOCRClient
from .config import OCRConfig
from .output import OCROutputManager
from .utils import batch_validate_images, estimate_processing_time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_recognize(args):
    """识别单张图片."""
    image_path = Path(args.image)

    if not image_path.exists():
        logger.error(f"图片不存在: {image_path}")
        return 1

    try:
        # 初始化客户端
        config = OCRConfig(
            token=args.token,
            email=args.email,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        client = KandiangujiOCRClient(config)

        logger.info(f"正在识别: {image_path}")
        result = client.recognize_image(image_path)

        # 输出基本信息
        print(f"\n识别完成:")
        print(f"  文本行数: {result.get_text_count()}")
        print(f"  平均置信度: {result.get_average_confidence():.2%}")
        print(f"  文本方向: {'竖排' if result.is_vertical_text() else '横排'}")

        # 保存结果
        if args.save_all:
            output_mgr = OCROutputManager(config.get_output_dir())
            saved_files = output_mgr.save_all(image_path, result)
            print(f"\n已保存到:")
            for file_type, file_path in saved_files.items():
                print(f"  {file_type}: {file_path}")
        elif args.output:
            output_path = Path(args.output)
            if args.format == "json":
                output_mgr = OCROutputManager(output_path.parent)
                output_mgr.save_json(result, output_path)
            elif args.format == "txt":
                output_mgr = OCROutputManager(output_path.parent)
                output_mgr.save_text(result, output_path)
            print(f"\n已保存到: {output_path}")
        else:
            # 直接输出文本
            print(f"\n识别文本:")
            print("-" * 50)
            print(result.get_full_text())
            print("-" * 50)

        return 0

    except Exception as e:
        logger.error(f"识别失败: {e}", exc_info=True)
        return 1


def cmd_batch(args):
    """批量识别图片."""
    image_paths = [Path(p) for p in args.images]

    # 验证文件
    valid_files, invalid_files = batch_validate_images(image_paths)

    if invalid_files:
        logger.warning(f"发现 {len(invalid_files)} 个无效文件:")
        for path, reason in invalid_files:
            logger.warning(f"  {path}: {reason}")

    if not valid_files:
        logger.error("没有有效的图片文件")
        return 1

    logger.info(f"准备处理 {len(valid_files)} 张图片")
    logger.info(f"预计耗时: {estimate_processing_time(len(valid_files))}")

    try:
        # 初始化
        config = OCRConfig(
            token=args.token,
            email=args.email,
            output_dir=Path(args.output_dir),
        )
        client = KandiangujiOCRClient(config)
        output_mgr = OCROutputManager(config.get_output_dir())

        # 批量处理
        success_count = 0
        failed_files = []

        for i, image_path in enumerate(valid_files, 1):
            try:
                logger.info(f"[{i}/{len(valid_files)}] 处理: {image_path.name}")
                result = client.recognize_image(image_path)
                output_mgr.save_all(image_path, result)
                success_count += 1

            except Exception as e:
                logger.error(f"处理失败 {image_path.name}: {e}")
                failed_files.append((image_path, str(e)))

        # 输出统计
        print(f"\n批量处理完成:")
        print(f"  成功: {success_count}/{len(valid_files)}")
        print(f"  失败: {len(failed_files)}")

        if failed_files:
            print(f"\n失败文件:")
            for path, reason in failed_files:
                print(f"  {path.name}: {reason}")

        return 0 if success_count > 0 else 1

    except Exception as e:
        logger.error(f"批量处理失败: {e}", exc_info=True)
        return 1


def cmd_status(args):
    """查询 Token 状态."""
    try:
        config = OCRConfig(token=args.token, email=args.email)
        client = KandiangujiOCRClient(config)

        status = client.get_token_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        logger.error(f"查询失败: {e}", exc_info=True)
        return 1


def main():
    """主函数."""
    parser = argparse.ArgumentParser(
        description="看典古籍 OCR 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 全局参数
    parser.add_argument(
        "--token",
        default=None,
        help="API Token（默认从环境变量 KANDIANGUJI_TOKEN 读取）",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="API Email（默认从环境变量 KANDIANGUJI_EMAIL 读取）",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # recognize 命令
    recognize_parser = subparsers.add_parser("recognize", help="识别单张图片")
    recognize_parser.add_argument("image", help="图片路径")
    recognize_parser.add_argument(
        "-o", "--output", help="输出文件路径"
    )
    recognize_parser.add_argument(
        "-f",
        "--format",
        choices=["json", "txt"],
        default="txt",
        help="输出格式",
    )
    recognize_parser.add_argument(
        "--save-all",
        action="store_true",
        help="保存所有格式（JSON、TXT、标注图片）",
    )
    recognize_parser.add_argument(
        "--output-dir",
        default="ocr/outputs",
        help="输出目录（用于 --save-all）",
    )

    # batch 命令
    batch_parser = subparsers.add_parser("batch", help="批量识别图片")
    batch_parser.add_argument("images", nargs="+", help="图片路径列表")
    batch_parser.add_argument(
        "--output-dir",
        default="ocr/outputs",
        help="输出目录",
    )

    # status 命令
    subparsers.add_parser("status", help="查询 Token 状态")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 执行命令
    if args.command == "recognize":
        return cmd_recognize(args)
    elif args.command == "batch":
        return cmd_batch(args)
    elif args.command == "status":
        return cmd_status(args)


if __name__ == "__main__":
    sys.exit(main())
