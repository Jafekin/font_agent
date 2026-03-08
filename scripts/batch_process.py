#!/usr/bin/env python3
"""批量处理脚本 - 分批处理大量图片，支持断点续传."""

import time
from pathlib import Path
from process_shiji_dataset import ShijiDatasetProcessor
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def batch_process_with_retry(
    data_dir: Path = Path("data"),
    output_dir: Path = Path("outputs"),
    batch_size: int = 50,
    delay_between_batches: float = 5.0,
):
    """分批处理，支持断点续传.

    Args:
        data_dir: 数据目录
        output_dir: 输出目录
        batch_size: 每批处理的图片数量
        delay_between_batches: 批次间延迟（秒）
    """
    processor = ShijiDatasetProcessor(
        data_dir=data_dir,
        output_dir=output_dir,
    )

    # 获取所有图片
    all_images = processor.find_images()
    total = len(all_images)

    logger.info(f"共找到 {total} 张图片")

    # 分批处理
    for batch_idx in range(0, total, batch_size):
        batch_end = min(batch_idx + batch_size, total)
        batch_images = all_images[batch_idx:batch_end]

        logger.info(f"\n{'='*60}")
        logger.info(f"处理批次 {batch_idx//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
        logger.info(f"图片范围: {batch_idx + 1} - {batch_end} / {total}")
        logger.info(f"{'='*60}\n")

        # 处理当前批次
        batch_stats = {'success': 0, 'failed': 0, 'skipped': 0}

        for idx, image_path in enumerate(batch_images, 1):
            logger.info(f"[批次内进度 {idx}/{len(batch_images)}] {image_path.name}")

            try:
                success = processor.process_image(image_path, skip_existing=True)
                if success:
                    # 检查是否跳过
                    if processor.stats['skipped'] > batch_stats['skipped']:
                        batch_stats['skipped'] += 1
                    else:
                        batch_stats['success'] += 1
                else:
                    batch_stats['failed'] += 1
            except Exception as e:
                logger.error(f"处理失败: {e}")
                batch_stats['failed'] += 1

        # 批次统计
        logger.info(f"\n批次统计: 成功={batch_stats['success']}, 失败={batch_stats['failed']}, 跳过={batch_stats['skipped']}")

        # 批次间延迟
        if batch_end < total:
            logger.info(f"等待 {delay_between_batches} 秒后继续下一批次...")
            time.sleep(delay_between_batches)

    # 最终统计
    processor._print_summary()


def process_by_version_batch(
    version_type: str,
    data_dir: Path = Path("data"),
    output_dir: Path = Path("outputs"),
):
    """按版本分批处理.

    Args:
        version_type: 版本类型 (A/B/C/D/E)
        data_dir: 数据目录
        output_dir: 输出目录
    """
    logger.info(f"开始处理 {version_type} 版本")

    processor = ShijiDatasetProcessor(
        data_dir=data_dir,
        output_dir=output_dir / f"version_{version_type}",
    )

    processor.process_by_version(
        version_type=version_type,
        skip_existing=True,
    )


def process_all_versions_separately():
    """分别处理各个版本."""
    versions = ['A', 'B', 'C', 'D', 'E']

    for version in versions:
        logger.info(f"\n{'='*60}")
        logger.info(f"开始处理版本: {version}")
        logger.info(f"{'='*60}\n")

        process_by_version_batch(
            version_type=version,
            data_dir=Path("data"),
            output_dir=Path("outputs"),
        )

        logger.info(f"\n版本 {version} 处理完成\n")
        time.sleep(3)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='批量处理史记数据集')
    parser.add_argument('--mode', choices=['batch', 'version', 'all-versions'],
                        default='batch', help='处理模式')
    parser.add_argument('--version', choices=['A', 'B', 'C', 'D', 'E'],
                        help='指定版本（仅在version模式下使用）')
    parser.add_argument('--batch-size', type=int, default=50,
                        help='每批处理数量（默认50）')
    parser.add_argument('--delay', type=float, default=5.0,
                        help='批次间延迟秒数（默认5.0）')
    parser.add_argument('--data', type=Path, default=Path('../data'),
                        help='数据目录')
    parser.add_argument('--output', type=Path, default=Path('../outputs'),
                        help='输出目录')

    args = parser.parse_args()

    if args.mode == 'batch':
        batch_process_with_retry(
            data_dir=args.data,
            output_dir=args.output,
            batch_size=args.batch_size,
            delay_between_batches=args.delay,
        )
    elif args.mode == 'version':
        if not args.version:
            parser.error("--version 参数在 version 模式下是必需的")
        process_by_version_batch(
            version_type=args.version,
            data_dir=args.data,
            output_dir=args.output,
        )
    elif args.mode == 'all-versions':
        process_all_versions_separately()
