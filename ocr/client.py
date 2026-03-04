"""Kandianguji 古籍 OCR 客户端（重构版）.

优化内容：
1. 使用数据类管理配置和结果
2. 改进错误处理和日志记录
3. 分离输出管理逻辑
4. 添加类型注解和文档
5. 支持更灵活的配置
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .config import OCRConfig
from .exceptions import (
    OCRAPIError,
    OCRAuthError,
    OCRFileError,
    OCRTimeoutError,
)
from .models import OCRResult, PDFTaskStatus

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_path: str | Path) -> str:
    """将图片编码为 base64 字符串.

    Args:
        image_path: 图片文件路径

    Returns:
        base64 编码的字符串

    Raises:
        OCRFileError: 文件不存在或无法读取
    """
    path = Path(image_path)
    if not path.is_file():
        raise OCRFileError(f"图片文件不存在: {path}")

    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception as e:
        raise OCRFileError(f"读取图片文件失败: {e}") from e


class KandiangujiOCRClient:
    """看典古籍 OCR API 客户端."""

    # API 端点
    OCR_ENDPOINT = "/ocr_api"
    TOKEN_STATUS_ENDPOINT = "/get_token_status"
    PDF_OCR_ENDPOINT = "/api/pdf_ocr_api"
    PDF_STATUS_ENDPOINT = "/api/pdf_ocr_api_status"
    PDF_DOWNLOAD_PATH = "/api/pdf_ocr_api_download/task_id-{task_id}"

    def __init__(self, config: Optional[OCRConfig] = None):
        """初始化 OCR 客户端.

        Args:
            config: OCR 配置对象，如果为 None 则从环境变量加载
        """
        if config is None:
            from .config import get_default_config

            config = get_default_config()

        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """验证配置有效性."""
        if not self.config.token or not self.config.email:
            raise OCRAuthError("token 和 email 不能为空")

    def recognize_image(
        self,
        image_path: str | Path = None,
        image_base64: str = None,
        **kwargs,
    ) -> OCRResult:
        """识别图片中的文字.

        Args:
            image_path: 图片文件路径（与 image_base64 二选一）
            image_base64: base64 编码的图片（与 image_path 二选一）
            **kwargs: 其他 OCR 参数，会覆盖配置中的默认值

        Returns:
            OCR 识别结果对象

        Raises:
            OCRFileError: 图片文件错误
            OCRAPIError: API 调用失败
        """
        # 准备图片数据
        if image_base64 is None:
            if image_path is None:
                raise OCRFileError("必须提供 image_path 或 image_base64")
            image_base64 = encode_image_to_base64(image_path)

        # 构建请求参数（使用配置默认值 + 传入参数）
        payload = {
            "image": image_base64,
            "char_ocr": kwargs.get("char_ocr", self.config.char_ocr),
            "det_mode": kwargs.get("det_mode", self.config.det_mode),
            "image_size": kwargs.get("image_size", self.config.image_size),
            "return_position": kwargs.get("return_position", self.config.return_position),
            "return_choices": kwargs.get("return_choices", self.config.return_choices),
            "version": kwargs.get("version", self.config.version),
            "det_layout": kwargs.get("det_layout", self.config.det_layout),
            "only_plain_text": kwargs.get("only_plain_text", self.config.only_plain_text),
            "return_layout": kwargs.get("return_layout", self.config.return_layout),
            "auto_insert_space": kwargs.get("auto_insert_space", self.config.auto_insert_space),
            "hp_line_words_angel": kwargs.get("hp_line_words_angel", self.config.hp_line_words_angel),
            "sp_line_words_angel": kwargs.get("sp_line_words_angel", self.config.sp_line_words_angel),
        }

        # 调用 API
        response = self._post(self.OCR_ENDPOINT, payload)

        # 解析结果
        return OCRResult.from_api_response(response)

    def get_token_status(self) -> Dict[str, Any]:
        """查询 Token 状态和剩余额度.

        Returns:
            包含 Token 状态信息的字典
        """
        return self._post(self.TOKEN_STATUS_ENDPOINT, {})

    def submit_pdf_task(
        self,
        pdf_path: str | Path,
        *,
        det_mode: str = "auto",
        image_size: int = 0,
        version: str = "default",
    ) -> str:
        """提交 PDF OCR 任务.

        Args:
            pdf_path: PDF 文件路径
            det_mode: 检测模式
            image_size: 图片尺寸
            version: 版本

        Returns:
            任务 ID

        Raises:
            OCRFileError: PDF 文件不存在
            OCRAPIError: API 调用失败
        """
        path = Path(pdf_path)
        if not path.is_file():
            raise OCRFileError(f"PDF 文件不存在: {path}")

        data = {
            "det_mode": det_mode,
            "image_size": image_size,
            "version": version,
        }

        try:
            files = {"file": (path.name, path.read_bytes(), "application/pdf")}
        except Exception as e:
            raise OCRFileError(f"读取 PDF 文件失败: {e}") from e

        response = self._post(self.PDF_OCR_ENDPOINT, data, files=files)
        return response.get("task_id", "")

    def get_pdf_task_status(self, task_id: str) -> PDFTaskStatus:
        """查询 PDF OCR 任务状态.

        Args:
            task_id: 任务 ID

        Returns:
            任务状态对象
        """
        if not task_id:
            raise ValueError("task_id 不能为空")

        response = self._post(self.PDF_STATUS_ENDPOINT, {"task_id": task_id})
        return PDFTaskStatus.from_api_response(response)

    def download_pdf_result(
        self,
        task_id: str,
        code: str,
        *,
        file_type: str = "all",
        output_path: Optional[str | Path] = None,
        overwrite: bool = False,
    ) -> Path:
        """下载 PDF OCR 结果.

        Args:
            task_id: 任务 ID
            code: 下载码
            file_type: 文件类型（all/json/txt）
            output_path: 输出路径
            overwrite: 是否覆盖已存在的文件

        Returns:
            下载文件的路径

        Raises:
            OCRAPIError: 下载失败
            FileExistsError: 文件已存在且 overwrite=False
        """
        if not task_id or not code:
            raise ValueError("task_id 和 code 不能为空")

        # 确定输出路径
        download_path = Path(output_path) if output_path else Path(
            f"{task_id}_{file_type}.zip")

        if download_path.exists() and not overwrite:
            raise FileExistsError(
                f"文件已存在: {download_path}（使用 overwrite=True 覆盖）")

        # 构建下载 URL
        path = self.PDF_DOWNLOAD_PATH.format(task_id=task_id)
        params = {"code": code, "file_type": file_type}
        url = f"{self.config.base_url}{path}?{urlencode(params)}"

        # 下载文件
        try:
            with requests.get(url, timeout=self.config.timeout, stream=True) as response:
                response.raise_for_status()

                # 使用临时文件避免下载中断导致的损坏
                tmp_path = download_path.with_suffix(
                    download_path.suffix + ".part")
                with tmp_path.open("wb") as buffer:
                    for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                        if chunk:
                            buffer.write(chunk)

                # 下载完成后重命名
                tmp_path.replace(download_path)

        except requests.Timeout as e:
            raise OCRTimeoutError(f"下载超时: {e}") from e
        except requests.RequestException as e:
            raise OCRAPIError(f"下载失败: {e}") from e

        logger.info(f"PDF 结果已下载到: {download_path}")
        return download_path

    def _post(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        *,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """发送 POST 请求到 API.

        Args:
            endpoint: API 端点
            payload: 请求数据
            files: 文件数据（用于文件上传）

        Returns:
            API 响应的 JSON 数据

        Raises:
            OCRAPIError: API 调用失败
            OCRTimeoutError: 请求超时
        """
        url = f"{self.config.base_url}{endpoint}"

        # 添加认证信息
        data = {
            "token": self.config.token,
            "email": self.config.email,
        }
        data.update(payload)

        # 构建请求参数
        request_kwargs = {"timeout": self.config.timeout}
        if files:
            request_kwargs["data"] = data
            request_kwargs["files"] = files
        else:
            request_kwargs["data"] = data

        # 发送请求
        try:
            logger.debug(f"POST {url}")
            response = requests.post(url, **request_kwargs)
            response.raise_for_status()
            return response.json()

        except requests.Timeout as e:
            raise OCRTimeoutError(f"请求超时: {e}") from e
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            if status_code == 401:
                raise OCRAuthError(f"认证失败: {e}") from e
            raise OCRAPIError(
                f"API 调用失败: {e}",
                status_code=status_code,
                response=e.response.json() if e.response else None,
            ) from e
        except requests.RequestException as e:
            raise OCRAPIError(f"网络请求失败: {e}") from e
        except ValueError as e:
            raise OCRAPIError(f"响应解析失败: {e}") from e


__all__ = [
    "encode_image_to_base64",
    "KandiangujiOCRClient",
    "OCRConfig",
    "OCRResult",
    "PDFTaskStatus",
]
