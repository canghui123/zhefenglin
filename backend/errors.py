"""Standardized business error codes and exception classes.

Every ``BusinessError`` carries a machine-readable ``code`` and a
human-readable ``message``.  The global exception handler in ``main.py``
converts these into the unified JSON envelope::

    {"error": {"code": "...", "message": "...", "request_id": "...", "details": {}}}
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class BusinessError(Exception):
    """Base class for domain / business errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


# ---- Concrete error codes ----

class AssetPackageNotFound(BusinessError):
    def __init__(self):
        super().__init__("ASSET_PACKAGE_NOT_FOUND", "资产包不存在", 404)


class SandboxResultNotFound(BusinessError):
    def __init__(self):
        super().__init__("SANDBOX_RESULT_NOT_FOUND", "模拟结果不存在", 404)


class SandboxBatchNotFound(BusinessError):
    def __init__(self):
        super().__init__("SANDBOX_BATCH_NOT_FOUND", "批量模拟批次不存在", 404)


class SandboxInputIncomplete(BusinessError):
    def __init__(self, detail: str = "库存沙盘输入不完整"):
        super().__init__("SANDBOX_INPUT_INCOMPLETE", detail, 400)


class JobNotFound(BusinessError):
    def __init__(self):
        super().__init__("JOB_NOT_FOUND", "任务不存在", 404)


class FileNotFoundError_(BusinessError):
    def __init__(self):
        super().__init__("FILE_NOT_FOUND", "文件不存在", 404)


class InvalidFileFormat(BusinessError):
    def __init__(self, detail: str = "仅支持.xlsx或.xls文件"):
        super().__init__("INVALID_FILE_FORMAT", detail, 400)


class ParseError(BusinessError):
    def __init__(self, detail: str = "Excel解析失败，请检查文件格式"):
        super().__init__("PARSE_ERROR", detail, 400)


class Unauthorized(BusinessError):
    def __init__(self, detail: str = "未登录或会话已过期"):
        super().__init__("UNAUTHORIZED", detail, 401)


class Forbidden(BusinessError):
    def __init__(self, detail: str = "权限不足"):
        super().__init__("FORBIDDEN", detail, 403)


class ReportNotGenerated(BusinessError):
    def __init__(self):
        super().__init__("REPORT_NOT_GENERATED", "尚未生成报告", 404)


class WorkOrderNotFound(BusinessError):
    def __init__(self):
        super().__init__("WORK_ORDER_NOT_FOUND", "工单不存在", 404)


class DataImportBatchNotFound(BusinessError):
    def __init__(self):
        super().__init__("DATA_IMPORT_BATCH_NOT_FOUND", "数据导入批次不存在", 404)


class InvalidWorkOrderTransition(BusinessError):
    def __init__(self, detail: str = "工单状态流转不合法"):
        super().__init__("INVALID_WORK_ORDER_TRANSITION", detail, 400)


class InvalidLegalDocumentRequest(BusinessError):
    def __init__(self, detail: str = "法务材料生成请求不合法"):
        super().__init__("INVALID_LEGAL_DOCUMENT_REQUEST", detail, 400)
