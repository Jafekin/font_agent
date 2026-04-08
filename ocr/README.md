# OCR 模块

看典古籍 OCR API 客户端，支持古籍页面识别、版式分析与多格式输出。

## 模块结构

| 文件 | 功能 |
| --- | --- |
| `client.py` | API 客户端核心（识别、鉴权） |
| `config.py` | 配置管理（支持环境变量） |
| `models.py` | 数据模型（OCRResult、TextLine、WordInfo） |
| `output.py` | 多格式输出管理（JSON、TXT、标注图片） |
| `exceptions.py` | 异常类型定义 |
| `utils.py` | 验证、哈希、统计工具函数 |
| `cli.py` | 命令行工具 |

## 输出结构

```
rag/data/{image_name}/
├── {image_name}.json         # 结构化 OCR 结果（text_lines）
├── metadata.json             # 统计信息（行数、置信度、图片尺寸）
├── raw/{image_name}_raw.json # 原始 API 响应
├── text/{image_name}.txt     # 纯文本输出
└── overlay/{image_name}_overlay.jpg  # 标注图片
```

## 环境配置

```bash
export KANDIANGUJI_TOKEN="your-token"
export KANDIANGUJI_EMAIL="your-email"
```

## 命令行

```bash
# 识别单张图片并保存所有格式
python -m ocr.cli recognize ancient_text.jpg --save-all --output-dir rag/data

# 批量识别
python -m ocr.cli batch images/*.jpg --output-dir rag/data

# 查询 Token 状态
python -m ocr.cli status
```

## Python API

```python
from pathlib import Path
from ocr import KandiangujiOCRClient, OCROutputManager

client = KandiangujiOCRClient()
output_mgr = OCROutputManager(Path("rag/data"))

result = client.recognize_image(Path("ancient_text.jpg"))

# 基本信息
print(result.get_full_text())
print(f"行数: {result.get_text_count()}")
print(f"平均置信度: {result.get_average_confidence():.2%}")
print(f"竖排: {result.is_vertical_text()}")

# 保存所有格式
output_mgr.save_all(Path("ancient_text.jpg"), result)
```

### 自定义配置

```python
from ocr import KandiangujiOCRClient, OCRConfig

config = OCRConfig(
    token="your-token",
    email="your-email",
    timeout=120,
    det_mode="auto",
    return_position=True,
)
client = KandiangujiOCRClient(config)
```

## 数据模型

**OCRResult**

```python
result.text_lines            # List[TextLine]
result.width / result.height # 图片尺寸
result.text_angel            # 文本方向（0=横排，1=竖排）
```

**TextLine**

```python
line.text       # str: 行文本
line.position   # List[List[int]]: 四边形坐标
line.words      # List[WordInfo]: 单字信息
line.confidence # float: 置信度
line.get_bbox() # [x_min, y_min, x_max, y_max]
```

**WordInfo**

```python
word.text            # str: 单字
word.confidence      # float: 识别置信度
word.det_confidence  # float: 检测置信度
word.position        # List[int]: [x1, y1, x2, y2]
```

## 错误处理

```python
from ocr.exceptions import OCRAPIError, OCRAuthError, OCRFileError, OCRTimeoutError

try:
    result = client.recognize_image("test.jpg")
except OCRFileError as e:
    print(f"文件错误: {e}")
except OCRAuthError as e:
    print(f"认证失败: {e}")
except OCRTimeoutError as e:
    print(f"请求超时: {e}")
except OCRAPIError as e:
    print(f"API 错误 [{e.status_code}]: {e}")
```

## 注意事项

- 默认最大图片 10MB
- 客户端不自动重试，需在应用层实现
- 注意 API 并发限制与配额
