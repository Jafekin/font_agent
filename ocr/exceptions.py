"""OCR 异常处理."""

from __future__ import annotations


class OCRError(Exception):
    """OCR 基础异常类."""

    pass


class OCRAPIError(OCRError):
    """API 调用错误."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class OCRAuthError(OCRError):
    """认证错误."""

    pass


class OCRFileError(OCRError):
    """文件操作错误."""

    pass


class OCRConfigError(OCRError):
    """配置错误."""

    pass


class OCRTimeoutError(OCRError):
    """超时错误."""

    pass


class OCRValidationError(OCRError):
    """数据验证错误."""

    pass
