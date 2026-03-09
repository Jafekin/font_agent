#!/usr/bin/env python3
"""测试脚本 - 验证 GraphRAG 模块功能."""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_data_loader():
    """测试数据加载器."""
    print("=" * 60)
    print("测试 OutputsDataLoader")
    print("=" * 60)

    from rag.graph import OutputsDataLoader

    outputs_dir = Path("outputs")
    if not outputs_dir.exists():
        print(f"❌ outputs 目录不存在: {outputs_dir}")
        return False

    try:
        loader = OutputsDataLoader(outputs_dir)
        print(f"✓ 数据加载器初始化成功")

        # 获取统计信息
        stats = loader.get_statistics()
        print(f"\n数据集统计:")
        print(f"  总页面数: {stats['total_pages']}")
        print(f"  平均置信度: {stats['average_confidence']:.2%}")
        print(f"  总文本行数: {stats['total_text_lines']}")

        if stats['total_pages'] > 0:
            print(f"\n版本分布:")
            for version, count in sorted(stats['version_distribution'].items())[:5]:
                print(f"  {version}: {count}")

            print(f"\n馆藏分布:")
            for institution, count in sorted(stats['institution_distribution'].items())[:5]:
                print(f"  {institution}: {count}")

        # 加载一个页面测试
        pages = loader.load_all_pages()
        if pages:
            page = pages[0]
            print(f"\n示例页面:")
            print(f"  页面 ID: {page['page_id']}")
            print(f"  版本类型: {page.get('version_type', 'N/A')}")
            print(f"  版本名称: {page.get('edition_name', 'N/A')}")
            print(f"  馆藏: {page.get('institution', 'N/A')}")
            print(f"  OCR 置信度: {page.get('ocr_confidence', 0):.2%}")
            print(f"  文本行数: {page.get('line_count', 0)}")

            # 测试实体提取
            if page.get('ocr_text'):
                entities = loader.extract_entities_from_text(page['ocr_text'][:200])
                if entities:
                    print(f"\n提取的实体:")
                    for entity in entities[:5]:
                        print(f"  {entity['entity_text']} ({entity['entity_type']})")

        print(f"\n✓ 数据加载器测试通过")
        return True

    except Exception as e:
        print(f"❌ 数据加载器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_builder():
    """测试增强构建器（不连接 Neo4j）."""
    print("\n" + "=" * 60)
    print("测试 EnhancedGraphBuilder")
    print("=" * 60)

    try:
        from rag.graph import EnhancedGraphBuilder

        print("✓ EnhancedGraphBuilder 导入成功")

        # 检查方法是否存在
        methods = [
            'build_from_outputs',
            'build_similarity_relations_from_embeddings',
            '_estimate_column_count',
            '_get_or_create_document',
            '_get_or_create_volume',
        ]

        for method in methods:
            if hasattr(EnhancedGraphBuilder, method):
                print(f"  ✓ 方法 {method} 存在")
            else:
                print(f"  ❌ 方法 {method} 不存在")
                return False

        print(f"\n✓ 增强构建器测试通过")
        return True

    except Exception as e:
        print(f"❌ 增强构建器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_imports():
    """测试模块导入."""
    print("\n" + "=" * 60)
    print("测试模块导入")
    print("=" * 60)

    modules = [
        ('rag.graph', ['Neo4jClient', 'GraphBuilder', 'EnhancedGraphBuilder', 'OutputsDataLoader']),
        ('rag.graph.models', ['Document', 'Volume', 'Page', 'Edition', 'Collection', 'Layout']),
    ]

    all_passed = True

    for module_name, classes in modules:
        try:
            module = __import__(module_name, fromlist=classes)
            print(f"✓ 模块 {module_name} 导入成功")

            for cls_name in classes:
                if hasattr(module, cls_name):
                    print(f"  ✓ 类 {cls_name} 存在")
                else:
                    print(f"  ❌ 类 {cls_name} 不存在")
                    all_passed = False

        except Exception as e:
            print(f"❌ 模块 {module_name} 导入失败: {e}")
            all_passed = False

    if all_passed:
        print(f"\n✓ 所有导入测试通过")
    else:
        print(f"\n❌ 部分导入测试失败")

    return all_passed


def test_script_exists():
    """测试脚本是否存在."""
    print("\n" + "=" * 60)
    print("测试脚本文件")
    print("=" * 60)

    script_path = Path("scripts/build_graph_from_outputs.py")
    if script_path.exists():
        print(f"✓ 脚本文件存在: {script_path}")

        # 检查是否可执行
        import os
        if os.access(script_path, os.X_OK):
            print(f"  ✓ 脚本可执行")
        else:
            print(f"  ⚠ 脚本不可执行（可能需要 chmod +x）")

        return True
    else:
        print(f"❌ 脚本文件不存在: {script_path}")
        return False


def main():
    """运行所有测试."""
    print("\n" + "=" * 60)
    print("GraphRAG 模块功能测试")
    print("=" * 60 + "\n")

    results = {
        "导入测试": test_imports(),
        "脚本文件测试": test_script_exists(),
        "数据加载器测试": test_data_loader(),
        "增强构建器测试": test_enhanced_builder(),
    }

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())
    print("=" * 60)

    if all_passed:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查上述错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
