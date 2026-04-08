"""图谱数据模型定义."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    """文献实体（一部书）."""
    doc_id: str
    title: str
    dynasty: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    annotators: List[str] = field(default_factory=list)
    total_juan: Optional[int] = None
    category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "dynasty": self.dynasty,
            "authors": "、".join(self.authors),
            "annotators": "、".join(self.annotators),
            "total_juan": self.total_juan,
            "category": self.category,
        }


@dataclass
class Edition:
    """版本实体（某一版本的刻本/写本等）."""
    edition_id: str
    version_type: str                      # A/B/C/D/E
    annotation_system: Optional[str] = None  # 集解 | 三家注 等
    dynasty: Optional[str] = None
    printer: Optional[str] = None
    extant_juan: Optional[str] = None
    catalog_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edition_id": self.edition_id,
            "version_type": self.version_type,
            "annotation_system": self.annotation_system,
            "dynasty": self.dynasty,
            "printer": self.printer,
            "extant_juan": self.extant_juan,
            "catalog_id": self.catalog_id,
        }


@dataclass
class Collection:
    """馆藏实体（收藏机构）."""
    collection_id: str
    institution: str
    call_number: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "institution": self.institution,
            "call_number": self.call_number,
        }


@dataclass
class Page:
    """页面实体."""
    page_id: str
    image_path: str
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    is_vertical: bool = True
    width: Optional[int] = None
    height: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "image_path": self.image_path,
            "ocr_text": self.ocr_text,
            "ocr_confidence": self.ocr_confidence,
            "is_vertical": self.is_vertical,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class Layout:
    """版式实体."""
    layout_id: str
    line_count: Optional[int] = None
    has_annotation: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layout_id": self.layout_id,
            "line_count": self.line_count,
            "has_annotation": self.has_annotation,
        }


@dataclass
class Entity:
    """命名实体（人物、地名等）."""
    entity_id: str
    entity_text: str
    entity_type: str   # PERSON | PLACE | TITLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_text": self.entity_text,
            "entity_type": self.entity_type,
        }
