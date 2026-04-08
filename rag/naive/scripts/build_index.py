"""使用 Chinese-CLIP 构建图片+文字信息的 RAG 向量索引（新版）。

与旧版区别：
- 数据源改为 rag/data/ 目录，由 NaiveDataLoader 统一扫描
- 元数据字段来自统一 schema（EditionMetadata / PrintingInfo）
- text_info 由 PageData.to_text_info() 生成
- 可选：使用 overlay 图片代替原始图片进行向量化
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.naive.embeddings import MODEL_NAME, get_image_embedding, get_text_embedding  # noqa: E402
from rag.naive.data_loader import NaiveDataLoader, PageData  # noqa: E402

DEFAULT_DATA_DIR = PROJECT_ROOT / "rag" / "data"
DEFAULT_INDEX_PATH = PROJECT_ROOT / "rag" / "naive" / "index"


def _normalize_vec(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def _combine_embeddings(
    image_vec: np.ndarray,
    text_vec: Optional[np.ndarray],
    weight: float,
) -> np.ndarray:
    if text_vec is None:
        return image_vec
    combined = weight * image_vec + (1.0 - weight) * text_vec
    return _normalize_vec(combined)


def _resolve_image_path(page: PageData, prefer_overlay: bool) -> Optional[Path]:
    """找出最佳图片路径：优先 overlay，其次 source_image。"""
    if prefer_overlay and page.overlay_image and page.overlay_image.exists():
        return page.overlay_image

    if page.source_image:
        # source_image 可能是相对路径（相对于 rag/data 的父目录）
        candidate = Path(page.source_image)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        # 尝试相对于项目根目录
        resolved = PROJECT_ROOT / candidate
        if resolved.exists():
            return resolved
        # 尝试 overlay 作为回退
        if page.overlay_image and page.overlay_image.exists():
            return page.overlay_image

    return None


def build_clip_index(
    pages: List[PageData],
    index_path: Path,
    *,
    model_name: str = MODEL_NAME,
    image_weight: float = 0.65,
    prefer_overlay: bool = True,
) -> None:
    """从 PageData 列表构建 Chinese-CLIP 向量索引。"""
    if not pages:
        raise ValueError("未找到任何页面数据，无法构建索引。")

    vectors: List[np.ndarray] = []
    doc_ids: List[str] = []
    metadata_store: Dict[str, Dict[str, Any]] = {}
    failures = 0

    for page in pages:
        image_path = _resolve_image_path(page, prefer_overlay)
        text_info = page.to_text_info()

        if image_path is None:
            print(f"警告: 找不到图片，跳过 {page.page_id}")
            failures += 1
            continue

        try:
            image_vec = np.asarray(
                get_image_embedding(str(image_path), normalize=True), dtype=np.float32
            )
            text_vec: Optional[np.ndarray] = None
            if text_info.strip():
                text_vec = np.asarray(
                    get_text_embedding(text_info, normalize=True), dtype=np.float32
                )
            vector = _combine_embeddings(image_vec, text_vec, image_weight).astype(np.float32)
        except Exception as exc:
            failures += 1
            print(f"警告: 向量化失败，跳过 {page.page_id}: {exc}")
            continue

        doc_id = page.page_id
        vectors.append(vector)
        doc_ids.append(doc_id)

        meta = page.to_metadata_dict()
        meta["text_info"] = text_info
        meta["image_path"] = str(image_path)
        meta["type"] = "image"
        meta["model"] = model_name
        metadata_store[doc_id] = meta

    if not vectors:
        raise RuntimeError("所有页面均向量化失败，索引未生成。")

    embeddings = np.stack(vectors).astype(np.float32)
    index_path.mkdir(parents=True, exist_ok=True)

    np.save(index_path / "embeddings.npy", embeddings)

    with open(index_path / "ids.json", "w", encoding="utf-8") as f:
        json.dump(doc_ids, f, ensure_ascii=False, indent=2)

    with open(index_path / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_store, f, ensure_ascii=False, indent=2)

    config = {
        "model": model_name,
        "dimension": int(embeddings.shape[1]),
        "image_weight": image_weight,
        "documents": len(doc_ids),
        "failures": failures,
        "data_schema": "naive_v2",
    }
    with open(index_path / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(
        f"索引构建完成，成功 {len(doc_ids)} 条，失败 {failures} 条。保存至 {index_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="使用 Chinese-CLIP 从 rag/data/ 构建向量索引"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_DATA_DIR),
        help="OCR 结果数据目录（默认: rag/data/）",
    )
    parser.add_argument(
        "--index-path",
        type=str,
        default=str(DEFAULT_INDEX_PATH),
        help="索引输出目录（默认: rag/naive/index/）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help="Chinese-CLIP 模型名称",
    )
    parser.add_argument(
        "--image-weight",
        type=float,
        default=0.65,
        help="图像与文字向量融合权重 (0-1)，越大越偏向图像",
    )
    parser.add_argument(
        "--use-overlay",
        action="store_true",
        default=True,
        help="优先使用 overlay 图片（含 OCR 叠加框）进行向量化",
    )
    parser.add_argument(
        "--no-overlay",
        dest="use_overlay",
        action="store_false",
        help="不使用 overlay 图片，尝试从 source_image 路径加载原始图片",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_dir}")

    print(f"扫描数据目录: {data_dir}")
    loader = NaiveDataLoader(data_dir)
    pages = loader.scan_pages()

    if not pages:
        raise RuntimeError("未找到任何页面目录，请检查数据目录结构。")

    print(f"找到 {len(pages)} 页，开始构建索引…")
    build_clip_index(
        pages,
        Path(args.index_path),
        model_name=args.model,
        image_weight=float(args.image_weight),
        prefer_overlay=args.use_overlay,
    )
    print("完成！")


if __name__ == "__main__":
    main()
