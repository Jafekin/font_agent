"""数据集分析工具 - 分析OCR处理结果."""

import json
from pathlib import Path
from typing import Dict, List
import statistics


class ShijiDatasetAnalyzer:
    """史记数据集分析器."""

    def __init__(self, output_dir: Path):
        """初始化分析器.

        Args:
            output_dir: OCR输出目录
        """
        self.output_dir = Path(output_dir)

    def collect_results(self) -> List[Dict]:
        """收集所有处理结果.

        Returns:
            结果列表
        """
        results = []

        # 查找所有 extended_metadata.json 文件
        for metadata_file in self.output_dir.rglob("extended_metadata.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    results.append(data)
            except Exception as e:
                print(f"读取失败 {metadata_file}: {e}")

        return results

    def analyze_confidence(self, results: List[Dict]) -> Dict:
        """分析置信度统计.

        Args:
            results: 结果列表

        Returns:
            置信度统计信息
        """
        confidences = [
            r['ocr_statistics']['average_confidence']
            for r in results
            if 'ocr_statistics' in r
        ]

        if not confidences:
            return {}

        return {
            'count': len(confidences),
            'mean': statistics.mean(confidences),
            'median': statistics.median(confidences),
            'stdev': statistics.stdev(confidences) if len(confidences) > 1 else 0,
            'min': min(confidences),
            'max': max(confidences),
            'high_quality': sum(1 for c in confidences if c >= 0.95),
            'medium_quality': sum(1 for c in confidences if 0.85 <= c < 0.95),
            'low_quality': sum(1 for c in confidences if c < 0.85),
        }

    def analyze_by_version(self, results: List[Dict]) -> Dict:
        """按版本分析.

        Args:
            results: 结果列表

        Returns:
            版本统计信息
        """
        version_stats = {}

        for result in results:
            version = result.get('image_metadata', {}).get('version_type', 'Unknown')

            if version not in version_stats:
                version_stats[version] = {
                    'count': 0,
                    'total_lines': 0,
                    'confidences': [],
                    'vertical_count': 0,
                }

            stats = result.get('ocr_statistics', {})
            version_stats[version]['count'] += 1
            version_stats[version]['total_lines'] += stats.get('line_count', 0)
            version_stats[version]['confidences'].append(stats.get('average_confidence', 0))

            if stats.get('is_vertical', False):
                version_stats[version]['vertical_count'] += 1

        # 计算平均值
        for version, stats in version_stats.items():
            if stats['confidences']:
                stats['avg_confidence'] = statistics.mean(stats['confidences'])
                stats['avg_lines'] = stats['total_lines'] / stats['count']
            del stats['confidences']  # 删除原始数据

        return version_stats

    def analyze_by_library(self, results: List[Dict]) -> Dict:
        """按图书馆分析.

        Args:
            results: 结果列表

        Returns:
            图书馆统计信息
        """
        library_stats = {}

        for result in results:
            library = result.get('image_metadata', {}).get('library', 'Unknown')

            if library not in library_stats:
                library_stats[library] = {
                    'count': 0,
                    'total_lines': 0,
                }

            stats = result.get('ocr_statistics', {})
            library_stats[library]['count'] += 1
            library_stats[library]['total_lines'] += stats.get('line_count', 0)

        # 计算平均值
        for library, stats in library_stats.items():
            if stats['count'] > 0:
                stats['avg_lines'] = stats['total_lines'] / stats['count']

        return library_stats

    def analyze_text_orientation(self, results: List[Dict]) -> Dict:
        """分析文本方向.

        Args:
            results: 结果列表

        Returns:
            文本方向统计
        """
        vertical_count = 0
        horizontal_count = 0

        for result in results:
            is_vertical = result.get('ocr_statistics', {}).get('is_vertical', False)
            if is_vertical:
                vertical_count += 1
            else:
                horizontal_count += 1

        return {
            'vertical': vertical_count,
            'horizontal': horizontal_count,
            'total': vertical_count + horizontal_count,
            'vertical_ratio': vertical_count / (vertical_count + horizontal_count) if (vertical_count + horizontal_count) > 0 else 0,
        }

    def generate_report(self, output_file: Path = None):
        """生成分析报告.

        Args:
            output_file: 输出文件路径（可选）
        """
        print("正在收集处理结果...")
        results = self.collect_results()

        if not results:
            print("未找到处理结果")
            return

        print(f"共找到 {len(results)} 个处理结果\n")

        # 置信度分析
        print("="*60)
        print("置信度分析")
        print("="*60)
        confidence_stats = self.analyze_confidence(results)
        if confidence_stats:
            print(f"总数: {confidence_stats['count']}")
            print(f"平均值: {confidence_stats['mean']:.2%}")
            print(f"中位数: {confidence_stats['median']:.2%}")
            print(f"标准差: {confidence_stats['stdev']:.4f}")
            print(f"最小值: {confidence_stats['min']:.2%}")
            print(f"最大值: {confidence_stats['max']:.2%}")
            print(f"\n质量分布:")
            print(f"  高质量 (≥95%): {confidence_stats['high_quality']} ({confidence_stats['high_quality']/confidence_stats['count']*100:.1f}%)")
            print(f"  中等质量 (85-95%): {confidence_stats['medium_quality']} ({confidence_stats['medium_quality']/confidence_stats['count']*100:.1f}%)")
            print(f"  低质量 (<85%): {confidence_stats['low_quality']} ({confidence_stats['low_quality']/confidence_stats['count']*100:.1f}%)")

        # 版本分析
        print("\n" + "="*60)
        print("版本分析")
        print("="*60)
        version_stats = self.analyze_by_version(results)
        for version in sorted(version_stats.keys()):
            stats = version_stats[version]
            print(f"\n{version}版本:")
            print(f"  图片数: {stats['count']}")
            print(f"  总行数: {stats['total_lines']}")
            print(f"  平均行数: {stats['avg_lines']:.1f}")
            print(f"  平均置信度: {stats['avg_confidence']:.2%}")
            print(f"  竖排文本: {stats['vertical_count']} ({stats['vertical_count']/stats['count']*100:.1f}%)")

        # 图书馆分析
        print("\n" + "="*60)
        print("图书馆分析 (前10)")
        print("="*60)
        library_stats = self.analyze_by_library(results)
        sorted_libraries = sorted(library_stats.items(), key=lambda x: x[1]['count'], reverse=True)
        for idx, (library, stats) in enumerate(sorted_libraries[:10], 1):
            print(f"{idx}. {library}")
            print(f"   图片数: {stats['count']}, 平均行数: {stats['avg_lines']:.1f}")

        # 文本方向分析
        print("\n" + "="*60)
        print("文本方向分析")
        print("="*60)
        orientation_stats = self.analyze_text_orientation(results)
        print(f"竖排文本: {orientation_stats['vertical']} ({orientation_stats['vertical_ratio']*100:.1f}%)")
        print(f"横排文本: {orientation_stats['horizontal']} ({(1-orientation_stats['vertical_ratio'])*100:.1f}%)")
        print(f"总计: {orientation_stats['total']}")

        # 保存报告
        if output_file:
            report_data = {
                'summary': {
                    'total_images': len(results),
                    'confidence': confidence_stats,
                    'orientation': orientation_stats,
                },
                'by_version': version_stats,
                'by_library': dict(sorted_libraries),
            }

            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)

            print(f"\n报告已保存到: {output_file}")


def main():
    """主函数."""
    import argparse

    parser = argparse.ArgumentParser(description='分析史记数据集OCR处理结果')
    parser.add_argument('--output-dir', type=Path, default=Path('outputs'),
                        help='OCR输出目录（默认: outputs）')
    parser.add_argument('--report', type=Path,
                        help='保存报告到指定文件（JSON格式）')

    args = parser.parse_args()

    analyzer = ShijiDatasetAnalyzer(args.output_dir)
    analyzer.generate_report(output_file=args.report)


if __name__ == '__main__':
    main()
