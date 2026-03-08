"""史记数据集批量OCR处理脚本.

从文件路径中提取元数据信息，包括：
- 版本类型（A/B/C/D/E）
- 刻本信息
- 卷数
- 页码
- 图书馆信息
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from ocr import KandiangujiOCRClient, OCROutputManager, OCRResult


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('shiji_ocr_process.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ImageMetadata:
    """图片元数据信息."""

    file_path: str
    version_type: str  # A/B/C/D/E
    edition_info: str  # 刻本信息
    volume: Optional[str] = None  # 卷数
    page: Optional[str] = None  # 页码
    library: Optional[str] = None  # 图书馆
    catalog_number: Optional[str] = None  # 编目号

    def to_dict(self) -> Dict:
        """转换为字典."""
        return asdict(self)


class ShijiPathParser:
    """史记数据集路径解析器."""

    # 版本类型正则
    VERSION_PATTERN = r'^([A-E])史记'

    # 卷数正则（支持多种格式）
    VOLUME_PATTERNS = [
        r'卷([一二三四五六七八九十百零〇]+)',
        r'卷(\d+)',
        r'·卷([一二三四五六七八九十百零〇]+)',
        r'·卷(\d+)',
    ]

    # 页码正则
    PAGE_PATTERNS = [
        r'[pP](\d+[ab]?)',
        r'页(\d+)',
    ]

    # 图书馆正则
    LIBRARY_PATTERN = r'([\u4e00-\u9fa5]+图书馆)'

    # 编目号正则
    CATALOG_PATTERN = r'【(\d+)】\s*(\d+)'

    def parse_path(self, image_path: Path) -> ImageMetadata:
        """解析图片路径，提取元数据.

        Args:
            image_path: 图片文件路径

        Returns:
            图片元数据对象
        """
        path_str = str(image_path)
        parts = image_path.parts

        # 提取版本类型和刻本信息
        version_type = ""
        edition_info = ""

        for part in parts:
            # 匹配版本类型
            version_match = re.search(self.VERSION_PATTERN, part)
            if version_match:
                version_type = version_match.group(1)
                edition_info = part
                break

        # 提取卷数
        volume = self._extract_volume(image_path.name)

        # 提取页码
        page = self._extract_page(image_path.name)

        # 提取图书馆
        library = self._extract_library(path_str)

        # 提取编目号
        catalog_number = self._extract_catalog(path_str)

        return ImageMetadata(
            file_path=str(image_path),
            version_type=version_type,
            edition_info=edition_info,
            volume=volume,
            page=page,
            library=library,
            catalog_number=catalog_number,
        )

    def _extract_volume(self, filename: str) -> Optional[str]:
        """提取卷数."""
        for pattern in self.VOLUME_PATTERNS:
            match = re.search(pattern, filename)
            if match:
                return match.group(1)
        return None

    def _extract_page(self, filename: str) -> Optional[str]:
        """提取页码."""
        for pattern in self.PAGE_PATTERNS:
            match = re.search(pattern, filename)
            if match:
                return match.group(1)
        return None

    def _extract_library(self, path_str: str) -> Optional[str]:
        """提取图书馆信息."""
        match = re.search(self.LIBRARY_PATTERN, path_str)
        return match.group(1) if match else None

    def _extract_catalog(self, path_str: str) -> Optional[str]:
        """提取编目号."""
        match = re.search(self.CATALOG_PATTERN, path_str)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        return None


class ShijiDatasetProcessor:
    """史记数据集处理器."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        client: Optional[KandiangujiOCRClient] = None,
    ):
        """初始化处理器.

        Args:
            data_dir: 数据集根目录
            output_dir: 输出目录
            client: OCR客户端（可选）
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.client = client or KandiangujiOCRClient()
        self.output_mgr = OCROutputManager(output_dir)
        self.parser = ShijiPathParser()

        # 统计信息
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
        }

    def find_images(self, extensions: List[str] = None) -> List[Path]:
        """查找所有图片文件.

        Args:
            extensions: 图片扩展名列表

        Returns:
            图片路径列表
        """
        if extensions is None:
            extensions = ['.jpg', '.jpeg', '.png', '.tif', '.tiff']

        images = []
        for ext in extensions:
            images.extend(self.data_dir.rglob(f'*{ext}'))
            images.extend(self.data_dir.rglob(f'*{ext.upper()}'))

        return sorted(images)

    def process_image(
        self,
        image_path: Path,
        skip_existing: bool = True,
    ) -> bool:
        """处理单张图片.

        Args:
            image_path: 图片路径
            skip_existing: 是否跳过已处理的图片

        Returns:
            是否处理成功
        """
        try:
            # 解析路径元数据
            metadata = self.parser.parse_path(image_path)

            # 生成输出名称（使用相对路径避免重名）
            rel_path = image_path.relative_to(self.data_dir)
            output_name = str(rel_path).replace('/', '_').replace('\\', '_')
            output_name = Path(output_name).stem

            # 检查是否已处理
            output_json = self.output_dir / output_name / f"{output_name}.json"
            if skip_existing and output_json.exists():
                logger.info(f"跳过已处理: {image_path.name}")
                self.stats['skipped'] += 1
                return True

            logger.info(f"处理图片: {image_path.name}")
            logger.info(f"  版本: {metadata.version_type}, 卷: {metadata.volume}, 页: {metadata.page}")

            # OCR识别
            result = self.client.recognize_image(image_path)

            # 保存结果
            saved_files = self.output_mgr.save_all(
                image_path,
                result,
                image_name=output_name,
            )

            # 保存扩展元数据
            extended_metadata_path = self.output_dir / output_name / "extended_metadata.json"
            self._save_extended_metadata(
                extended_metadata_path,
                metadata,
                result,
            )

            logger.info(f"  识别行数: {result.get_text_count()}")
            logger.info(f"  平均置信度: {result.get_average_confidence():.2%}")
            logger.info(f"  输出目录: {self.output_dir / output_name}")

            self.stats['success'] += 1
            return True

        except Exception as e:
            logger.error(f"处理失败 {image_path.name}: {e}", exc_info=True)
            self.stats['failed'] += 1
            return False

    def _save_extended_metadata(
        self,
        output_path: Path,
        image_metadata: ImageMetadata,
        ocr_result: OCRResult,
    ):
        """保存扩展元数据（包含路径解析信息）.

        Args:
            output_path: 输出路径
            image_metadata: 图片元数据
            ocr_result: OCR结果
        """
        data = {
            'image_metadata': image_metadata.to_dict(),
            'ocr_statistics': {
                'line_count': ocr_result.get_text_count(),
                'average_confidence': ocr_result.get_average_confidence(),
                'is_vertical': ocr_result.is_vertical_text(),
                'image_size': {
                    'width': ocr_result.width,
                    'height': ocr_result.height,
                },
            },
        }

        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def process_all(
        self,
        skip_existing: bool = True,
        max_images: Optional[int] = None,
    ):
        """批量处理所有图片.

        Args:
            skip_existing: 是否跳过已处理的图片
            max_images: 最大处理数量（用于测试）
        """
        images = self.find_images()
        total = len(images)

        if max_images:
            images = images[:max_images]
            logger.info(f"限制处理数量: {max_images}")

        logger.info(f"找到 {total} 张图片，准备处理 {len(images)} 张")

        self.stats['total'] = len(images)

        for idx, image_path in enumerate(images, 1):
            logger.info(f"\n[{idx}/{len(images)}] 处理进度: {idx/len(images)*100:.1f}%")
            self.process_image(image_path, skip_existing=skip_existing)

        # 输出统计信息
        self._print_summary()

    def process_by_version(
        self,
        version_type: str,
        skip_existing: bool = True,
    ):
        """按版本类型处理图片.

        Args:
            version_type: 版本类型（A/B/C/D/E）
            skip_existing: 是否跳过已处理的图片
        """
        all_images = self.find_images()
        filtered_images = []

        for img in all_images:
            metadata = self.parser.parse_path(img)
            if metadata.version_type == version_type:
                filtered_images.append(img)

        logger.info(f"找到版本 {version_type} 的图片: {len(filtered_images)} 张")

        self.stats['total'] = len(filtered_images)

        for idx, image_path in enumerate(filtered_images, 1):
            logger.info(f"\n[{idx}/{len(filtered_images)}] 处理进度: {idx/len(filtered_images)*100:.1f}%")
            self.process_image(image_path, skip_existing=skip_existing)

        self._print_summary()

    def _print_summary(self):
        """打印处理统计信息."""
        logger.info("\n" + "="*60)
        logger.info("处理完成统计:")
        logger.info(f"  总数: {self.stats['total']}")
        logger.info(f"  成功: {self.stats['success']}")
        logger.info(f"  失败: {self.stats['failed']}")
        logger.info(f"  跳过: {self.stats['skipped']}")
        logger.info(f"  成功率: {self.stats['success']/self.stats['total']*100:.1f}%" if self.stats['total'] > 0 else "  成功率: N/A")
        logger.info("="*60)

    def export_metadata_index(self, output_file: Path):
        """导出所有图片的元数据索引.

        Args:
            output_file: 输出文件路径
        """
        images = self.find_images()
        index = []

        logger.info(f"正在生成元数据索引...")

        for image_path in images:
            metadata = self.parser.parse_path(image_path)
            index.append(metadata.to_dict())

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        logger.info(f"元数据索引已保存到: {output_file}")
        logger.info(f"共 {len(index)} 条记录")


def main():
    """主函数 - 命令行入口."""
    import argparse

    parser = argparse.ArgumentParser(
        description='史记数据集批量OCR处理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 处理所有图片
  python process_shiji_dataset.py --data data --output outputs

  # 只处理前10张（测试）
  python process_shiji_dataset.py --data data --output outputs --max 10

  # 按版本处理
  python process_shiji_dataset.py --data data --output outputs --version A

  # 导出元数据索引
  python process_shiji_dataset.py --data data --export-index metadata_index.json

  # 强制重新处理（不跳过已存在的）
  python process_shiji_dataset.py --data data --output outputs --no-skip
        """
    )

    parser.add_argument(
        '--data',
        type=Path,
        default=Path('data'),
        help='数据集根目录（默认: data）'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('outputs'),
        help='输出目录（默认: outputs）'
    )
    parser.add_argument(
        '--max',
        type=int,
        help='最大处理数量（用于测试）'
    )
    parser.add_argument(
        '--version',
        choices=['A', 'B', 'C', 'D', 'E'],
        help='只处理指定版本类型'
    )
    parser.add_argument(
        '--no-skip',
        action='store_true',
        help='不跳过已处理的图片，强制重新处理'
    )
    parser.add_argument(
        '--export-index',
        type=Path,
        help='导出元数据索引到指定文件'
    )

    args = parser.parse_args()

    # 创建处理器
    processor = ShijiDatasetProcessor(
        data_dir=args.data,
        output_dir=args.output,
    )

    # 导出索引模式
    if args.export_index:
        processor.export_metadata_index(args.export_index)
        return

    # 处理图片
    skip_existing = not args.no_skip

    if args.version:
        processor.process_by_version(
            version_type=args.version,
            skip_existing=skip_existing,
        )
    else:
        processor.process_all(
            skip_existing=skip_existing,
            max_images=args.max,
        )


if __name__ == '__main__':
    main()
