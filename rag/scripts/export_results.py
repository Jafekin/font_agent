"""导出工具 - 将OCR结果导出为不同格式."""

import json
import csv
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ExportRecord:
    """导出记录，对应 EditionMetadata + OCR统计."""
    # ── 版本元数据 ──────────────────────────────────────────
    file_path: str
    page: str                              # 文件名（不含扩展名）
    edition_dir: str                       # 版本目录名
    version_type: str                      # A/B/C/D/E
    annotation_system: Optional[str]       # 集解 | 集解+索隐 | 三家注
    dynasty_period: Optional[str]          # 刻印朝代
    printer: Optional[str]                 # 刻印者/书坊
    total_juan: Optional[int]              # 全书总卷数
    extant_juan: Optional[str]             # 现存卷数说明
    holding_institution: Optional[str]     # 收藏机构
    catalog_id_main: Optional[str]         # 主编目号
    catalog_id_secondary: Optional[str]    # 副编目号
    authors: str                           # 原作者（分号分隔）
    annotators: str                        # 注疏者（分号分隔）
    peiben_notes: Optional[str]            # 配本说明
    colophon_authors: Optional[str]        # 跋文作者
    # ── OCR统计 ────────────────────────────────────────────
    line_count: int
    average_confidence: float
    is_vertical: bool
    text_content: str


class ShijiExporter:
    """史记数据集导出器."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def collect_all_data(self) -> List[ExportRecord]:
        """收集所有 extended_metadata.json 并转为 ExportRecord 列表."""
        records = []

        for metadata_file in self.output_dir.rglob("extended_metadata.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                text_file = metadata_file.parent / "text" / f"{metadata_file.parent.name}.txt"
                text_content = ""
                if text_file.exists():
                    with open(text_file, 'r', encoding='utf-8') as f:
                        text_content = f.read()

                ed = metadata.get('edition_metadata', {})
                ocr = metadata.get('ocr_statistics', {})
                printing = ed.get('printing_info') or {}
                image_file = metadata.get('image_file', '')

                records.append(ExportRecord(
                    file_path=image_file,
                    page=Path(image_file).stem,
                    edition_dir=ed.get('edition_dir', ''),
                    version_type=ed.get('version_type', ''),
                    annotation_system=ed.get('annotation_system'),
                    dynasty_period=printing.get('dynasty_period'),
                    printer=printing.get('printer'),
                    total_juan=ed.get('total_juan'),
                    extant_juan=ed.get('extant_juan'),
                    holding_institution=ed.get('holding_institution'),
                    catalog_id_main=ed.get('catalog_id_main'),
                    catalog_id_secondary=ed.get('catalog_id_secondary'),
                    authors='；'.join(ed.get('authors') or []),
                    annotators='；'.join(ed.get('annotators') or []),
                    peiben_notes=ed.get('peiben_notes'),
                    colophon_authors=ed.get('colophon_authors'),
                    line_count=ocr.get('line_count', 0),
                    average_confidence=ocr.get('average_confidence', 0.0),
                    is_vertical=ocr.get('is_vertical', False),
                    text_content=text_content,
                ))

            except Exception as e:
                print(f"处理失败 {metadata_file}: {e}")

        return records

    def export_to_csv(self, output_file: Path, include_text: bool = False):
        """导出为CSV格式."""
        records = self.collect_all_data()
        if not records:
            print("没有数据可导出")
            return

        output_file.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            'file_path', 'page', 'edition_dir', 'version_type',
            'annotation_system', 'dynasty_period', 'printer',
            'total_juan', 'extant_juan',
            'holding_institution', 'catalog_id_main', 'catalog_id_secondary',
            'authors', 'annotators', 'peiben_notes', 'colophon_authors',
            'line_count', 'average_confidence', 'is_vertical',
        ]
        if include_text:
            fieldnames.append('text_content')

        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                row = {
                    'file_path': r.file_path,
                    'page': r.page,
                    'edition_dir': r.edition_dir,
                    'version_type': r.version_type,
                    'annotation_system': r.annotation_system or '',
                    'dynasty_period': r.dynasty_period or '',
                    'printer': r.printer or '',
                    'total_juan': r.total_juan if r.total_juan is not None else '',
                    'extant_juan': r.extant_juan or '',
                    'holding_institution': r.holding_institution or '',
                    'catalog_id_main': r.catalog_id_main or '',
                    'catalog_id_secondary': r.catalog_id_secondary or '',
                    'authors': r.authors,
                    'annotators': r.annotators,
                    'peiben_notes': r.peiben_notes or '',
                    'colophon_authors': r.colophon_authors or '',
                    'line_count': r.line_count,
                    'average_confidence': f"{r.average_confidence:.4f}",
                    'is_vertical': '是' if r.is_vertical else '否',
                }
                if include_text:
                    row['text_content'] = r.text_content
                writer.writerow(row)

        print(f"CSV已导出到: {output_file}（共 {len(records)} 条）")

    def export_to_json(self, output_file: Path):
        """导出为JSON格式."""
        records = self.collect_all_data()
        if not records:
            print("没有数据可导出")
            return

        output_file.parent.mkdir(parents=True, exist_ok=True)

        data = [
            {
                'file_path': r.file_path,
                'page': r.page,
                'edition_dir': r.edition_dir,
                'version_type': r.version_type,
                'annotation_system': r.annotation_system,
                'dynasty_period': r.dynasty_period,
                'printer': r.printer,
                'total_juan': r.total_juan,
                'extant_juan': r.extant_juan,
                'holding_institution': r.holding_institution,
                'catalog_id_main': r.catalog_id_main,
                'catalog_id_secondary': r.catalog_id_secondary,
                'authors': r.authors,
                'annotators': r.annotators,
                'peiben_notes': r.peiben_notes,
                'colophon_authors': r.colophon_authors,
                'line_count': r.line_count,
                'average_confidence': r.average_confidence,
                'is_vertical': r.is_vertical,
                'text_content': r.text_content,
            }
            for r in records
        ]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"JSON已导出到: {output_file}（共 {len(records)} 条）")

    def export_texts_by_version(self, output_dir: Path):
        """按版本导出纯文本."""
        records = self.collect_all_data()
        if not records:
            print("没有数据可导出")
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        by_version: dict = {}
        for r in records:
            by_version.setdefault(r.version_type or 'Unknown', []).append(r)

        for version, version_records in by_version.items():
            version_file = output_dir / f"version_{version}_texts.txt"
            with open(version_file, 'w', encoding='utf-8') as f:
                for r in sorted(version_records, key=lambda x: (x.extant_juan or '', x.page or '')):
                    f.write(f"{'='*60}\n")
                    f.write(f"文件: {Path(r.file_path).name}\n")
                    f.write(f"版本: {r.version_type}  注释: {r.annotation_system or 'N/A'}\n")
                    f.write(f"刻印: {r.dynasty_period or 'N/A'}  刻印者: {r.printer or 'N/A'}\n")
                    f.write(f"现存卷: {r.extant_juan or 'N/A'}\n")
                    f.write(f"收藏: {r.holding_institution or 'N/A'}\n")
                    f.write(f"著者: {r.authors or 'N/A'}  注疏者: {r.annotators or 'N/A'}\n")
                    f.write(f"{'='*60}\n\n")
                    f.write(r.text_content)
                    f.write("\n\n\n")

            print(f"版本 {version} 已导出到: {version_file}（{len(version_records)} 条）")

    def export_markdown_catalog(self, output_file: Path):
        """导出Markdown格式的目录."""
        records = self.collect_all_data()
        if not records:
            print("没有数据可导出")
            return

        output_file.parent.mkdir(parents=True, exist_ok=True)

        by_version: dict = {}
        for r in records:
            by_version.setdefault(r.version_type or 'Unknown', []).append(r)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# 史记数据集OCR处理目录\n\n")
            f.write(f"总计: {len(records)} 张图片\n\n")

            for version in sorted(by_version.keys()):
                version_records = by_version[version]
                f.write(f"## {version}版本 ({len(version_records)} 张)\n\n")

                by_edition: dict = {}
                for r in version_records:
                    by_edition.setdefault(r.edition_dir or 'Unknown', []).append(r)

                for edition, edition_records in sorted(by_edition.items()):
                    # 取第一条记录的版本级信息作为 header
                    s = edition_records[0]
                    f.write(f"### {edition}\n\n")
                    f.write(f"- **注释体系**: {s.annotation_system or '-'}\n")
                    f.write(f"- **刻印朝代**: {s.dynasty_period or '-'}　**刻印者**: {s.printer or '-'}\n")
                    f.write(f"- **总卷数**: {s.total_juan or '-'}　**现存卷**: {s.extant_juan or '-'}\n")
                    f.write(f"- **收藏机构**: {s.holding_institution or '-'}\n")
                    f.write(f"- **编目号**: {s.catalog_id_main or '-'}　副号: {s.catalog_id_secondary or '-'}\n")
                    f.write(f"- **著者**: {s.authors or '-'}　**注疏者**: {s.annotators or '-'}\n")
                    if s.peiben_notes:
                        f.write(f"- **配本说明**: {s.peiben_notes}\n")
                    if s.colophon_authors:
                        f.write(f"- **跋文作者**: {s.colophon_authors}\n")
                    f.write(f"\n共 {len(edition_records)} 张图片\n\n")

                    f.write("| 文件名 | 行数 | 置信度 | 方向 |\n")
                    f.write("|--------|------|--------|------|\n")
                    for r in sorted(edition_records, key=lambda x: x.page or ''):
                        f.write(f"| {Path(r.file_path).name} | {r.line_count} | "
                                f"{r.average_confidence:.2%} | {'竖' if r.is_vertical else '横'} |\n")
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
            include_text=args.include_text,
        )
    if args.format in ['json', 'all']:
        exporter.export_to_json(args.export_dir / 'shiji_dataset.json')
    if args.format in ['texts', 'all']:
        exporter.export_texts_by_version(args.export_dir / 'texts')
    if args.format in ['markdown', 'all']:
        exporter.export_markdown_catalog(args.export_dir / 'catalog.md')


if __name__ == '__main__':
    main()
