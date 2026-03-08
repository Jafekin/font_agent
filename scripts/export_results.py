"""导出工具 - 将OCR结果导出为不同格式."""

import json
import csv
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class ExportRecord:
    """导出记录."""
    file_path: str
    version_type: str
    edition_info: str
    volume: str
    page: str
    library: str
    catalog_number: str
    line_count: int
    average_confidence: float
    is_vertical: bool
    text_content: str


class ShijiExporter:
    """史记数据集导出器."""

    def __init__(self, output_dir: Path):
        """初始化导出器.

        Args:
            output_dir: OCR输出目录
        """
        self.output_dir = Path(output_dir)

    def collect_all_data(self) -> List[ExportRecord]:
        """收集所有数据.

        Returns:
            导出记录列表
        """
        records = []

        for metadata_file in self.output_dir.rglob("extended_metadata.json"):
            try:
                # 读取元数据
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                # 读取文本内容
                text_file = metadata_file.parent / "text" / f"{metadata_file.parent.name}.txt"
                text_content = ""
                if text_file.exists():
                    with open(text_file, 'r', encoding='utf-8') as f:
                        text_content = f.read()

                # 创建记录
                img_meta = metadata.get('image_metadata', {})
                ocr_stats = metadata.get('ocr_statistics', {})

                record = ExportRecord(
                    file_path=img_meta.get('file_path', ''),
                    version_type=img_meta.get('version_type', ''),
                    edition_info=img_meta.get('edition_info', ''),
                    volume=img_meta.get('volume', ''),
                    page=img_meta.get('page', ''),
                    library=img_meta.get('library', ''),
                    catalog_number=img_meta.get('catalog_number', ''),
                    line_count=ocr_stats.get('line_count', 0),
                    average_confidence=ocr_stats.get('average_confidence', 0.0),
                    is_vertical=ocr_stats.get('is_vertical', False),
                    text_content=text_content,
                )

                records.append(record)

            except Exception as e:
                print(f"处理失败 {metadata_file}: {e}")

        return records

    def export_to_csv(self, output_file: Path, include_text: bool = False):
        """导出为CSV格式.

        Args:
            output_file: 输出文件路径
            include_text: 是否包含文本内容
        """
        records = self.collect_all_data()

        if not records:
            print("没有数据可导出")
            return

        output_file.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            'file_path', 'version_type', 'edition_info', 'volume', 'page',
            'library', 'catalog_number', 'line_count', 'average_confidence',
            'is_vertical'
        ]

        if include_text:
            fieldnames.append('text_content')

        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for record in records:
                row = {
                    'file_path': record.file_path,
                    'version_type': record.version_type,
                    'edition_info': record.edition_info,
                    'volume': record.volume or '',
                    'page': record.page or '',
                    'library': record.library or '',
                    'catalog_number': record.catalog_number or '',
                    'line_count': record.line_count,
                    'average_confidence': f"{record.average_confidence:.4f}",
                    'is_vertical': '是' if record.is_vertical else '否',
                }

                if include_text:
                    row['text_content'] = record.text_content

                writer.writerow(row)

        print(f"CSV已导出到: {output_file}")
        print(f"共 {len(records)} 条记录")

    def export_to_json(self, output_file: Path):
        """导出为JSON格式.

        Args:
            output_file: 输出文件路径
        """
        records = self.collect_all_data()

        if not records:
            print("没有数据可导出")
            return

        output_file.parent.mkdir(parents=True, exist_ok=True)

        data = [
            {
                'file_path': r.file_path,
                'version_type': r.version_type,
                'edition_info': r.edition_info,
                'volume': r.volume,
                'page': r.page,
                'library': r.library,
                'catalog_number': r.catalog_number,
                'line_count': r.line_count,
                'average_confidence': r.average_confidence,
                'is_vertical': r.is_vertical,
                'text_content': r.text_content,
            }
            for r in records
        ]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"JSON已导出到: {output_file}")
        print(f"共 {len(records)} 条记录")

    def export_texts_by_version(self, output_dir: Path):
        """按版本导出纯文本.

        Args:
            output_dir: 输出目录
        """
        records = self.collect_all_data()

        if not records:
            print("没有数据可导出")
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        # 按版本分组
        by_version = {}
        for record in records:
            version = record.version_type or 'Unknown'
            if version not in by_version:
                by_version[version] = []
            by_version[version].append(record)

        # 导出每个版本
        for version, version_records in by_version.items():
            version_file = output_dir / f"version_{version}_texts.txt"

            with open(version_file, 'w', encoding='utf-8') as f:
                for record in sorted(version_records, key=lambda x: (x.volume or '', x.page or '')):
                    f.write(f"{'='*60}\n")
                    f.write(f"文件: {Path(record.file_path).name}\n")
                    f.write(f"版本: {record.version_type}\n")
                    f.write(f"卷: {record.volume or 'N/A'}, 页: {record.page or 'N/A'}\n")
                    f.write(f"图书馆: {record.library or 'N/A'}\n")
                    f.write(f"{'='*60}\n\n")
                    f.write(record.text_content)
                    f.write("\n\n\n")

            print(f"版本 {version} 已导出到: {version_file} ({len(version_records)} 条记录)")

    def export_markdown_catalog(self, output_file: Path):
        """导出Markdown格式的目录.

        Args:
            output_file: 输出文件路径
        """
        records = self.collect_all_data()

        if not records:
            print("没有数据可导出")
            return

        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 按版本分组
        by_version = {}
        for record in records:
            version = record.version_type or 'Unknown'
            if version not in by_version:
                by_version[version] = []
            by_version[version].append(record)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# 史记数据集OCR处理目录\n\n")
            f.write(f"总计: {len(records)} 张图片\n\n")

            for version in sorted(by_version.keys()):
                version_records = by_version[version]
                f.write(f"## {version}版本 ({len(version_records)} 张)\n\n")

                # 按刻本分组
                by_edition = {}
                for record in version_records:
                    edition = record.edition_info or 'Unknown'
                    if edition not in by_edition:
                        by_edition[edition] = []
                    by_edition[edition].append(record)

                for edition, edition_records in sorted(by_edition.items()):
                    f.write(f"### {edition}\n\n")
                    f.write(f"共 {len(edition_records)} 张图片\n\n")

                    f.write("| 文件名 | 卷 | 页 | 行数 | 置信度 | 图书馆 |\n")
                    f.write("|--------|----|----|------|--------|--------|\n")

                    for record in sorted(edition_records, key=lambda x: (x.volume or '', x.page or '')):
                        filename = Path(record.file_path).name
                        f.write(f"| {filename} | {record.volume or '-'} | {record.page or '-'} | "
                                f"{record.line_count} | {record.average_confidence:.2%} | "
                                f"{record.library or '-'} |\n")

                    f.write("\n")

        print(f"Markdown目录已导出到: {output_file}")


def main():
    """主函数."""
    import argparse

    parser = argparse.ArgumentParser(description='导出史记数据集OCR结果')
    parser.add_argument('--output-dir', type=Path, default=Path('outputs'),
                        help='OCR输出目录（默认: outputs）')
    parser.add_argument('--format', choices=['csv', 'json', 'texts', 'markdown', 'all'],
                        default='all', help='导出格式')
    parser.add_argument('--export-dir', type=Path, default=Path('exports'),
                        help='导出文件保存目录（默认: exports）')
    parser.add_argument('--include-text', action='store_true',
                        help='CSV导出时包含文本内容')

    args = parser.parse_args()

    exporter = ShijiExporter(args.output_dir)
    args.export_dir.mkdir(parents=True, exist_ok=True)

    if args.format in ['csv', 'all']:
        exporter.export_to_csv(
            args.export_dir / 'shiji_dataset.csv',
            include_text=args.include_text
        )

    if args.format in ['json', 'all']:
        exporter.export_to_json(args.export_dir / 'shiji_dataset.json')

    if args.format in ['texts', 'all']:
        exporter.export_texts_by_version(args.export_dir / 'texts')

    if args.format in ['markdown', 'all']:
        exporter.export_markdown_catalog(args.export_dir / 'catalog.md')


if __name__ == '__main__':
    main()
