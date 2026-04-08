"""史记数据集批量OCR处理脚本.

使用LLM从版本目录名称中提取结构化元数据，包括：
- 版本类型（A/B/C/D/E）
- 注释体系
- 刻印信息（朝代、刻印者）
- 收藏机构与编目号
- 著者与注疏者
- 配本及跋文信息
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from ocr import KandiangujiOCRClient, OCROutputManager, OCRResult

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('shiji_ocr_process.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ─── 数据模型 ──────────────────────────────────────────────────────────────────

@dataclass
class PrintingInfo:
    """刻印信息."""
    dynasty_period: Optional[str] = None  # 刻印朝代
    printer: Optional[str] = None         # 刻印者/书坊名称


@dataclass
class EditionMetadata:
    """版本级元数据（一个版本目录对应一条记录）."""

    edition_dir: str                             # 版本目录名
    version_type: str                            # A/B/C/D/E
    annotation_system: Optional[str] = None      # 集解 | 集解+索隐 | 三家注
    printing_info: PrintingInfo = field(default_factory=PrintingInfo)
    total_juan: Optional[int] = None             # 全书总卷数
    extant_juan: Optional[str] = None            # 现存卷数说明
    holding_institution: Optional[str] = None    # 收藏机构
    catalog_id_main: Optional[str] = None        # 主编目号
    catalog_id_secondary: Optional[str] = None   # 副编目号
    authors: List[str] = field(default_factory=list)      # 原作者列表
    annotators: List[str] = field(default_factory=list)   # 注疏者列表
    peiben_notes: Optional[str] = None           # 配本说明
    colophon_authors: Optional[str] = None       # 跋文作者
    image_files: List[str] = field(default_factory=list)  # 图片文件路径列表

    def to_dict(self) -> Dict:
        return asdict(self)


# ─── LLM 元数据提取器 ──────────────────────────────────────────────────────────

class LLMMetadataExtractor:
    """使用LLM从版本目录名称中提取结构化元数据."""

    SYSTEM_PROMPT = (
        "你是一名古籍文献专家，熟悉《史记》各版本的注释体系、刻印历史和收藏信息。"
        "请严格按照用户要求，仅输出JSON格式的结构化数据，不要添加任何解释文字。"
    )

    USER_PROMPT_TEMPLATE = """\
请从以下史记版本目录名称中提取结构化元数据，以JSON格式返回。

目录名称：{edition_dir}

请提取以下字段（无法确定时填 null）：
{{
  "version_type": "版本标识字母，A/B/C/D/E 之一",
  "annotation_system": "注释体系，可选值：集解 | 集解+索隐 | 三家注 | null",
  "printing_info": {{
    "dynasty_period": "刻印朝代，如宋、元、明、清等",
    "printer": "刻印者或书坊名称"
  }},
  "total_juan": 130,
  "extant_juan": "现存卷数说明，如存卷一至卷三十，或null",
  "holding_institution": "收藏机构名称",
  "catalog_id_main": "主编目号",
  "catalog_id_secondary": "副编目号",
  "authors": ["原作者，如司马迁"],
  "annotators": ["注疏者列表，如裴骃、司马贞、张守节"],
  "peiben_notes": "配本说明",
  "colophon_authors": "跋文作者"
}}

只返回 JSON，不要其他文字。"""

    def __init__(self, client: OpenAI, model: str = "ernie-4.5-turbo-vl"):
        self.client = client
        self.model = model
        self._cache: Dict[str, EditionMetadata] = {}

    def extract(self, edition_dir: str, image_files: List[str]) -> EditionMetadata:
        """提取版本元数据，相同目录名命中缓存直接返回.

        Args:
            edition_dir: 版本目录名（不含父路径）
            image_files: 该版本下的图片文件路径列表

        Returns:
            EditionMetadata 对象
        """
        if edition_dir in self._cache:
            logger.debug(f"命中缓存: {edition_dir}")
            meta = self._cache[edition_dir]
            meta.image_files = list(image_files)
            return meta

        logger.info(f"LLM 提取元数据: {edition_dir}")
        try:
            raw = self._call_llm(edition_dir)
            meta = self._parse_response(raw, edition_dir)
        except Exception as e:
            logger.warning(f"LLM 提取失败，使用兜底值: {e}")
            meta = self._fallback_metadata(edition_dir)

        meta.image_files = list(image_files)
        self._cache[edition_dir] = meta
        return meta

    def _call_llm(self, edition_dir: str) -> str:
        prompt = self.USER_PROMPT_TEMPLATE.format(edition_dir=edition_dir)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return response.choices[0].message.content.strip()

    def _parse_response(self, raw: str, edition_dir: str) -> EditionMetadata:
        """解析 LLM 返回的 JSON，去除可能包裹的 markdown 代码块."""
        text = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        data = json.loads(text.strip())

        printing_raw = data.get('printing_info') or {}
        printing_info = PrintingInfo(
            dynasty_period=printing_raw.get('dynasty_period'),
            printer=printing_raw.get('printer'),
        )

        return EditionMetadata(
            edition_dir=edition_dir,
            version_type=str(data.get('version_type') or ''),
            annotation_system=data.get('annotation_system'),
            printing_info=printing_info,
            total_juan=data.get('total_juan'),
            extant_juan=data.get('extant_juan'),
            holding_institution=data.get('holding_institution'),
            catalog_id_main=data.get('catalog_id_main'),
            catalog_id_secondary=data.get('catalog_id_secondary'),
            authors=data.get('authors') or [],
            annotators=data.get('annotators') or [],
            peiben_notes=data.get('peiben_notes'),
            colophon_authors=data.get('colophon_authors'),
        )

    @staticmethod
    def _fallback_metadata(edition_dir: str) -> EditionMetadata:
        """LLM 失败时的兜底：仅用正则提取版本字母."""
        m = re.match(r'^([A-E])', edition_dir)
        return EditionMetadata(
            edition_dir=edition_dir,
            version_type=m.group(1) if m else '',
        )


# ─── 数据集处理器 ──────────────────────────────────────────────────────────────

class ShijiDatasetProcessor:
    """史记数据集处理器."""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        ocr_client: Optional[KandiangujiOCRClient] = None,
        llm_client: Optional[OpenAI] = None,
        llm_model: str = "ernie-4.5-turbo-vl",
    ):
        """初始化处理器.

        Args:
            data_dir: 数据集根目录
            output_dir: 输出目录
            ocr_client: OCR客户端（可选，默认自动创建）
            llm_client: OpenAI兼容客户端（可选，默认从环境变量创建）
            llm_model: LLM模型名称
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.ocr_client = ocr_client or KandiangujiOCRClient()
        self.output_mgr = OCROutputManager(output_dir)

        llm = llm_client or OpenAI(
            api_key=os.environ['OPENAI_API_KEY'],
            base_url=os.getenv('OPENAI_BASE_URL', 'https://aistudio.baidu.com/llm/lmapi/v3'),
        )
        self.extractor = LLMMetadataExtractor(llm, model=llm_model)

        self.stats = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}

    # ── 图片发现与分组 ──────────────────────────────────────────────────────────

    def find_images(self, extensions: List[str] = None) -> List[Path]:
        """查找所有图片文件."""
        if extensions is None:
            extensions = ['.jpg', '.jpeg', '.png', '.tif', '.tiff']
        images = []
        for ext in extensions:
            images.extend(self.data_dir.rglob(f'*{ext}'))
            images.extend(self.data_dir.rglob(f'*{ext.upper()}'))
        return sorted(images)

    def group_by_edition(self, images: List[Path]) -> Dict[str, List[Path]]:
        """将图片按版本目录分组（data_dir 下的 parts[1]/parts[2]，保留版本字母和书目详情）."""
        groups: Dict[str, List[Path]] = {}
        for img in images:
            try:
                rel = img.relative_to(self.data_dir)
                # parts[0]: 数据集根目录（如"名录 史记2025-11-6"），跳过
                # parts[1]: 版本字母目录（如"A史记 集解本 1北宋刻本"）
                # parts[2]: 具体书目目录（如"【1】00393 史记..."）
                if len(rel.parts) >= 3:
                    edition_dir = f"{rel.parts[1]}/{rel.parts[2]}"
                elif len(rel.parts) >= 2:
                    edition_dir = rel.parts[1]
                else:
                    edition_dir = rel.parts[0]
            except (ValueError, IndexError):
                edition_dir = img.parent.name
            groups.setdefault(edition_dir, []).append(img)
        return groups

    # ── 核心处理逻辑 ────────────────────────────────────────────────────────────

    def process_image(
        self,
        image_path: Path,
        metadata: EditionMetadata,
        skip_existing: bool = True,
    ) -> bool:
        """处理单张图片：OCR识别并保存结果.

        Args:
            image_path: 图片路径
            metadata: 所属版本的元数据
            skip_existing: 是否跳过已处理的图片

        Returns:
            是否处理成功
        """
        try:
            rel_path = image_path.relative_to(self.data_dir)
            output_name = str(rel_path).replace('/', '_').replace('\\', '_')
            output_name = Path(output_name).stem

            output_json = self.output_dir / output_name / f"{output_name}.json"
            if skip_existing and output_json.exists():
                logger.info(f"跳过已处理: {image_path.name}")
                self.stats['skipped'] += 1
                return True

            logger.info(f"处理图片: {image_path.name}")

            result = self.ocr_client.recognize_image(image_path)
            self.output_mgr.save_all(image_path, result, image_name=output_name)

            extended_path = self.output_dir / output_name / "extended_metadata.json"
            self._save_extended_metadata(extended_path, image_path, metadata, result)

            logger.info(
                f"  识别行数: {result.get_text_count()}, "
                f"平均置信度: {result.get_average_confidence():.2%}"
            )
            self.stats['success'] += 1
            return True

        except Exception as e:
            logger.error(f"处理失败 {image_path.name}: {e}", exc_info=True)
            self.stats['failed'] += 1
            return False

    def _save_extended_metadata(
        self,
        output_path: Path,
        image_path: Path,
        edition_meta: EditionMetadata,
        ocr_result: OCRResult,
    ):
        """保存扩展元数据（版本信息 + OCR统计）."""
        data = {
            'edition_metadata': edition_meta.to_dict(),
            'image_file': str(image_path),
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    # ── 批处理入口 ──────────────────────────────────────────────────────────────

    def process_all(self, skip_existing: bool = True, max_images: Optional[int] = None):
        """批量处理所有图片."""
        images = self.find_images()
        if max_images:
            images = images[:max_images]
            logger.info(f"限制处理数量: {max_images}")

        self.stats['total'] = len(images)
        logger.info(f"准备处理 {len(images)} 张图片")

        groups = self.group_by_edition(images)
        for edition_dir, edition_images in groups.items():
            image_strs = [str(p) for p in edition_images]
            metadata = self.extractor.extract(edition_dir, image_strs)
            logger.info(
                f"版本 {metadata.version_type} [{edition_dir}]: "
                f"注释={metadata.annotation_system}, "
                f"朝代={metadata.printing_info.dynasty_period}, "
                f"注疏者={metadata.annotators}"
            )
            for idx, img in enumerate(edition_images, 1):
                logger.info(f"  [{idx}/{len(edition_images)}] {img.name}")
                self.process_image(img, metadata, skip_existing=skip_existing)

        self._print_summary()

    def process_by_version(self, version_type: str, skip_existing: bool = True):
        """按版本类型处理图片（通过目录名首字母快速过滤，无需调用LLM）."""
        all_images = self.find_images()
        filtered = [img for img in all_images if self._quick_version(img) == version_type]
        logger.info(f"版本 {version_type} 图片: {len(filtered)} 张")
        self.stats['total'] = len(filtered)

        groups = self.group_by_edition(filtered)
        for edition_dir, edition_images in groups.items():
            image_strs = [str(p) for p in edition_images]
            metadata = self.extractor.extract(edition_dir, image_strs)
            for img in edition_images:
                self.process_image(img, metadata, skip_existing=skip_existing)

        self._print_summary()

    def _quick_version(self, image_path: Path) -> str:
        """从路径版本字母目录名快速提取版本字母（无需调用LLM）."""
        try:
            rel = image_path.relative_to(self.data_dir)
            # parts[0] 是数据集根目录，parts[1] 才是版本字母目录
            part = rel.parts[1] if len(rel.parts) >= 2 else rel.parts[0]
            m = re.match(r'^([A-E])', part)
            return m.group(1) if m else ''
        except (ValueError, IndexError):
            return ''

    def _print_summary(self):
        logger.info("\n" + "=" * 60)
        logger.info("处理完成统计:")
        logger.info(f"  总数: {self.stats['total']}")
        logger.info(f"  成功: {self.stats['success']}")
        logger.info(f"  失败: {self.stats['failed']}")
        logger.info(f"  跳过: {self.stats['skipped']}")
        if self.stats['total'] > 0:
            logger.info(f"  成功率: {self.stats['success'] / self.stats['total'] * 100:.1f}%")
        logger.info("=" * 60)

    def export_metadata_index(self, output_file: Path):
        """导出所有版本的元数据索引（每个版本目录一条记录）."""
        images = self.find_images()
        groups = self.group_by_edition(images)
        index = []

        logger.info("正在生成元数据索引...")
        for edition_dir, edition_images in groups.items():
            image_strs = [str(p) for p in edition_images]
            metadata = self.extractor.extract(edition_dir, image_strs)
            index.append(metadata.to_dict())

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        logger.info(f"元数据索引已保存到: {output_file}")
        logger.info(f"共 {len(index)} 条版本记录")


# ─── 命令行入口 ────────────────────────────────────────────────────────────────

def main():
    import argparse

    arg_parser = argparse.ArgumentParser(
        description='史记数据集批量OCR处理工具（LLM元数据提取版）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 处理所有图片
  python process_shiji_dataset.py --data data --output outputs

  # 只处理前10张（测试）
  python process_shiji_dataset.py --data data --output outputs --max 10

  # 按版本处理
  python process_shiji_dataset.py --data data --output outputs --version A

  # 导出元数据索引（仅调用LLM，不做OCR）
  python process_shiji_dataset.py --data data --export-index metadata_index.json

  # 强制重新处理（不跳过已存在的）
  python process_shiji_dataset.py --data data --output outputs --no-skip

  # 指定LLM模型
  python process_shiji_dataset.py --data data --output outputs --model ernie-4.5-turbo-vl
        """
    )
    arg_parser.add_argument('--data', type=Path, default=Path('data'), help='数据集根目录（默认: data）')
    arg_parser.add_argument('--output', type=Path, default=Path('outputs'), help='输出目录（默认: outputs）')
    arg_parser.add_argument('--max', type=int, help='最大处理数量（用于测试）')
    arg_parser.add_argument('--version', choices=['A', 'B', 'C', 'D', 'E'], help='只处理指定版本类型')
    arg_parser.add_argument('--no-skip', action='store_true', help='不跳过已处理的图片，强制重新处理')
    arg_parser.add_argument('--export-index', type=Path, help='导出元数据索引到指定文件')
    arg_parser.add_argument('--model', default='ernie-4.5-turbo-vl', help='LLM模型名称（默认: ernie-4.5-turbo-vl）')

    args = arg_parser.parse_args()

    processor = ShijiDatasetProcessor(
        data_dir=args.data,
        output_dir=args.output,
        llm_model=args.model,
    )

    if args.export_index:
        processor.export_metadata_index(args.export_index)
        # return

    skip_existing = not args.no_skip
    if args.version:
        processor.process_by_version(version_type=args.version, skip_existing=skip_existing)
    else:
        processor.process_all(skip_existing=skip_existing, max_images=args.max)


if __name__ == '__main__':
    main()
