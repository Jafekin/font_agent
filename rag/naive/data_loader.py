"""NaiveRAG 数据加载器：扫描 rag/data/ 目录，加载 OCR 结果与统一元数据 schema。

目录结构（每页一个目录）：
    data/
    └── {图片名}/
        ├── {图片名}.json              # OCR text_lines 结构
        ├── metadata.json             # OCR 统计 + 图片信息
        ├── extended_metadata.json    # 版本/机构/作者等元数据
        ├── raw/{图片名}_raw.json     # 原始 OCR 响应
        ├── text/{图片名}.txt         # 清洗后纯文本
        └── overlay/{图片名}_overlay.jpg
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PrintingInfo:
    dynasty_period: Optional[str] = None   # 朝代/时期，如"宋"
    printer: Optional[str] = None          # 刻印者或书坊


@dataclass
class EditionMetadata:
    edition_dir: str = ""                              # 版本目录名
    version_type: str = ""                             # A/B/C/D/E
    annotation_system: Optional[str] = None            # 集解 | 集解+索隐 | 三家注
    printing_info: PrintingInfo = field(default_factory=PrintingInfo)
    total_juan: Optional[int] = None                   # 全书总卷数
    extant_juan: Optional[str] = None                  # 现存卷数说明
    holding_institution: Optional[str] = None          # 收藏机构
    catalog_id_main: Optional[str] = None              # 主编目号
    catalog_id_secondary: Optional[str] = None         # 副编目号
    authors: List[str] = field(default_factory=list)
    annotators: List[str] = field(default_factory=list)
    peiben_notes: Optional[str] = None                 # 配本说明
    colophon_authors: Optional[str] = None             # 跋文作者
    image_files: List[str] = field(default_factory=list)


@dataclass
class OcrStatistics:
    line_count: int = 0
    average_confidence: float = 0.0
    is_vertical: bool = True
    image_width: int = 0
    image_height: int = 0


@dataclass
class PageData:
    """单页 OCR 处理结果，包含文本内容与完整元数据。"""

    page_id: str                                           # 目录名（唯一标识）
    page_dir: Path                                         # 目录路径
    ocr_lines: List[str] = field(default_factory=list)     # 每行 OCR 识别文本
    full_text: str = ""                                    # 清洗后纯文本
    source_image: str = ""                                 # 原始图片相对路径
    overlay_image: Optional[Path] = None                   # overlay 图片路径
    ocr_stats: OcrStatistics = field(default_factory=OcrStatistics)
    edition: EditionMetadata = field(default_factory=EditionMetadata)

    def to_text_info(self, max_chars: int = 800) -> str:
        """生成供向量化的文字信息摘要。"""
        parts: List[str] = []
        e = self.edition

        if e.version_type:
            parts.append(f"版本类型: {e.version_type}")
        if e.annotation_system:
            parts.append(f"注释体系: {e.annotation_system}")
        pi = e.printing_info
        if pi.dynasty_period:
            parts.append(f"朝代/时期: {pi.dynasty_period}")
        if pi.printer:
            parts.append(f"刻印者: {pi.printer}")
        if e.total_juan:
            parts.append(f"全书卷数: {e.total_juan}卷")
        if e.extant_juan:
            parts.append(f"现存卷数: {e.extant_juan}")
        if e.holding_institution:
            parts.append(f"收藏机构: {e.holding_institution}")
        if e.catalog_id_main:
            cat = e.catalog_id_main
            if e.catalog_id_secondary:
                cat = f"{e.catalog_id_secondary}{cat}"
            parts.append(f"编目号: {cat}")
        if e.authors:
            parts.append(f"著者: {'、'.join(e.authors)}")
        if e.annotators:
            parts.append(f"注释者: {'、'.join(e.annotators)}")
        if e.peiben_notes:
            parts.append(f"配本说明: {e.peiben_notes}")
        if e.colophon_authors:
            parts.append(f"跋文作者: {e.colophon_authors}")

        summary = "。".join(parts)

        if self.full_text:
            preview = self.full_text[:300].replace("\n", " ")
            summary = summary + ("。" if summary else "") + f"本页文字节选: {preview}"

        return summary[:max_chars]

    def to_metadata_dict(self) -> Dict[str, Any]:
        """生成可序列化的元数据字典（写入 metadata.json 索引）。"""
        e = self.edition
        return {
            "page_id": self.page_id,
            "source_image": self.source_image,
            "overlay_image": str(self.overlay_image) if self.overlay_image else "",
            "edition_dir": e.edition_dir,
            "version_type": e.version_type,
            "annotation_system": e.annotation_system or "",
            "dynasty_period": e.printing_info.dynasty_period or "",
            "printer": e.printing_info.printer or "",
            "total_juan": e.total_juan if e.total_juan is not None else "",
            "extant_juan": e.extant_juan or "",
            "holding_institution": e.holding_institution or "",
            "catalog_id_main": e.catalog_id_main or "",
            "catalog_id_secondary": e.catalog_id_secondary or "",
            "authors": "、".join(e.authors),
            "annotators": "、".join(e.annotators),
            "peiben_notes": e.peiben_notes or "",
            "colophon_authors": e.colophon_authors or "",
            "ocr_line_count": self.ocr_stats.line_count,
            "ocr_avg_confidence": round(self.ocr_stats.average_confidence, 4),
            "is_vertical": self.ocr_stats.is_vertical,
        }


def _clean_null(value: Any) -> Optional[str]:
    """将字符串 'null'/'None' 转换为 None。"""
    if value is None:
        return None
    s = str(value).strip()
    return None if s.lower() in ("null", "none", "") else s


def _parse_printing_info(raw: Dict[str, Any]) -> PrintingInfo:
    return PrintingInfo(
        dynasty_period=_clean_null(raw.get("dynasty_period")),
        printer=_clean_null(raw.get("printer")),
    )


def _parse_edition_metadata(raw: Dict[str, Any]) -> EditionMetadata:
    em = raw.get("edition_metadata", raw)
    printing_raw = em.get("printing_info", {}) or {}
    image_files = em.get("image_files", []) or []
    if not isinstance(image_files, list):
        image_files = [image_files]

    total_juan = em.get("total_juan")
    if total_juan is not None:
        try:
            total_juan = int(total_juan)
        except (ValueError, TypeError):
            total_juan = None

    authors = em.get("authors", []) or []
    annotators = em.get("annotators", []) or []

    return EditionMetadata(
        edition_dir=em.get("edition_dir", ""),
        version_type=em.get("version_type", ""),
        annotation_system=_clean_null(em.get("annotation_system")),
        printing_info=_parse_printing_info(printing_raw),
        total_juan=total_juan,
        extant_juan=_clean_null(em.get("extant_juan")),
        holding_institution=_clean_null(em.get("holding_institution")),
        catalog_id_main=_clean_null(em.get("catalog_id_main")),
        catalog_id_secondary=_clean_null(em.get("catalog_id_secondary")),
        authors=[a for a in authors if _clean_null(a)],
        annotators=[a for a in annotators if _clean_null(a)],
        peiben_notes=_clean_null(em.get("peiben_notes")),
        colophon_authors=_clean_null(em.get("colophon_authors")),
        image_files=[str(f) for f in image_files if f],
    )


class NaiveDataLoader:
    """扫描 rag/data/ 目录，按页加载所有 OCR 结果与元数据。

    每个子目录代表一页，包含：
    - {name}.json         → OCR text_lines
    - metadata.json       → 统计信息与原始图片路径
    - extended_metadata.json → 版本/机构/作者元数据
    - text/{name}.txt     → 清洗后纯文本
    - overlay/{name}_overlay.jpg → 叠加注释图
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")

    def scan_pages(self) -> List[PageData]:
        """扫描数据目录，返回所有页面数据列表（按目录名排序）。"""
        pages: List[PageData] = []
        dirs = sorted(
            [d for d in self.data_dir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
        )
        for page_dir in dirs:
            try:
                page = self._load_page(page_dir)
                if page is not None:
                    pages.append(page)
            except Exception as exc:
                logger.warning("跳过目录 %s: %s", page_dir.name, exc)

        logger.info("共加载 %d 页数据（来自 %s）", len(pages), self.data_dir)
        return pages

    def _load_page(self, page_dir: Path) -> Optional[PageData]:
        """加载单个页目录中的所有数据文件。"""
        page_id = page_dir.name

        # 1. 查找主 OCR JSON（非 metadata/extended_metadata）
        ocr_json_path = self._find_main_json(page_dir)
        ocr_lines: List[str] = []
        if ocr_json_path and ocr_json_path.exists():
            try:
                with open(ocr_json_path, "r", encoding="utf-8") as f:
                    ocr_data = json.load(f)
                text_lines = ocr_data.get("text_lines", [])
                ocr_lines = [
                    line["text"]
                    for line in text_lines
                    if isinstance(line, dict) and line.get("text")
                ]
            except Exception as exc:
                logger.debug("读取 OCR JSON 失败 %s: %s", ocr_json_path, exc)

        # 2. 读取清洗后纯文本
        full_text = ""
        text_dir = page_dir / "text"
        if text_dir.exists():
            txt_files = list(text_dir.glob("*.txt"))
            if txt_files:
                try:
                    full_text = txt_files[0].read_text(encoding="utf-8").strip()
                except Exception as exc:
                    logger.debug("读取 txt 失败 %s: %s", txt_files[0], exc)

        # 3. 读取 metadata.json（基础统计）
        source_image = ""
        ocr_stats = OcrStatistics()
        metadata_path = page_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                source_image = meta.get("source_image", "")
                stats = meta.get("statistics", {}) or {}
                image_size = stats.get("image_size", {}) or {}
                ocr_stats = OcrStatistics(
                    line_count=int(stats.get("line_count", 0)),
                    average_confidence=float(stats.get("average_confidence", 0.0)),
                    is_vertical=bool(stats.get("is_vertical", True)),
                    image_width=int(image_size.get("width", 0)),
                    image_height=int(image_size.get("height", 0)),
                )
            except Exception as exc:
                logger.debug("读取 metadata.json 失败 %s: %s", page_dir, exc)

        # 4. 读取 extended_metadata.json（版本/机构元数据）
        edition = EditionMetadata()
        ext_meta_path = page_dir / "extended_metadata.json"
        if ext_meta_path.exists():
            try:
                with open(ext_meta_path, "r", encoding="utf-8") as f:
                    ext_meta = json.load(f)
                edition = _parse_edition_metadata(ext_meta)
                # 如果 source_image 未从 metadata.json 取到，则从 extended_metadata 补充
                if not source_image:
                    source_image = ext_meta.get("image_file", "")
            except Exception as exc:
                logger.debug("读取 extended_metadata.json 失败 %s: %s", page_dir, exc)

        # 5. 查找 overlay 图片
        overlay_image: Optional[Path] = None
        overlay_dir = page_dir / "overlay"
        if overlay_dir.exists():
            overlays = list(overlay_dir.glob("*_overlay.jpg"))
            if overlays:
                overlay_image = overlays[0]

        return PageData(
            page_id=page_id,
            page_dir=page_dir,
            ocr_lines=ocr_lines,
            full_text=full_text,
            source_image=source_image,
            overlay_image=overlay_image,
            ocr_stats=ocr_stats,
            edition=edition,
        )

    @staticmethod
    def _find_main_json(page_dir: Path) -> Optional[Path]:
        """在目录中找到主 OCR JSON（排除 metadata.json / extended_metadata.json / raw/）。"""
        excluded = {"metadata.json", "extended_metadata.json"}
        for json_file in sorted(page_dir.glob("*.json")):
            if json_file.name not in excluded:
                return json_file
        return None
