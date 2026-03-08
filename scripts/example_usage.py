"""史记数据集处理脚本使用示例."""

from pathlib import Path
from process_shiji_dataset import ShijiDatasetProcessor, ShijiPathParser

# ============================================================
# 示例 1: 快速测试 - 处理前5张图片
# ============================================================
def example_quick_test():
    """快速测试：处理前5张图片."""
    print("示例 1: 快速测试")
    print("-" * 60)

    processor = ShijiDatasetProcessor(
        data_dir=Path("data"),
        output_dir=Path("outputs_test"),
    )

    # 只处理前5张图片
    processor.process_all(skip_existing=True, max_images=5)


# ============================================================
# 示例 2: 按版本处理 - 只处理A版本（集解本）
# ============================================================
def example_process_by_version():
    """按版本处理：只处理A版本."""
    print("\n示例 2: 按版本处理")
    print("-" * 60)

    processor = ShijiDatasetProcessor(
        data_dir=Path("data"),
        output_dir=Path("outputs_version_a"),
    )

    # 只处理A版本
    processor.process_by_version(version_type="A", skip_existing=True)


# ============================================================
# 示例 3: 查看元数据解析结果
# ============================================================
def example_parse_metadata():
    """查看元数据解析结果."""
    print("\n示例 3: 元数据解析")
    print("-" * 60)

    parser = ShijiPathParser()

    # 示例路径
    test_paths = [
        "data/名录 史记2025-11-6/B史记 集解、索隐合刻本 4明正德十三年（1518）邵宗周刻本/【4】10160 （四）00096 史记一百三十卷 （汉）司马迁撰 （南朝宋）裴骃集解 （唐）司马贞索隐 明正德十三年（1518）邵宗周刻本 欧阳辅跋 江西省图书馆#存一百二十六卷/史記·卷四十p1a.jpg",
        "data/名录 史记2025-11-6/C史记 集解、索隐、正义三家注本 3元至元二十五年（1288）彭寅翁崇道精舍刻本/【6】12357 （六）19106 史记一百三十卷 （汉）司马迁撰 （南朝宋）裴骃集解 （唐）司马贞索隐 （唐）张守节正义 元至元二十五年（1288）彭寅翁崇道精舍刻本（卷一百十七至一百二十二配蒙古/增补6-11279 史记一百三十卷 书影003-卷117首叶.jpg",
    ]

    for path_str in test_paths:
        path = Path(path_str)
        if path.exists():
            metadata = parser.parse_path(path)
            print(f"\n文件: {path.name}")
            print(f"  版本类型: {metadata.version_type}")
            print(f"  刻本信息: {metadata.edition_info}")
            print(f"  卷数: {metadata.volume}")
            print(f"  页码: {metadata.page}")
            print(f"  图书馆: {metadata.library}")
            print(f"  编目号: {metadata.catalog_number}")


# ============================================================
# 示例 4: 导出元数据索引并分析
# ============================================================
def example_export_and_analyze():
    """导出元数据索引并进行统计分析."""
    print("\n示例 4: 导出并分析元数据")
    print("-" * 60)

    processor = ShijiDatasetProcessor(
        data_dir=Path("data"),
        output_dir=Path("outputs"),
    )

    # 导出元数据索引
    index_file = Path("metadata_index.json")
    processor.export_metadata_index(index_file)

    # 读取并分析
    import json
    with open(index_file, 'r', encoding='utf-8') as f:
        metadata_list = json.load(f)

    # 统计各版本数量
    version_counts = {}
    library_counts = {}

    for item in metadata_list:
        version = item['version_type']
        library = item['library']

        version_counts[version] = version_counts.get(version, 0) + 1
        if library:
            library_counts[library] = library_counts.get(library, 0) + 1

    print(f"\n总图片数: {len(metadata_list)}")
    print("\n各版本统计:")
    for version in sorted(version_counts.keys()):
        print(f"  {version}版本: {version_counts[version]} 张")

    print("\n图书馆统计 (前10):")
    sorted_libraries = sorted(library_counts.items(), key=lambda x: x[1], reverse=True)
    for library, count in sorted_libraries[:10]:
        print(f"  {library}: {count} 张")


# ============================================================
# 示例 5: 自定义OCR配置
# ============================================================
def example_custom_config():
    """使用自定义OCR配置."""
    print("\n示例 5: 自定义OCR配置")
    print("-" * 60)

    from ocr import KandiangujiOCRClient, OCRConfig

    # 自定义配置
    config = OCRConfig(
        token="your-token",
        email="your-email",
        det_mode="auto",  # 自动检测模式
        version="default",
        char_ocr=True,  # 启用字符级OCR
        return_position=True,  # 返回位置信息
    )

    client = KandiangujiOCRClient(config)

    processor = ShijiDatasetProcessor(
        data_dir=Path("data"),
        output_dir=Path("outputs_custom"),
        client=client,
    )

    processor.process_all(skip_existing=True, max_images=3)


# ============================================================
# 示例 6: 处理单张图片
# ============================================================
def example_single_image():
    """处理单张图片."""
    print("\n示例 6: 处理单张图片")
    print("-" * 60)

    processor = ShijiDatasetProcessor(
        data_dir=Path("data"),
        output_dir=Path("outputs_single"),
    )

    # 找到第一张图片
    images = processor.find_images()
    if images:
        first_image = images[0]
        print(f"处理图片: {first_image}")
        success = processor.process_image(first_image, skip_existing=False)
        print(f"处理结果: {'成功' if success else '失败'}")


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("史记数据集处理脚本 - 使用示例")
    print("=" * 60)

    # 运行示例（取消注释想要运行的示例）

    # example_quick_test()              # 快速测试
    # example_process_by_version()      # 按版本处理
    example_parse_metadata()          # 元数据解析
    example_export_and_analyze()      # 导出并分析
    # example_custom_config()           # 自定义配置
    # example_single_image()            # 单张图片

    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)
