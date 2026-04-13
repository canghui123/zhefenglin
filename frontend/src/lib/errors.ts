/**
 * Standardized error handling for the auto-finance platform.
 *
 * The backend returns errors in the envelope format:
 * { error: { code, message, request_id, details } }
 *
 * This module provides helpers to parse and display those errors.
 */

export interface ServerError {
  code: string;
  message: string;
  request_id: string;
  details: Record<string, unknown>;
}

export interface ErrorEnvelope {
  error: ServerError;
}

/** Human-readable labels for known error codes. */
const ERROR_LABELS: Record<string, string> = {
  UNAUTHORIZED: "未登录或会话已过期",
  FORBIDDEN: "权限不足",
  VALIDATION_ERROR: "请求参数校验失败",
  ASSET_PACKAGE_NOT_FOUND: "资产包不存在",
  SANDBOX_RESULT_NOT_FOUND: "模拟结果不存在",
  JOB_NOT_FOUND: "任务不存在",
  FILE_NOT_FOUND: "文件不存在",
  INVALID_FILE_FORMAT: "文件格式不正确",
  PARSE_ERROR: "文件解析失败",
  REPORT_NOT_GENERATED: "尚未生成报告",
};

/**
 * Try to parse a response body as an error envelope.
 * Returns the ServerError if parsing succeeds, null otherwise.
 */
export function parseErrorEnvelope(body: unknown): ServerError | null {
  if (
    body &&
    typeof body === "object" &&
    "error" in body &&
    typeof (body as ErrorEnvelope).error === "object"
  ) {
    return (body as ErrorEnvelope).error;
  }
  return null;
}

/** Get a user-friendly message for an error code. */
export function errorMessage(err: ServerError): string {
  return ERROR_LABELS[err.code] || err.message || "未知错误";
}

/** Returns true if the error represents an auth issue (should redirect to login). */
export function isAuthError(err: ServerError): boolean {
  return err.code === "UNAUTHORIZED";
}
