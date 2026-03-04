# OCR 模块

看典古籍 OCR API 客户端（重构版 v2.0）

## 主要改进

### 1. 模块化设计
- `client.py`: API 客户端核心逻辑
- `config.py`: 配置管理（支持环境变量）
- `models.py`: 数据模型（OCRResult, TextLine, WordInfo）
- `output.py`: 输出管理（支持多种格式和目录结构）
- `exceptions.py`: 异常定义（细分错误类型）
- `utils.py`: 工具函数（验证、哈希、统计）
- `cli.py`: 命令行工具

### 2. 优化的输出结构

```
outputs/
└── {image_name}/
    ├── raw/                    # 原始 API 响应
    │   └── {image_name}_raw.json
    ├── text/                   # 纯文本输出
    │   └── {image_name}.txt
    ├── overlay/                # 标注图片
    │   └── {image_name}_overlay.jpg
    ├── {image_name}.json       # 结构化结果
    └── metadata.json           # 元数据（统计信息、时间戳等）
```

### 3. 增强的功能
- 完善的错误处理和日志记录
- 支持批量处理和进度估算
- 图片文件验证
- 结果统计分析
- 灵活的配置管理

## 快速开始

### 环境配置

```bash
# 设置环境变量
export KANDIANGUJI_TOKEN="your-token"
export KANDIANGUJI_EMAIL="your-email"
```

### 基础用法

```python
from ocr import KandiangujiOCRClient

# 使用环境变量配置
client = KandiangujiOCRClient()

# 识别图片
result = client.recognize_image("ancient_text.jpg")

# 获取文本
print(result.get_full_text())

# 查看统计
print(f"识别行数: {result.get_text_count()}")
print(f"平均置信度: {result.get_average_confidence():.2%}")
print(f"是否竖排: {result.is_vertical_text()}")
```

### 保存输出

```python
from pathlib import Path
from ocr import KandiangujiOCRClient, OCROutputManager

client = KandiangujiOCRClient()
output_mgr = OCROutputManager(Path("outputs"))

image_path = Path("ancient_text.jpg")
result = client.recognize_image(image_path)

# 保存所有格式（JSON、TXT、标注图片、元数据）
saved_files = output_mgr.save_all(image_path, result)
print(f"已保存: {saved_files}")
```

### 自定义配置

```python
from pathlib import Path
from ocr import KandiangujiOCRClient, OCRConfig

config = OCRConfig(
    token="your-token",
    email="your-email",
    timeout=120,
    output_dir=Path("custom_outputs"),
    det_mode="auto",
    return_position=True,
)

client = KandiangujiOCRClient(config)
```

## 命令行工具

### 识别单张图片

```bash
# 基础识别（输出到终端）
python -m ocr.cli recognize test.jpg

# 保存为文本文件
python -m ocr.cli recognize test.jpg -o result.txt

# 保存所有格式
python -m ocr.cli recognize test.jpg --save-all --output-dir outputs
```

### 批量识别

```bash
# 批量处理多张图片
python -m ocr.cli batch images/*.jpg --output-dir outputs

# 指定 Token（不使用环境变量）
python -m ocr.cli batch images/*.jpg \
  --token your-token \
  --email your-email \
  --output-dir outputs
```

### 查询 Token 状态

```bash
python -m ocr.cli status
```

## API 参考

### OCRResult 对象

```python
result = client.recognize_image("test.jpg")

# 属性
result.text_lines          # List[TextLine]: 文本行列表
result.width               # int: 图片宽度
result.height              # int: 图片高度
result.text_angel          # int: 文本方向（0=横排，1=竖排）
result.text_angel_confidence  # float: 方向置信度

# 方法
result.get_full_text()           # 获取完整文本
result.get_text_count()          # 获取文本行数
result.get_average_confidence()  # 获取平均置信度
result.is_vertical_text()        # 判断是否竖排
result.to_dict()                 # 转换为字典
```

### TextLine 对象

```python
line = result.text_lines[0]

# 属性
line.text          # str: 文本内容
line.position      # List[List[int]]: 四边形坐标
line.words         # List[WordInfo]: 单字列表
line.confidence    # Optional[float]: 置信度

# 方法
line.get_bbox()    # 获取边界框 [x_min, y_min, x_max, y_max]
```

### WordInfo 对象

```python
word = line.words[0]

# 属性
word.text              # str: 文字
word.confidence        # float: 识别置信度
word.det_confidence    # float: 检测置信度
word.position          # List[int]: 位置 [x1, y1, x2, y2]
```

## 错误处理

```python
from ocr import KandiangujiOCRClient
from ocr.exceptions import (
    OCRAPIError,
    OCRAuthError,
    OCRFileError,
    OCRTimeoutError,
)

try:
    client = KandiangujiOCRClient()
    result = client.recognize_image("test.jpg")

except OCRFileError as e:
    print(f"文件错误: {e}")

except OCRAuthError as e:
    print(f"认证失败: {e}")

except OCRTimeoutError as e:
    print(f"请求超时: {e}")

except OCRAPIError as e:
    print(f"API 错误: {e}")
    if e.status_code:
        print(f"状态码: {e.status_code}")
```

## 批量处理示例

```python
from pathlib import Path
from ocr import KandiangujiOCRClient, OCROutputManager
from ocr.utils import batch_validate_images, estimate_processing_time

# 准备图片列表
image_paths = list(Path("images").glob("*.jpg"))

# 验证文件
valid_files, invalid_files = batch_validate_images(image_paths)
print(f"有效: {len(valid_files)}, 无效: {len(invalid_files)}")

# 估算时间
print(f"预计耗时: {estimate_processing_time(len(valid_files))}")

# 批量处理
client = KandiangujiOCRClient()
output_mgr = OCROutputManager(Path("outputs"))

for i, image_path in enumerate(valid_files, 1):
    print(f"[{i}/{len(valid_files)}] {image_path.name}")
    try:
        result = client.recognize_image(image_path)
        output_mgr.save_all(image_path, result)
        print(f"  ✓ 成功")
    except Exception as e:
        print(f"  ✗ 失败: {e}")
```

## 更多示例

查看 `examples.py` 文件获取更多使用示例：

```bash
python ocr/examples.py
```

## 迁移指南（从旧版本）

### 旧版本
```python
from ocr.ocr import KandiangujiOCRClient, save_ocr_outputs, draw_overlay

client = KandiangujiOCRClient(token="xxx", email="xxx")
result = client.recognize_image(image_base64)
save_ocr_outputs(result, image_path, output_dir)
draw_overlay(image_path, result)
```

### 新版本
```python
from ocr import KandiangujiOCRClient, OCROutputManager, OCRConfig

config = OCRConfig(token="xxx", email="xxx")
client = KandiangujiOCRClient(config)
result = client.recognize_image(image_path)  # 直接传路径

output_mgr = OCROutputManager(output_dir)
output_mgr.save_all(image_path, result)  # 一次保存所有格式
```

## 注意事项

1. **环境变量优先**: 建议使用环境变量配置 Token 和 Email
2. **文件大小限制**: 默认最大 10MB，可通过 `validate_image_file()` 调整
3. **输出目录**: 自动创建，支持嵌套结构
4. **错误重试**: 客户端不自动重试，需要在应用层实现
5. **并发限制**: 注意 API 的并发限制和配额

## 依赖

- Python 3.10+
- requests
- Pillow

## 许可证

MIT License
