"""OCR 结果数据模型."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WordInfo:
    """单字识别信息."""

    text: str
    confidence: float
    det_confidence: float
    position: List[int]  # [x1, y1, x2, y2]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WordInfo:
        """从字典创建实例."""
        return cls(
            text=data.get("text", ""),
            confidence=data.get("confidence", 0.0),
            det_confidence=data.get("det_confidence", 0.0),
            position=data.get("position", []),
        )


@dataclass
class TextLine:
    """文本行识别信息."""

    text: str
    position: List[List[int]]  # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    words: List[WordInfo] = field(default_factory=list)
    confidence: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TextLine:
        """从字典创建实例."""
        words_data = data.get("words", [])
        words = [WordInfo.from_dict(w) for w in words_data]

        return cls(
            text=data.get("text", ""),
            position=data.get("position", []),
            words=words,
            confidence=data.get("confidence"),
        )

    def get_bbox(self) -> Optional[List[int]]:
        """获取文本行的边界框 [x_min, y_min, x_max, y_max]."""
        if not self.position or len(self.position) < 2:
            return None

        xs = [pt[0] for pt in self.position]
        ys = [pt[1] for pt in self.position]
        return [min(xs), min(ys), max(xs), max(ys)]


@dataclass
class OCRResult:
    """OCR 识别结果."""

    text_lines: List[TextLine]
    width: int
    height: int
    text_angel: int  # 文本方向：0=横排，1=竖排
    text_angel_confidence: float
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, response: Dict[str, Any]) -> OCRResult:
        """从 API 响应创建实例."""
        data = response.get("data", {})
        text_lines_data = data.get("text_lines", [])
        text_lines = [TextLine.from_dict(line) for line in text_lines_data]

        return cls(
            text_lines=text_lines,
            width=data.get("width", 0),
            height=data.get("height", 0),
            text_angel=data.get("text_angel", 0),
            text_angel_confidence=data.get("text_angel_confidence", 0.0),
            raw_data=response,
        )

    def get_full_text(self, separator: str = "\n") -> str:
        """获取完整文本."""
        return separator.join(line.text for line in self.text_lines if line.text)

    def get_text_count(self) -> int:
        """获取识别的文本行数."""
        return len(self.text_lines)

    def get_average_confidence(self) -> float:
        """获取平均置信度."""
        confidences = []
        for line in self.text_lines:
            for word in line.words:
                confidences.append(word.confidence)

        return sum(confidences) / len(confidences) if confidences else 0.0

    def is_vertical_text(self) -> bool:
        """判断是否为竖排文本."""
        return self.text_angel == 1

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "text_lines": [
                {
                    "text": line.text,
                    "position": line.position,
                    "words": [
                        {
                            "text": w.text,
                            "confidence": w.confidence,
                            "det_confidence": w.det_confidence,
                            "position": w.position,
                        }
                        for w in line.words
                    ],
                }
                for line in self.text_lines
            ],
            "width": self.width,
            "height": self.height,
            "text_angel": self.text_angel,
            "text_angel_confidence": self.text_angel_confidence,
            "statistics": {
                "line_count": self.get_text_count(),
                "average_confidence": self.get_average_confidence(),
                "is_vertical": self.is_vertical_text(),
            },
        }


@dataclass
class PDFTaskStatus:
    """PDF OCR 任务状态."""

    task_id: str
    status: str  # "processing", "completed", "failed"
    progress: float  # 0.0 - 1.0
    message: Optional[str] = None
    code: Optional[str] = None  # 下载码

    @classmethod
    def from_api_response(cls, response: Dict[str, Any]) -> PDFTaskStatus:
        """从 API 响应创建实例."""
        return cls(
            task_id=response.get("task_id", ""),
            status=response.get("status", "unknown"),
            progress=response.get("progress", 0.0),
            message=response.get("message"),
            code=response.get("code"),
        )

    def is_completed(self) -> bool:
        """判断任务是否完成."""
        return self.status == "completed"

    def is_failed(self) -> bool:
        """判断任务是否失败."""
        return self.status == "failed"

    def is_processing(self) -> bool:
        """判断任务是否处理中."""
        return self.status == "processing"
