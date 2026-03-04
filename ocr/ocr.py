"""Kandianguji 古籍 OCR API helper.

This module consolidates interactions with https://www.kandianguji.com/api_documentation so the
rest of the project can call a single, well-documented client.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode

import requests
from PIL import Image, ImageDraw, ImageFont

BASE_URL = "https://ocr.kandianguji.com"
# 文字识别接口
OCR_ENDPOINT = "/ocr_api"
# Token状态查询接口
TOKEN_STATUS_ENDPOINT = "/get_token_status"
# 文字识别接口
PDF_OCR_ENDPOINT = "/api/pdf_ocr_api"
# PDF识别任务进度查询接口
PDF_STATUS_ENDPOINT = "/api/pdf_ocr_api_status"
# PDF识别任务识别结果下载接口
PDF_DOWNLOAD_PATH = "/api/pdf_ocr_api_download/task_id-{task_id}"

DEFAULT_TIMEOUT = 60
CHUNK_SIZE = 1024 * 256


def encode_image_to_base64(image_path: str | Path) -> str:
    """Return base64 encoded contents of ``image_path`` for the OCR API."""

    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")
    return base64.b64encode(path.read_bytes()).decode("utf-8")


class KandiangujiOCRClient:
    """Thin wrapper around the 看典古籍 OCR endpoints from the published docs."""

    def __init__(
        self,
        token: str,
        email: str,
        *,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not token or not email:
            raise ValueError("token and email are required")
        self.token = token
        self.email = email
        self.timeout = timeout

    def recognize_image(
        self,
        image_base64: str,
        *,
        char_ocr: bool = False,
        det_mode: str = "auto",
        image_size: int = 0,
        return_position: bool = True,
        return_choices: bool = False,
        version: str = "default",
        det_layout: bool = False,
        only_plain_text: bool = False,
        return_layout: bool = False,
        auto_insert_space: bool = False,
        hp_line_words_angel: str = "left2right",
        sp_line_words_angel: str = "top2bottom",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call /ocr_api with the documented parameters.

        The API accepts JSON or form payloads; this client sends JSON. The
        ``extra`` mapping can be used to pass vendor additions without changing
        the signature.
        """

        payload: Dict[str, Any] = {
            "image": image_base64,
            "char_ocr": char_ocr,
            "det_mode": det_mode,
            "image_size": image_size,
            "return_position": return_position,
            "return_choices": return_choices,
            "version": version,
            "det_layout": det_layout,
            "only_plain_text": only_plain_text,
            "return_layout": return_layout,
            "auto_insert_space": auto_insert_space,
            "hp_line_words_angel": hp_line_words_angel,
            "sp_line_words_angel": sp_line_words_angel,
        }
        if extra:
            payload.update(extra)
        return self._post(OCR_ENDPOINT, payload)

    def get_token_status(self) -> Dict[str, Any]:
        """Call /get_token_status to inspect remaining quota and status."""

        return self._post(TOKEN_STATUS_ENDPOINT, {})

    def submit_pdf_task(
        self,
        pdf_path: str | Path,
        *,
        det_mode: str = "auto",
        image_size: int = 0,
        version: str = "default",
    ) -> Dict[str, Any]:
        """Create a PDF OCR task via /api/pdf_ocr_api (form-data upload)."""

        path = Path(pdf_path)
        if not path.is_file():
            raise FileNotFoundError(f"PDF not found: {path}")
        data = {
            "det_mode": det_mode,
            "image_size": image_size,
            "version": version,
        }
        files = {"file": (path.name, path.read_bytes(), "application/pdf")}
        return self._post(PDF_OCR_ENDPOINT, data, files=files)

    def get_pdf_task_status(self, task_id: str) -> Dict[str, Any]:
        """Query PDF OCR task progress via /api/pdf_ocr_api_status."""

        if not task_id:
            raise ValueError("task_id is required")
        return self._post(PDF_STATUS_ENDPOINT, {"task_id": task_id})

    def download_pdf_result(
        self,
        task_id: str,
        code: str,
        *,
        file_type: str = "all",
        output_path: Optional[str | Path] = None,
        overwrite: bool = False,
    ) -> Path:
        """Download PDF OCR result archive via /api/pdf_ocr_api_download/task_id-xxx."""

        if not task_id or not code:
            raise ValueError("task_id and code are required")
        download_path = Path(output_path) if output_path else Path(
            f"{task_id}_{file_type}.zip")
        if download_path.exists() and not overwrite:
            raise FileExistsError(
                f"{download_path} already exists (use overwrite=True)")

        path = PDF_DOWNLOAD_PATH.format(task_id=task_id)
        params = {"code": code, "file_type": file_type}
        url = f"{BASE_URL}{path}?{urlencode(params)}"
        with requests.get(url, timeout=self.timeout, stream=True) as response:
            response.raise_for_status()
            tmp_path = download_path.with_suffix(
                download_path.suffix + ".part")
            with tmp_path.open("wb") as buffer:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        buffer.write(chunk)
            tmp_path.replace(download_path)
        return download_path

    def _post(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        *,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal helper that sends JSON for normal calls and form-data when files are present."""

        url = f"{BASE_URL}{endpoint}"
        data = {"token": self.token, "email": self.email}
        data.update(payload)
        request_kwargs = {"timeout": self.timeout}
        if files:
            request_kwargs["data"] = data
            request_kwargs["files"] = files
        else:
            request_kwargs["data"] = data
        # print(f"POST {url} with {request_kwargs}")
        response = requests.post(url, **request_kwargs)
        response.raise_for_status()
        return response.json()


def summarize_text_lines(result: Dict[str, Any]) -> str:
    """Render a newline joined summary of OCR text lines."""

    texts = result.get("data", {}).get("texts") or []

    def to_text(item: Any) -> str:
        if isinstance(item, dict):
            return str(item.get("text", ""))
        return str(item)

    lines: Iterable[str] = (to_text(line) for line in texts)
    return "\n".join(filter(None, lines))


def save_ocr_outputs(result: Dict[str, Any], source_image: Path, output_dir: Path) -> None:
    """Save OCR JSON and plain text next to the source image."""

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = source_image.stem
    json_path = output_dir / f"{stem}_ocr.json"
    txt_path = output_dir / f"{stem}_ocr.txt"

    json_path.write_text(json.dumps(
        result, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text(summarize_text_lines(result), encoding="utf-8")


def draw_overlay(image_path: Path, result: Dict[str, Any], output_path: Optional[Path] = None) -> Path:
    """Draw text-line polygons and labels on the image and save a copy."""

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    text_lines = (result.get("data") or {}).get("text_lines") or []
    for line in text_lines:
        polygon = line.get("position") or []
        text = line.get("text", "")
        if len(polygon) >= 3:
            flat = [tuple(pt) for pt in polygon]
            draw.line(flat + [flat[0]], fill="red", width=2)
            if flat:
                draw.text(flat[0], text, fill="yellow", font=font)

    output_path = output_path or image_path.with_name(
        f"{image_path.stem}_overlay{image_path.suffix}")
    image.save(output_path)
    return output_path


__all__ = [
    "encode_image_to_base64",
    "KandiangujiOCRClient",
    "summarize_text_lines",
    "save_ocr_outputs",
    "draw_overlay",
]


if __name__ == "__main__":
    client = KandiangujiOCRClient(
        token="6a750d32-b0eb-48ac-bdf8-897923e9555d", email="17324018120")

    image_path = Path("./ocr/test2.jpg")
    test_base64 = encode_image_to_base64(image_path)
    result = client.recognize_image(test_base64)
    print(result)

    output_dir = image_path.parent / "outputs"
    save_ocr_outputs(result, image_path, output_dir)
    overlay_path = draw_overlay(image_path, result)
    print(f"Saved JSON/text to: {output_dir}")
    print(f"Overlay image: {overlay_path}")
