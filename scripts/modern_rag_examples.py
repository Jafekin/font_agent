"""现代RAG使用示例."""
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from rag.modern import ModernRAGPipeline, ModernIndexer, ModernRAGConfig


def example_1_build_index():
    """示例1: 构建索引."""
    print("\n" + "="*60)
    print("示例1: 构建现代RAG索引")
    print("="*60)

    indexer = ModernIndexer()
    indexer.build_index(
        data_dir=Path("outputs"),
        output_dir=Path("rag/modern/indexes")
    )

    print("\n✓ 索引构建完成")


def example_2_single_image():
    """示例2: 处理单张图片."""
    print("\n" + "="*60)
    print("示例2: 处理单张古籍图片")
    print("="*60)

    # 初始化流程
    pipeline = ModernRAGPipeline()

    # 处理图片
    result = pipeline.run(
        image_path="media/uploads/test.jpg",
        ocr_text="史記卷四十 太史公自序第七十",  # 可选
        metadata={"edition_type": "刻本", "dynasty": "明"}  # 可选
    )

    # 查看结果
    if result["success"]:
        print("\n✓ 处理成功")
        print(f"\n检索结果: {result['retrieval']['num_results']} 条")
        print(f"版本类型: {result['final_output'].get('version_type')}")
        print(f"时代: {result['final_output'].get('dynasty')}")
        print(f"题名: {result['final_output'].get('title')}")
        print(f"置信度: {result['final_output'].get('confidence')}")
        print(f"\n总耗时: {result['timing']['total']:.2f}s")
    else:
        print(f"\n✗ 处理失败: {result.get('error')}")

    return result


def example_3_batch_processing():
    """示例3: 批量处理."""
    print("\n" + "="*60)
    print("示例3: 批量处理多张图片")
    print("="*60)

    pipeline = ModernRAGPipeline()

    # 批量处理
    image_paths = [
        "media/uploads/test1.jpg",
        "media/uploads/test2.jpg",
        "media/uploads/test3.jpg"
    ]

    results = pipeline.batch_run(image_paths)

    # 统计
    success_count = sum(1 for r in results if r["success"])
    print(f"\n✓ 批量处理完成: {success_count}/{len(results)} 成功")

    return results


def example_4_custom_config():
    """示例4: 自定义配置."""
    print("\n" + "="*60)
    print("示例4: 使用自定义配置")
    print("="*60)

    # 自定义配置
    config = ModernRAGConfig()
    config.retriever.hybrid_top_k = 5  # 只检索Top-5
    config.retriever.fusion_weights = {
        "vector": 0.5,  # 提高向量检索权重
        "text": 0.3,
        "graph": 0.2
    }
    config.pipeline.enable_multi_stage = True  # 启用多阶段推理

    # 使用自定义配置
    pipeline = ModernRAGPipeline(config)

    result = pipeline.run(
        image_path="media/uploads/test.jpg"
    )

    print(f"\n✓ 使用自定义配置处理完成")
    return result


def example_5_compare_with_old():
    """示例5: 与旧方案对比."""
    print("\n" + "="*60)
    print("示例5: 新旧方案对比")
    print("="*60)

    import time

    # 旧方案 (Naive RAG)
    print("\n[旧方案] Naive RAG")
    from rag.pipeline import RAGPipeline as OldPipeline

    old_pipeline = OldPipeline(index_path="rag/index")
    old_start = time.time()
    old_result = old_pipeline.run(
        image_path="media/uploads/test.jpg",
        script_type="汉文古籍",
        hint="明刻本",
        k=3
    )
    old_time = time.time() - old_start

    print(f"检索结果: {old_result.get('num_references', 0)} 条")
    print(f"耗时: {old_time:.2f}s")

    # 新方案 (Modern RAG)
    print("\n[新方案] Modern RAG")
    from rag.modern import ModernRAGPipeline

    new_pipeline = ModernRAGPipeline()
    new_start = time.time()
    new_result = new_pipeline.run(
        image_path="media/uploads/test.jpg",
        ocr_text="",
        metadata={"edition_type": "刻本", "dynasty": "明"}
    )
    new_time = time.time() - new_start

    print(f"检索结果: {new_result['retrieval']['num_results']} 条")
    print(f"耗时: {new_time:.2f}s")

    # 对比
    print("\n" + "-"*60)
    print("对比总结:")
    print(f"  检索数量: 旧={old_result.get('num_references', 0)} vs 新={new_result['retrieval']['num_results']}")
    print(f"  处理时间: 旧={old_time:.2f}s vs 新={new_time:.2f}s")
    print(f"  结构化输出: 旧=否 vs 新=是")
    print(f"  多阶段推理: 旧=否 vs 新=是")
    print(f"  混合检索: 旧=否 vs 新=是")


def main():
    """运行所有示例."""
    print("\n" + "="*60)
    print("现代RAG系统使用示例")
    print("="*60)

    # 示例1: 构建索引（首次运行需要）
    # example_1_build_index()

    # 示例2: 处理单张图片
    example_2_single_image()

    # 示例3: 批量处理
    # example_3_batch_processing()

    # 示例4: 自定义配置
    # example_4_custom_config()

    # 示例5: 新旧对比
    # example_5_compare_with_old()


if __name__ == "__main__":
    main()
