"""
处理史记数据集图片脚本

功能：
1. 遍历data目录下的所有图片
2. 从路径中解析版本、藏馆等信息
3. 对图片进行合理的重命名
4. 为每个图片生成对应的JSON文件，包含路径信息和提示词字段
"""
import os
import json
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# 支持的图片格式
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')


def parse_directory_info(dir_path: Path) -> Dict[str, Any]:
    """
    从目录路径中解析信息

    示例路径：
    A史记 集解本 1北宋刻本/【1】00393 史记一百三十卷 （汉）司马迁撰 （南朝宋）裴骃集解 北宋刻本（卷一至四、八至一百三十配南宋初建阳刻本） 北京大学图书馆/

    Returns:
        包含解析信息的字典
    """
    info = {
        'category': '',  # A史记 集解本
        'edition_type': '',  # 北宋刻本
        'edition_style': '',  # 建刻本等
        'catalog_number': '',  # 【1】00393
        'title': '',  # 史记一百三十卷
        'author': '',  # （汉）司马迁
        'editors': [],  # 裴骃集解、司马贞索隐、张守节正义
        'publication_period': '',  # 北宋、明正德十年等
        'publisher': '',  # 出版者
        'current_location': '',  # 北京大学图书馆
        'notes': '',  # 配本、题识、跋等信息
        'full_path': str(dir_path)
    }

    # 获取目录名
    dir_name = dir_path.name
    parent_name = dir_path.parent.name if dir_path.parent else ''

    # 解析分类和版本类型（从父目录）
    if parent_name:
        # 例如：A史记 集解本 1北宋刻本
        if '集解本' in parent_name:
            info['category'] = '集解本'
        elif '集解、索隐合刻本' in parent_name:
            info['category'] = '集解、索隐合刻本'
        elif '集解、索隐、正义三家注本' in parent_name:
            info['category'] = '集解、索隐、正义三家注本'
        elif '三家注明陈仁锡评本' in parent_name:
            info['category'] = '三家注明陈仁锡评本'
        elif '三家注明徐孚远陈子龙测议本' in parent_name:
            info['category'] = '三家注明徐孚远陈子龙测议本'

        # 提取版本类型
        edition_patterns = [
            r'(\d+)([^0-9]+刻本)',
            r'([^0-9]+刻本)',
            r'([^0-9]+写本)',
            r'([^0-9]+影抄)',
            r'([^0-9]+集配本)',
            r'([^0-9]+印本)',
        ]
        for pattern in edition_patterns:
            match = re.search(pattern, parent_name)
            if match:
                info['edition_type'] = match.group(
                    1) if match.groups() else match.group(0)
                break

        # 提取版本风格
        if '建刻本' in parent_name or '建阳' in parent_name:
            info['edition_style'] = '建刻本'
        elif '浙刻本' in parent_name:
            info['edition_style'] = '浙刻本'
        elif '蜀刻本' in parent_name:
            info['edition_style'] = '蜀刻本'

    # 解析详细目录名
    # 例如：【1】00393 史记一百三十卷 （汉）司马迁撰 （南朝宋）裴骃集解 北宋刻本（卷一至四、八至一百三十配南宋初建阳刻本） 北京大学图书馆
    if dir_name:
        # 提取编号
        catalog_match = re.search(r'【(\d+)】\s*(\d+)', dir_name)
        if catalog_match:
            info['catalog_number'] = f"【{catalog_match.group(1)}】{catalog_match.group(2)}"

        # 提取标题
        title_match = re.search(r'史记[^（]*', dir_name)
        if title_match:
            info['title'] = title_match.group(0).strip()

        # 提取作者
        author_match = re.search(r'（([^）]+)）([^撰]+)撰', dir_name)
        if author_match:
            info['author'] = f"（{author_match.group(1)}）{author_match.group(2)}撰"

        # 提取编者
        editor_patterns = [
            r'（([^）]+)）([^集解索隐正义]+)(集解|索隐|正义)',
        ]
        editors = []
        for pattern in editor_patterns:
            matches = re.finditer(pattern, dir_name)
            for match in matches:
                editor = f"（{match.group(1)}）{match.group(2)}{match.group(3)}"
                editors.append(editor)
        if editors:
            info['editors'] = editors

        # 提取出版时间
        period_patterns = [
            r'([宋元明清朝代]+[^刻]+)',
            r'([^（]+年号[^）]+)',
            r'(\d+年)',
        ]
        for pattern in period_patterns:
            match = re.search(pattern, dir_name)
            if match:
                period = match.group(1)
                # 进一步提取具体年份
                year_match = re.search(r'(\d{4})', period)
                if year_match:
                    info['publication_period'] = period
                elif not info['publication_period']:
                    info['publication_period'] = period
                break

        # 提取藏馆
        location_patterns = [
            r'([^#]+图书馆)',
            r'([^#]+博物院)',
            r'([^#]+书店)',
        ]
        for pattern in location_patterns:
            match = re.search(pattern, dir_name)
            if match:
                info['current_location'] = match.group(1).strip()
                break

        # 提取备注信息（配本、题识、跋等）
        notes_parts = []
        if '配' in dir_name:
            notes_parts.append('配本')
        if '题识' in dir_name or '题款' in dir_name:
            notes_parts.append('题识')
        if '跋' in dir_name:
            notes_parts.append('跋')
        if '存' in dir_name:
            # 提取存卷信息
            cun_match = re.search(r'存[^#]*', dir_name)
            if cun_match:
                notes_parts.append(cun_match.group(0))
        if notes_parts:
            info['notes'] = '；'.join(notes_parts)

    return info


def generate_image_metadata(image_path: Path, dir_info: Dict[str, Any], output_image_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    为图片生成完整的元数据JSON结构

    Args:
        image_path: 原始图片路径
        dir_info: 从目录解析的信息
        output_image_path: 输出图片路径（如果已复制到输出目录）

    Returns:
        完整的元数据字典，符合prompt.py中的字段结构
    """
    # 提取图片文件名信息
    image_name = image_path.stem
    image_ext = image_path.suffix

    # 尝试从文件名提取卷号等信息
    volume_match = re.search(r'卷[^pP]*', image_name)
    volume_info = volume_match.group(0) if volume_match else ''

    # 构建完整的元数据
    metadata = {
        # 路径信息
        "path_info": {
            "original_path": str(image_path),
            "original_relative_path": str(image_path.relative_to(image_path.parents[3])) if len(image_path.parents) > 3 else str(image_path),
            "original_directory": str(image_path.parent),
            "original_filename": image_path.name,
            "output_path": str(output_image_path) if output_image_path else "",
            "output_filename": output_image_path.name if output_image_path else image_path.name,
            "category": dir_info.get('category', ''),
            "catalog_number": dir_info.get('catalog_number', '')
        },

        # 文档元数据
        "document_metadata": {
            "document_type": {
                "value": "汉文古籍",
                "confidence": 1.0
            },
            "language": {
                "value": "汉文",
                "confidence": 1.0
            },
            "classification": {
                "value": "史部-紀傳類-通代之屬",
                "confidence": 1.0
            }
        },

        # 标题
        "title": {
            "title_text": dir_info.get('title', '史记一百三十卷'),
            "confidence": 1.0
        },

        # 作者和编者
        "author_and_editors": {
            "author": dir_info.get('author', '（汉）司马迁撰'),
            "editor_commentator": dir_info.get('editors', []),
            "biographies": "",
            "confidence": 1.0
        },

        # 版本信息
        "edition_information": {
            "edition_type": dir_info.get('edition_type', ''),
            "edition_style": dir_info.get('edition_style', ''),
            "publication_period": dir_info.get('publication_period', ''),
            "publisher": dir_info.get('publisher', ''),
            "publisher_biography": "",
            "edition_variants": [],
            "judgement_basis": "",
            "confidence": 0.8 if dir_info.get('edition_type') else 0.0
        },

        # 格式和版式
        "format_and_layout": {
            "layout_description": "",
            "page_frame_size_cm": {
                "width": 0.0,
                "height": 0.0
            },
            "print_frame_size_cm": {
                "width": 0.0,
                "height": 0.0
            },
            "colophons": "",
            "confidence": 0.0
        },

        # 题跋和印章
        "marks_and_annotations": {
            "inscriptions": [],
            "seals": [],
            "confidence": 0.0
        },

        # 物理规格
        "physical_specifications": {
            "quantity": "",
            "binding_style": "",
            "open_size_cm": {
                "width": 0.0,
                "height": 0.0
            },
            "damage_level": "",
            "damage_description": "",
            "damage_assessment": "",
            "repair_suggestions": "",
            "confidence": 0.0
        },

        # 页面内容
        "page_content": {
            "transcription": {
                "lines": [],
                "annotations": [],
                "modern_reading": ""
            },
            "page_summary": "",
            "vernacular_translation": "",
            "key_terms": [],
            "confidence": 0.0
        },

        # 字形关键点和证据
        "glyph_keypoints_and_evidence": [],

        # 词汇候选和参考
        "lexical_candidates_and_references": [],

        # 收藏和来源
        "collection_and_provenance": {
            "current_location": dir_info.get('current_location', ''),
            "collection_history": "",
            "collector_biography": "",
            "bibliographic_records": "",
            "confidence": 1.0 if dir_info.get('current_location') else 0.0
        },

        # 数字资源
        "digital_resources": {
            "full_text_images": "",
            "similar_edition_links": "",
            "reprint_information": "",
            "research_references": ""
        },

        # 进一步工作建议
        "further_work_suggestions": {
            "photography": [],
            "image_processing": [],
            "exhibition_and_activation": "",
            "learning_resources": ""
        },

        # 初步释读
        "preliminary_reading": {
            "possible_script_and_period": {
                "text": "",
                "confidence": 0.0
            },
            "writing_direction_and_layout": {
                "text": "",
                "confidence": 0.0
            }
        },

        # 备注
        "notes": dir_info.get('notes', ''),

        # 处理时间
        "processing_info": {
            "processed_at": datetime.now().isoformat(),
            "script_version": "1.0"
        }
    }

    return metadata


def generate_new_filename(image_path: Path, dir_info: Dict[str, Any], index: int) -> str:
    """
    生成新的文件名（确保唯一性）

    格式：史记_{版本类型}_{编号}_{序号}_{原文件名hash}.jpg
    例如：史记_北宋刻本_00393_0001_a1b2c3.jpg
    """
    # 提取编号
    catalog_num = dir_info.get('catalog_number', '').replace(
        '【', '').replace('】', '').strip()
    if not catalog_num:
        catalog_num = 'unknown'

    # 提取版本类型（简化）
    edition = dir_info.get('edition_type', 'unknown')
    if not edition:
        edition = 'unknown'

    # 清理版本类型，移除特殊字符
    edition_clean = re.sub(r'[^\w]', '_', edition)[:20]

    # 生成序号（4位数字）
    seq = f"{index:04d}"

    # 使用原文件名的hash确保唯一性（取前6位）
    import hashlib
    original_name_hash = hashlib.md5(
        image_path.name.encode('utf-8')).hexdigest()[:6]

    # 保留原扩展名
    ext = image_path.suffix

    # 组合新文件名
    new_name = f"史记_{edition_clean}_{catalog_num}_{seq}_{original_name_hash}{ext}"

    return new_name


def process_images(
    data_dir: str,
    output_dir: str,
    rename_images: bool = True,
    backup_original: bool = True
) -> None:
    """
    处理所有图片，将所有文件复制到单一的输出目录

    Args:
        data_dir: 数据目录路径
        output_dir: 输出目录（必须指定，所有文件将复制到此目录）
        rename_images: 是否重命名图片
        backup_original: 是否备份原文件（在原目录备份）
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"错误: 数据目录不存在: {data_dir}")
        return

    # 输出目录必须指定
    if not output_dir:
        print("错误: 必须指定输出目录 --output-dir")
        return

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 统计信息
    stats = {
        'total_images': 0,
        'processed': 0,
        'errors': 0,
        'skipped': 0,
        'duplicates': 0
    }

    # 用于跟踪已使用的文件名，避免重复
    used_filenames = set()

    print(f"开始处理图片，数据目录: {data_dir}")
    print(f"输出目录: {output_path}")
    print("-" * 80)

    # 遍历所有图片
    for image_path in data_path.rglob('*'):
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        stats['total_images'] += 1

        try:
            # 解析目录信息
            dir_info = parse_directory_info(image_path.parent)

            # 生成新文件名
            if rename_images:
                new_filename = generate_new_filename(
                    image_path, dir_info, stats['processed'] + 1)

                # 确保文件名唯一
                base_name = Path(new_filename).stem
                ext = Path(new_filename).suffix
                counter = 1
                while new_filename in used_filenames:
                    new_filename = f"{base_name}_{counter:03d}{ext}"
                    counter += 1

                used_filenames.add(new_filename)
            else:
                # 不重命名时，使用原文件名，但也要确保唯一
                new_filename = image_path.name
                base_name = image_path.stem
                ext = image_path.suffix
                counter = 1
                while new_filename in used_filenames:
                    new_filename = f"{base_name}_{counter:03d}{ext}"
                    counter += 1

                used_filenames.add(new_filename)
                if counter > 1:
                    stats['duplicates'] += 1

            # 目标文件路径（在输出目录中）
            output_image_path = output_path / new_filename
            output_json_path = output_path / f"{output_image_path.stem}.json"

            # 生成元数据（保留原始路径信息，包含输出路径）
            metadata = generate_image_metadata(
                image_path, dir_info, output_image_path)

            # 复制图片到输出目录
            shutil.copy2(image_path, output_image_path)

            # 保存JSON文件到输出目录
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            # 备份原文件（如果需要，在原目录备份）
            if backup_original:
                backup_path = image_path.parent / f".backup_{image_path.name}"
                if not backup_path.exists():
                    shutil.copy2(image_path, backup_path)

            if rename_images:
                print(f"✓ {image_path.name} -> {new_filename}")
            else:
                print(f"✓ {image_path.name} (复制到输出目录)")

            stats['processed'] += 1

            # 每处理100个文件显示进度
            if stats['processed'] % 100 == 0:
                print(f"已处理: {stats['processed']}/{stats['total_images']}")

        except Exception as e:
            stats['errors'] += 1
            print(f"✗ 处理失败 {image_path}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # 显示统计信息
    print("-" * 80)
    print(f"处理完成！")
    print(f"总图片数: {stats['total_images']}")
    print(f"成功处理: {stats['processed']}")
    print(f"错误: {stats['errors']}")
    print(f"跳过: {stats['skipped']}")
    if stats['duplicates'] > 0:
        print(f"重名文件: {stats['duplicates']} (已自动重命名)")
    print(f"\n所有文件已复制到: {output_path}")
    print(f"图片文件: {stats['processed']} 个")
    print(f"JSON文件: {stats['processed']} 个")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='处理史记数据集图片，重命名并生成JSON元数据文件'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/名录 史记2025-11-6',
        help='数据目录路径（默认: data/名录 史记2025-11-6）'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        required=True,
        help='输出目录（必须指定，所有处理后的文件将复制到此目录）'
    )
    parser.add_argument(
        '--no-rename',
        action='store_true',
        help='不重命名图片，只生成JSON文件'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='不备份原文件'
    )

    args = parser.parse_args()

    # 处理图片
    process_images(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        rename_images=not args.no_rename,
        backup_original=not args.no_backup
    )


if __name__ == "__main__":
    main()
