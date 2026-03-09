"""图谱数据模型定义."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    """文献实体."""

    doc_id: str
    title: str
    author: Optional[str] = None
    dynasty: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "author": self.author,
            "dynasty": self.dynasty,
            "category": self.category,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Document:
        """从字典创建实例."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")

        return cls(
            doc_id=data["doc_id"],
            title=data["title"],
            author=data.get("author"),
            dynasty=data.get("dynasty"),
            category=data.get("category"),
            description=data.get("description"),
            created_at=datetime.fromisoformat(
                created_at) if created_at else None,
            updated_at=datetime.fromisoformat(
                updated_at) if updated_at else None,
        )


@dataclass
class Volume:
    """卷次实体."""

    volume_id: str
    volume_number: int
    volume_title: Optional[str] = None
    page_count: Optional[int] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "volume_id": self.volume_id,
            "volume_number": self.volume_number,
            "volume_title": self.volume_title,
            "page_count": self.page_count,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Volume:
        """从字典创建实例."""
        return cls(
            volume_id=data["volume_id"],
            volume_number=data["volume_number"],
            volume_title=data.get("volume_title"),
            page_count=data.get("page_count"),
            description=data.get("description"),
        )


@dataclass
class Page:
    """页面实体."""

    page_id: str
    page_number: int
    image_path: str
    image_hash: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    text_direction: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "page_id": self.page_id,
            "page_number": self.page_number,
            "image_path": self.image_path,
            "image_hash": self.image_hash,
            "ocr_text": self.ocr_text,
            "ocr_confidence": self.ocr_confidence,
            "text_direction": self.text_direction,
            "width": self.width,
            "height": self.height,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Page:
        """从字典创建实例."""
        created_at = data.get("created_at")

        return cls(
            page_id=data["page_id"],
            page_number=data["page_number"],
            image_path=data["image_path"],
            image_hash=data.get("image_hash"),
            ocr_text=data.get("ocr_text"),
            ocr_confidence=data.get("ocr_confidence"),
            text_direction=data.get("text_direction"),
            width=data.get("width"),
            height=data.get("height"),
            created_at=datetime.fromisoformat(
                created_at) if created_at else None,
        )


@dataclass
class Edition:
    """版本实体."""

    edition_id: str
    edition_type: str
    edition_name: Optional[str] = None
    publisher: Optional[str] = None
    publish_year: Optional[str] = None
    publish_place: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "edition_id": self.edition_id,
            "edition_type": self.edition_type,
            "edition_name": self.edition_name,
            "publisher": self.publisher,
            "publish_year": self.publish_year,
            "publish_place": self.publish_place,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Edition:
        """从字典创建实例."""
        return cls(
            edition_id=data["edition_id"],
            edition_type=data["edition_type"],
            edition_name=data.get("edition_name"),
            publisher=data.get("publisher"),
            publish_year=data.get("publish_year"),
            publish_place=data.get("publish_place"),
            description=data.get("description"),
        )


@dataclass
class Collection:
    """馆藏实体."""

    collection_id: str
    institution: str
    call_number: Optional[str] = None
    location: Optional[str] = None
    acquisition_date: Optional[str] = None
    condition: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "collection_id": self.collection_id,
            "institution": self.institution,
            "call_number": self.call_number,
            "location": self.location,
            "acquisition_date": self.acquisition_date,
            "condition": self.condition,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Collection:
        """从字典创建实例."""
        return cls(
            collection_id=data["collection_id"],
            institution=data["institution"],
            call_number=data.get("call_number"),
            location=data.get("location"),
            acquisition_date=data.get("acquisition_date"),
            condition=data.get("condition"),
            notes=data.get("notes"),
        )


@dataclass
class Layout:
    """版式实体."""

    layout_id: str
    column_count: Optional[int] = None
    line_count: Optional[int] = None
    chars_per_line: Optional[float] = None
    border_type: Optional[str] = None
    border_color: Optional[str] = None
    has_fish_tail: Optional[bool] = None
    has_annotation: Optional[bool] = None
    annotation_position: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "layout_id": self.layout_id,
            "column_count": self.column_count,
            "line_count": self.line_count,
            "chars_per_line": self.chars_per_line,
            "border_type": self.border_type,
            "border_color": self.border_color,
            "has_fish_tail": self.has_fish_tail,
            "has_annotation": self.has_annotation,
            "annotation_position": self.annotation_position,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Layout:
        """从字典创建实例."""
        return cls(
            layout_id=data["layout_id"],
            column_count=data.get("column_count"),
            line_count=data.get("line_count"),
            chars_per_line=data.get("chars_per_line"),
            border_type=data.get("border_type"),
            border_color=data.get("border_color"),
            has_fish_tail=data.get("has_fish_tail"),
            has_annotation=data.get("has_annotation"),
            annotation_position=data.get("annotation_position"),
        )


@dataclass
class Seal:
    """钤印实体."""

    seal_id: str
    seal_text: Optional[str] = None
    seal_type: Optional[str] = None
    owner: Optional[str] = None
    shape: Optional[str] = None
    color: Optional[str] = None
    position: Optional[str] = None
    image_embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "seal_id": self.seal_id,
            "seal_text": self.seal_text,
            "seal_type": self.seal_type,
            "owner": self.owner,
            "shape": self.shape,
            "color": self.color,
            "position": self.position,
            "image_embedding": self.image_embedding,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Seal:
        """从字典创建实例."""
        return cls(
            seal_id=data["seal_id"],
            seal_text=data.get("seal_text"),
            seal_type=data.get("seal_type"),
            owner=data.get("owner"),
            shape=data.get("shape"),
            color=data.get("color"),
            position=data.get("position"),
            image_embedding=data.get("image_embedding"),
        )


@dataclass
class Entity:
    """实体词条."""

    entity_id: str
    entity_text: str
    entity_type: str
    normalized_name: Optional[str] = None
    description: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    birth_year: Optional[str] = None
    death_year: Optional[str] = None
    dynasty: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "entity_id": self.entity_id,
            "entity_text": self.entity_text,
            "entity_type": self.entity_type,
            "normalized_name": self.normalized_name,
            "description": self.description,
            "aliases": self.aliases,
            "birth_year": self.birth_year,
            "death_year": self.death_year,
            "dynasty": self.dynasty,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Entity:
        """从字典创建实例."""
        return cls(
            entity_id=data["entity_id"],
            entity_text=data["entity_text"],
            entity_type=data["entity_type"],
            normalized_name=data.get("normalized_name"),
            description=data.get("description"),
            aliases=data.get("aliases", []),
            birth_year=data.get("birth_year"),
            death_year=data.get("death_year"),
            dynasty=data.get("dynasty"),
        )
