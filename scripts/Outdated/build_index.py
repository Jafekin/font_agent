"""使用 Chinese-CLIP 构建图片+文字信息的 RAG 向量索引。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.embeddings import MODEL_NAME, get_image_embedding, get_text_embedding  # noqa: E402

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
DEFAULT_INDEX_PATH = PROJECT_ROOT / "rag" / "index"


def flatten_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """将嵌套结构压扁为 JSON 友好的字典。"""

    flattened: Dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (dict, list)):
            flattened[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            flattened[key] = ""
        else:
            flattened[key] = value
    return flattened


def build_default_text_info(image_path: Path, metadata: Dict[str, Any]) -> str:
    """当缺失描述时，使用基础元数据拼接一句话。"""

    parts = [f"图片文件: {image_path.name}"]
    for label in ("title", "directory", "category", "catalog_number", "current_location"):
        value = metadata.get(label)
        if value:
            human_label = {
                "title": "标题",
                "directory": "目录",
                "category": "类别",
                "catalog_number": "编号",
                "current_location": "现藏",
            }[label]
            parts.append(f"{human_label}: {value}")
    return "。".join(parts) + "。"


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        return "、".join(str(v).strip() for v in value if v)
    if isinstance(value, dict):
        return "、".join(f"{k}:{v}" for k, v in value.items() if v)
    return str(value).strip()


def extract_text_info_from_json(json_data: Dict[str, Any]) -> str:
    parts: List[str] = []

    def push(label: str, value: Any) -> None:
        normalized = _normalize_value(value)
        if normalized:
            parts.append(f"{label}{normalized}")

    title_block = json_data.get("title", {})
    push("标题: ", title_block.get("title_text"))

    author_editors = json_data.get("author_and_editors", {})
    push("作者: ", author_editors.get("author"))
    push("编者: ", author_editors.get("editor_commentator"))

    edition_info = json_data.get("edition_information", {})
    push("版本: ", [
        edition_info.get("edition_type"),
        edition_info.get("edition_style"),
        edition_info.get("publication_period"),
    ])
    push("出版者: ", edition_info.get("publisher"))

    doc_metadata = json_data.get("document_metadata", {})
    push("分类: ", doc_metadata.get("classification", {}).get("value"))
    push("语言: ", doc_metadata.get("language", {}).get("value"))
    push("文献类型: ", doc_metadata.get("document_type", {}).get("value"))

    collection = json_data.get("collection_and_provenance", {})
    current_location = collection.get("current_location")
    if current_location:
        match = re.search(r"([^/]+(?:图书馆|博物院|书店))", str(current_location))
        push("现藏: ", match.group(1) if match else current_location)
    push("旧藏: ", collection.get("previous_owner"))

    path_info = json_data.get("path_info", {})
    push("类别: ", path_info.get("category"))
    push("编号: ", path_info.get("catalog_number"))
    push("卷册: ", path_info.get("volume"))

    notes = json_data.get("notes") or json_data.get("note")
    push("备注: ", notes)

    return "。".join(parts) + "。" if parts else json.dumps(json_data, ensure_ascii=False)


def find_image_text_pairs(
    image_dir: str,
    text_info_dir: Optional[str] = None,
    text_file_extensions: tuple[str, ...] = (".json", ".txt", ".md"),
) -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []
    image_dir_path = Path(image_dir)

    for image_path in image_dir_path.rglob("*"):
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        text_info = None
        text_path = None
        json_data = None

        for ext in text_file_extensions:
            candidate = image_path.with_suffix(ext)
            if candidate.exists():
                text_path = candidate
                break

        if text_path is None and text_info_dir:
            candidate = Path(text_info_dir) / \
                image_path.relative_to(image_dir_path)
            for ext in text_file_extensions:
                alt = candidate.with_suffix(ext)
                if alt.exists():
                    text_path = alt
                    break

        if text_path and text_path.exists():
            try:
                if text_path.suffix.lower() == ".json":
                    with open(text_path, "r", encoding="utf-8") as f:
                        json_data = json.load(f)
                    if isinstance(json_data, dict):
                        text_info = extract_text_info_from_json(json_data)
                    else:
                        text_info = str(json_data)
                else:
                    with open(text_path, "r", encoding="utf-8") as f:
                        text_info = f.read()
            except Exception as exc:
                print(f"警告: 无法读取文字信息 {text_path}: {exc}")
                text_info = None
                json_data = None

        metadata: Dict[str, Any] = {
            "filename": image_path.name,
            "directory": str(image_path.parent.relative_to(image_dir_path)),
            "has_text_info": text_path is not None,
        }

        if isinstance(json_data, dict):
            path_info = json_data.get("path_info", {})
            doc_metadata = json_data.get("document_metadata", {})
            title_info = json_data.get("title", {})
            edition_info = json_data.get("edition_information", {})
            collection_info = json_data.get("collection_and_provenance", {})

            metadata.update({
                "category": path_info.get("category", ""),
                "catalog_number": path_info.get("catalog_number", ""),
                "title": title_info.get("title_text", ""),
                "edition_type": edition_info.get("edition_type", ""),
                "current_location": collection_info.get("current_location", ""),
                "document_type": doc_metadata.get("document_type", {}).get("value", ""),
                "language": doc_metadata.get("language", {}).get("value", ""),
            })

        if not text_info or not text_info.strip():
            text_info = build_default_text_info(image_path, metadata)

        pairs.append({
            "image_path": str(image_path),
            "text_info": text_info,
            "id": str(image_path.relative_to(image_dir_path)),
            "metadata": metadata,
        })

    return pairs


def _combine_embeddings(image_vec: np.ndarray, text_vec: Optional[np.ndarray], weight: float) -> np.ndarray:
    if text_vec is None:
        return image_vec
    combined = weight * image_vec + (1.0 - weight) * text_vec
    norm = np.linalg.norm(combined)
    return combined / norm if norm > 0 else combined


def build_clip_index(
    pairs: List[Dict[str, Any]],
    index_path: Path,
    *,
    model_name: str = MODEL_NAME,
    image_weight: float = 0.65,
) -> None:
    if not pairs:
        raise ValueError("未找到任何图片-文字对，无法构建索引。")

    vectors: List[np.ndarray] = []
    doc_ids: List[str] = []
    metadata_store: Dict[str, Dict[str, Any]] = {}
    failures = 0

    for pair in pairs:
        image_path = pair["image_path"]
        text_info = pair["text_info"] or ""
        doc_id = pair["id"]

        try:
            image_vec = np.asarray(get_image_embedding(
                image_path, normalize=True), dtype=np.float32)
            text_vec = None
            if text_info.strip():
                text_vec = np.asarray(get_text_embedding(
                    text_info, normalize=True), dtype=np.float32)
            vector = _combine_embeddings(
                image_vec, text_vec, image_weight).astype(np.float32)
        except Exception as exc:
            failures += 1
            print(f"警告: 向量化失败，跳过 {image_path}: {exc}")
            continue

        vectors.append(vector)
        doc_ids.append(doc_id)

        metadata = flatten_metadata({
            **pair["metadata"],
            "text_info": text_info,
            "image_path": image_path,
            "type": "image",
            "model": model_name,
        })
        metadata_store[doc_id] = metadata

    if not vectors:
        raise RuntimeError("所有图片均向量化失败，索引未生成。")

    embeddings = np.stack(vectors).astype(np.float32)
    index_path.mkdir(parents=True, exist_ok=True)
    np.save(index_path / "embeddings.npy", embeddings)

    with open(index_path / "ids.json", "w", encoding="utf-8") as f:
        json.dump(doc_ids, f, ensure_ascii=False, indent=2)

    with open(index_path / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_store, f, ensure_ascii=False, indent=2)

    config = {
        "model": model_name,
        "dimension": embeddings.shape[1],
        "image_weight": image_weight,
        "documents": len(doc_ids),
        "failures": failures,
    }
    with open(index_path / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"索引构建完成，成功 {len(doc_ids)} 条，失败 {failures} 条。保存至 {index_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="使用 Chinese-CLIP 构建本地向量索引")
    parser.add_argument("--image-dir", type=str, default="data", help="图片目录")
    parser.add_argument("--text-info-dir", type=str,
                        default=None, help="文字信息目录，默认与图片同目录")
    parser.add_argument("--index-path", type=str,
                        default=str(DEFAULT_INDEX_PATH), help="索引输出目录")
    parser.add_argument("--model", type=str,
                        default=MODEL_NAME, help="Chinese-CLIP 模型名称")
    parser.add_argument("--image-weight", type=float, default=0.65,
                        help="图像与文字向量融合权重(0-1)，越大越偏向图像")

    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    if not image_dir.exists():
        raise FileNotFoundError(f"图片目录不存在: {image_dir}")

    print(f"扫描图片目录: {image_dir}")
    pairs = find_image_text_pairs(str(image_dir), args.text_info_dir)
    if not pairs:
        raise RuntimeError("未找到任何图片文件，请检查目录是否包含受支持的格式。")

    print(f"找到 {len(pairs)} 个图片-文字对，开始构建索引…")
    build_clip_index(
        pairs,
        Path(args.index_path),
        model_name=args.model,
        image_weight=float(args.image_weight),
    )

    print("完成！")


if __name__ == "__main__":
    main()
