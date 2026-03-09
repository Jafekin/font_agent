"""Chinese-CLIP based embedding helpers for the RAG pipeline."""

from __future__ import annotations

import importlib
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, List

import numpy as np
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIP_THIRDPARTY = PROJECT_ROOT / "thirdparty" / "Chinese-CLIP"
if CLIP_THIRDPARTY.exists():
    sys.path.insert(0, str(CLIP_THIRDPARTY))

# Configuration与`scripts/build_index.py`保持一致
MODEL_NAME = "OFA-Sys/chinese-clip-vit-base-patch16"
DEVICE = os.getenv("RAG_DEVICE") or (
    "cuda" if torch.cuda.is_available() else "cpu")

HF_MODEL_ALIASES = {
    "chinese-clip-vit-base-patch16": "ViT-B-16",
    "chinese-clip-vit-large-patch14": "ViT-L-14",
    "chinese-clip-vit-large-patch14-336px": "ViT-L-14-336",
    "chinese-clip-vit-huge-patch14": "ViT-H-14",
    "chinese-clip-rn50": "RN50",
}

_FAKE_MODE = os.getenv("RAG_FAKE_EMBEDDINGS") == "1"


@lru_cache(maxsize=1)
def _load_cn_clip_module():
    try:
        return importlib.import_module("cn_clip.clip")
    except ImportError as exc:  # pragma: no cover - 环境问题
        raise ImportError(
            "无法导入 cn_clip.clip，请先运行 pip install -e thirdparty/Chinese-CLIP"
        ) from exc


class _FakeClip:
    """Deterministic fallback when heavy deps不可用。"""

    dim = 512

    @staticmethod
    def _vec(seed_obj: Any) -> np.ndarray:
        rng = np.random.default_rng(abs(hash(seed_obj)) % (2**32))
        vec = rng.normal(size=_FakeClip.dim).astype("float32")
        vec /= np.linalg.norm(vec) + 1e-9
        return vec

    def encode_image(self, image_path: str) -> np.ndarray:
        return self._vec(("image", image_path))

    def encode_text(self, text: str) -> np.ndarray:
        return self._vec(("text", text))


@lru_cache(maxsize=1)
def _load_chinese_clip():
    if _FAKE_MODE:
        return _FakeClip(), None

    clip = _load_cn_clip_module()
    load_from_name = getattr(clip, "load_from_name")

    resolved_name = _resolve_loader_model_name(MODEL_NAME)

    cache_dir = os.path.join(os.path.dirname(
        os.path.dirname(__file__)), "model")
    os.makedirs(cache_dir, exist_ok=True)
    model, preprocess = load_from_name(
        resolved_name,
        device=torch.device(DEVICE),
        download_root=cache_dir,
        use_modelscope=False,
    )
    model.eval()
    return model, preprocess


def _load_colorless_image(image_path: str) -> Image.Image:
    """Open image as luminance-only data expanded to RGB for CLIP preprocessing."""

    with Image.open(image_path) as img:
        grayscale = img.convert("L")  # strip chroma information
        return grayscale.convert("RGB")


def _normalize(vec: np.ndarray) -> List[float]:
    @lru_cache(maxsize=1)
    def _load_cn_clip_module():
        try:
            return importlib.import_module("cn_clip.clip")
        except ImportError as exc:  # pragma: no cover - 环境问题
            raise ImportError(
                "无法导入 cn_clip.clip，请先运行 pip install -e thirdparty/Chinese-CLIP"
            ) from exc

    if not isinstance(vec, np.ndarray):
        vec = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec.tolist()
    return (vec / norm).astype("float32").tolist()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_image_embedding(image_path: str, *, normalize: bool = True) -> List[float]:
    """Build embedding for单张图片."""

    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    model, preprocess = _load_chinese_clip()
    if isinstance(model, _FakeClip):
        vec = model.encode_image(image_path)
        return vec.tolist()

    with torch.no_grad():
        image = preprocess(_load_colorless_image(image_path))
        image = image.unsqueeze(0).to(DEVICE)
        vec = model.encode_image(image)
        vec = vec.squeeze(0).cpu().numpy()
    return _normalize(vec) if normalize else vec.tolist()


def get_text_embedding(text: str, *, normalize: bool = True) -> List[float]:
    if not text or not text.strip():
        raise ValueError("Text must be a non-empty string.")

    model, _ = _load_chinese_clip()
    if isinstance(model, _FakeClip):
        vec = model.encode_text(text)
        return vec.tolist()

    clip = _load_cn_clip_module()
    tokens = clip.tokenize([text]).to(DEVICE)
    with torch.no_grad():
        vec = model.encode_text(tokens)
        vec = vec.squeeze(0).cpu().numpy()
    return _normalize(vec) if normalize else vec.tolist()


def batch_image_embeddings(image_paths: List[str], *, normalize: bool = True) -> List[List[float]]:
    if not image_paths:
        raise ValueError("image_paths must not be empty")

    model, preprocess = _load_chinese_clip()
    valid_paths = [p for p in image_paths if os.path.isfile(p)]
    if not valid_paths:
        raise ValueError("No valid image files found in image_paths")

    if isinstance(model, _FakeClip):
        return [model.encode_image(path).tolist() for path in valid_paths]

    vectors: List[List[float]] = []
    batch_tensors = []
    for path in valid_paths:
        tensor = preprocess(_load_colorless_image(path)).unsqueeze(0)
        batch_tensors.append(tensor)

        if len(batch_tensors) == 8:
            vectors.extend(_encode_image_batch(
                model, batch_tensors, normalize))
            batch_tensors = []

    if batch_tensors:
        vectors.extend(_encode_image_batch(model, batch_tensors, normalize))

    return vectors


def batch_text_embeddings(texts: List[str], *, normalize: bool = True) -> List[List[float]]:
    valid_texts = [t for t in texts if t and t.strip()]
    if not valid_texts:
        raise ValueError("No valid texts found in input")

    model, _ = _load_chinese_clip()
    if isinstance(model, _FakeClip):
        return [model.encode_text(text).tolist() for text in valid_texts]

    clip = _load_cn_clip_module()
    vectors: List[List[float]] = []
    batch_size = 16
    for i in range(0, len(valid_texts), batch_size):
        chunk = valid_texts[i:i + batch_size]
        tokens = clip.tokenize(chunk).to(DEVICE)
        with torch.no_grad():
            vec = model.encode_text(tokens).cpu().numpy()
        if normalize:
            vec = vec / (np.linalg.norm(vec, axis=1, keepdims=True) + 1e-9)
        vectors.extend(vec.astype("float32").tolist())

    return vectors

# ---------------------------------------------------------------------------
# (Optional) Index build helper for future extension
# ---------------------------------------------------------------------------


def build_embeddings_index(items: List[str], output_dir: str) -> None:
    raise NotImplementedError("索引构建已迁移到 scripts/build_index.py")


def _encode_image_batch(model, tensors, normalize):
    stacked = torch.cat(tensors, dim=0).to(DEVICE)
    with torch.no_grad():
        vec = model.encode_image(stacked).cpu().numpy()
    if normalize:
        vec = vec / (np.linalg.norm(vec, axis=1, keepdims=True) + 1e-9)
    return vec.astype("float32").tolist()


def _resolve_loader_model_name(config_name: str) -> str:
    """将 HuggingFace Repo ID 映射到 Chinese-CLIP 原生名称。"""

    name = (config_name or "").strip()
    if not name:
        return "ViT-B-16"

    if os.path.isfile(name):
        return name

    normalized = name.split("/", 1)[1] if "/" in name else name
    normalized = normalized.strip().lower()
    if normalized in HF_MODEL_ALIASES:
        return HF_MODEL_ALIASES[normalized]

    return name
