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


class ApprovalNotFound(BusinessError):
    def __init__(self):
        super().__init__("APPROVAL_NOT_FOUND", "审批单不存在", 404)


class ApprovalAlreadyDecided(BusinessError):
    def __init__(self):
        super().__init__("APPROVAL_ALREADY_DECIDED", "审批单已处理，不能重复操作", 409)


class ApprovalNotApproved(BusinessError):
    def __init__(self):
        super().__init__("APPROVAL_NOT_APPROVED", "审批单尚未通过，不能执行高成本动作", 409)


class ApprovalContextMismatch(BusinessError):
    def __init__(self):
        super().__init__("APPROVAL_CONTEXT_MISMATCH", "审批单与当前执行对象不匹配", 409)


class ApprovalAlreadyConsumed(BusinessError):
    def __init__(self):
        super().__init__("APPROVAL_ALREADY_CONSUMED", "审批单已被消费，不能重复使用", 409)


class QuotaExceeded(BusinessError):
    def __init__(self, detail: str = "当前额度已用尽", details: Optional[Dict[str, Any]] = None):
        super().__init__("QUOTA_EXCEEDED", detail, 409, details)


class BudgetExceeded(BusinessError):
    def __init__(self, detail: str = "当前预算不足", details: Optional[Dict[str, Any]] = None):
        super().__init__("BUDGET_EXCEEDED", detail, 409, details)


class HighCostActionBlocked(BusinessError):
    def __init__(
        self,
        detail: str = "当前请求未满足高成本能力触发条件",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__("HIGH_COST_ACTION_BLOCKED", detail, 409, details)
