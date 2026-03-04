"""OCR 模块使用示例.

演示如何使用重构后的 OCR 模块进行古籍文字识别。
"""

from pathlib import Path

from ocr import (
    KandiangujiOCRClient,
    OCRConfig,
    OCROutputManager,
)


def example_basic_usage():
    """示例 1: 基础用法 - 使用环境变量配置."""
    print("=" * 60)
    print("示例 1: 基础用法")
    print("=" * 60)

    # 从环境变量加载配置
    client = KandiangujiOCRClient()

    # 识别图片
    image_path = Path("ocr/test/test2.jpg")
    result = client.recognize_image(image_path)

    # 输出结果
    print(f"\n识别完成:")
    print(f"  文本行数: {result.get_text_count()}")
    print(f"  平均置信度: {result.get_average_confidence():.2%}")
    print(f"  文本方向: {'竖排' if result.is_vertical_text() else '横排'}")
    print(f"\n前 5 行文本:")
    lines = result.get_full_text().split("\n")[:5]
    for i, line in enumerate(lines, 1):
        print(f"  {i}. {line}")


def example_custom_config():
    """示例 2: 自定义配置."""
    print("\n" + "=" * 60)
    print("示例 2: 自定义配置")
    print("=" * 60)

    # 创建自定义配置
    config = OCRConfig(
        token="your-token-here",
        email="your-email@example.com",
        timeout=120,  # 增加超时时间
        output_dir=Path("custom_outputs"),
        det_mode="auto",
        return_position=True,
    )

    client = KandiangujiOCRClient(config)
    print(f"\n配置信息:")
    print(f"  超时时间: {config.timeout}s")
    print(f"  输出目录: {config.output_dir}")
    print(f"  检测模式: {config.det_mode}")


def example_save_outputs():
    """示例 3: 保存多种格式的输出."""
    print("\n" + "=" * 60)
    print("示例 3: 保存输出文件")
    print("=" * 60)

    client = KandiangujiOCRClient()
    output_mgr = OCROutputManager(Path("ocr/outputs"))

    image_path = Path("ocr/tests/test.jpg")
    result = client.recognize_image(image_path)

    # 保存所有格式
    saved_files = output_mgr.save_all(image_path, result)

    print(f"\n已保存以下文件:")
    for file_type, file_path in saved_files.items():
        print(f"  {file_type:12s}: {file_path}")


def example_custom_output():
    """示例 4: 自定义输出选项."""
    print("\n" + "=" * 60)
    print("示例 4: 自定义输出")
    print("=" * 60)

    client = KandiangujiOCRClient()
    output_mgr = OCROutputManager(Path("ocr/outputs_v2"))

    image_path = Path("ocr/tests/test2.jpg")
    result = client.recognize_image(image_path)

    # 只保存 JSON
    json_path = output_mgr.save_json(
        result,
        Path("ocr/outputs_v2/custom_result.json"),
        pretty=True,
    )
    print(f"\nJSON 已保存到: {json_path}")

    # 保存自定义样式的标注图片
    overlay_path = output_mgr.save_overlay_image(
        image_path,
        result,
        Path("ocr/outputs_v2/custom_overlay.jpg"),
        line_color="blue",
        line_width=3,
        text_color="green",
        show_text=True,
    )
    print(f"标注图片已保存到: {overlay_path}")


def example_error_handling():
    """示例 5: 错误处理."""
    print("\n" + "=" * 60)
    print("示例 5: 错误处理")
    print("=" * 60)

    from ocr.exceptions import OCRAPIError, OCRAuthError, OCRFileError

    try:
        # 尝试识别不存在的文件
        client = KandiangujiOCRClient()
        result = client.recognize_image("non_existent.jpg")

    except OCRFileError as e:
        print(f"\n文件错误: {e}")

    except OCRAuthError as e:
        print(f"\n认证错误: {e}")

    except OCRAPIError as e:
        print(f"\nAPI 错误: {e}")
        if e.status_code:
            print(f"  状态码: {e.status_code}")

    except Exception as e:
        print(f"\n未知错误: {e}")


def example_batch_processing():
    """示例 6: 批量处理."""
    print("\n" + "=" * 60)
    print("示例 6: 批量处理")
    print("=" * 60)

    from ocr.utils import batch_validate_images, estimate_processing_time

    # 准备图片列表
    image_dir = Path("ocr")
    image_paths = list(image_dir.glob("test*.jpg"))

    print(f"\n找到 {len(image_paths)} 张图片")

    # 验证文件
    valid_files, invalid_files = batch_validate_images(image_paths)
    print(f"有效文件: {len(valid_files)}")
    print(f"无效文件: {len(invalid_files)}")

    if invalid_files:
        print("\n无效文件:")
        for path, reason in invalid_files:
            print(f"  {path.name}: {reason}")

    # 估算处理时间
    if valid_files:
        estimated_time = estimate_processing_time(len(valid_files))
        print(f"\n预计处理时间: {estimated_time}")

        # 批量处理
        client = KandiangujiOCRClient()
        output_mgr = OCROutputManager(Path("ocr/outputs_v2/batch"))

        for i, image_path in enumerate(valid_files, 1):
            print(f"\n[{i}/{len(valid_files)}] 处理: {image_path.name}")
            try:
                result = client.recognize_image(image_path)
                output_mgr.save_all(image_path, result)
                print(f"  ✓ 成功 (识别 {result.get_text_count()} 行)")
            except Exception as e:
                print(f"  ✗ 失败: {e}")


def example_result_analysis():
    """示例 7: 结果分析."""
    print("\n" + "=" * 60)
    print("示例 7: 结果分析")
    print("=" * 60)

    client = KandiangujiOCRClient()
    image_path = Path("ocr/test2.jpg")
    result = client.recognize_image(image_path)

    print(f"\n详细统计:")
    print(f"  图片尺寸: {result.width} x {result.height}")
    print(f"  文本行数: {result.get_text_count()}")
    print(f"  平均置信度: {result.get_average_confidence():.2%}")
    print(f"  文本方向: {'竖排' if result.is_vertical_text() else '横排'}")
    print(f"  方向置信度: {result.text_angel_confidence:.2%}")

    # 分析每行的置信度
    print(f"\n前 5 行详细信息:")
    for i, line in enumerate(result.text_lines[:5], 1):
        word_confidences = [w.confidence for w in line.words]
        avg_conf = sum(word_confidences) / \
            len(word_confidences) if word_confidences else 0
        print(
            f"  {i}. {line.text[:20]:20s} (置信度: {avg_conf:.2%}, {len(line.words)} 字)")


def example_token_status():
    """示例 8: 查询 Token 状态."""
    print("\n" + "=" * 60)
    print("示例 8: 查询 Token 状态")
    print("=" * 60)

    try:
        client = KandiangujiOCRClient()
        status = client.get_token_status()

        print(f"\nToken 状态:")
        import json
        print(json.dumps(status, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"\n查询失败: {e}")


def main():
    """运行所有示例."""
    print("\n" + "=" * 60)
    print("OCR 模块使用示例")
    print("=" * 60)

    examples = [
        ("基础用法", example_basic_usage),
        ("自定义配置", example_custom_config),
        ("保存输出", example_save_outputs),
        ("自定义输出", example_custom_output),
        ("错误处理", example_error_handling),
        ("批量处理", example_batch_processing),
        ("结果分析", example_result_analysis),
        ("Token 状态", example_token_status),
    ]

    print("\n可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\n提示: 修改代码以运行特定示例")
    print("=" * 60)

    # 运行示例（取消注释以运行）
    # example_basic_usage()
    # example_custom_config()
    example_save_outputs()
    # example_custom_output()
    # example_error_handling()
    # example_batch_processing()
    # example_result_analysis()
    # example_token_status()


if __name__ == "__main__":
    main()
