"""Kandianguji 古籍 OCR API helper.

This module consolidates interactions with https://www.kandianguji.com/api_documentation so the
rest of the project can call a single, well-documented client.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode

import requests

BASE_URL = "https://ocr.kandianguji.com"
OCR_ENDPOINT = "/ocr_api"
TOKEN_STATUS_ENDPOINT = "/get_token_status"
PDF_OCR_ENDPOINT = "/api/pdf_ocr_api"
PDF_STATUS_ENDPOINT = "/api/pdf_ocr_api_status"
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
    """Thin wrapper around the 看典古籍 OCR endpoints."""

    def __init__(
        self,
        token: str,
        email: str,
        *,
        session: Optional[requests.Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not token or not email:
            raise ValueError("token and email are required")
        self.token = token
        self.email = email
        self.session = session or requests.Session()
        self.timeout = timeout

    def recognize_image(self, image_base64: str, **options: Any) -> Dict[str, Any]:
        payload = {"image": image_base64}
        payload.update(options)
        return self._post(OCR_ENDPOINT, payload)

    def get_token_status(self) -> Dict[str, Any]:
        return self._post(TOKEN_STATUS_ENDPOINT, {})

    def submit_pdf_task(
        self,
        pdf_path: str | Path,
        *,
        det_mode: str = "auto",
        image_size: int = 0,
        version: str = "default",
    ) -> Dict[str, Any]:
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
        with self.session.get(url, timeout=self.timeout, stream=True) as response:
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
        url = f"{BASE_URL}{endpoint}"
        data = {"token": self.token, "email": self.email}
        data.update(payload)
        request_kwargs = {"timeout": self.timeout}
        if files:
            request_kwargs["data"] = data
            request_kwargs["files"] = files
        else:
            request_kwargs["json"] = data
        response = self.session.post(url, **request_kwargs)
        response.raise_for_status()
        return response.json()


def summarize_text_lines(result: Dict[str, Any]) -> str:
    """Render a newline joined summary of OCR text lines."""

    texts = result.get("data", {}).get("texts") or []
    lines: Iterable[str] = (line.get("text", "") for line in texts)
    return "\n".join(filter(None, lines))


__all__ = [
    "encode_image_to_base64",
    "KandiangujiOCRClient",
    "summarize_text_lines",
]
