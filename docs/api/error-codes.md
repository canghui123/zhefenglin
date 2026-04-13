# API Error Codes

All API errors return a standard JSON envelope:

```json
{
  "error": {
    "code": "ASSET_PACKAGE_NOT_FOUND",
    "message": "资产包不存在",
    "request_id": "a1b2c3d4...",
    "details": {}
  }
}
```

## Error Code Reference

| Code | HTTP Status | Message | Description |
|------|-------------|---------|-------------|
| `UNAUTHORIZED` | 401 | 未登录或会话已过期 | Missing or invalid authentication token |
| `FORBIDDEN` | 403 | 权限不足 | User lacks required role for the operation |
| `VALIDATION_ERROR` | 422 | 请求参数校验失败 | Request body or query params failed validation |
| `ASSET_PACKAGE_NOT_FOUND` | 404 | 资产包不存在 | Package ID does not exist or belongs to another tenant |
| `SANDBOX_RESULT_NOT_FOUND` | 404 | 模拟结果不存在 | Simulation result not found |
| `JOB_NOT_FOUND` | 404 | 任务不存在 | Job ID does not exist or belongs to another tenant |
| `FILE_NOT_FOUND` | 404 | 文件不存在 | Referenced storage object is missing |
| `INVALID_FILE_FORMAT` | 400 | 仅支持.xlsx或.xls文件 | Uploaded file has wrong extension |
| `PARSE_ERROR` | 400 | Excel解析失败 | Could not parse the uploaded Excel file |
| `REPORT_NOT_GENERATED` | 404 | 尚未生成报告 | Report has not been generated yet for this result |

## Validation Error Details

When `code` is `VALIDATION_ERROR`, the `details` field contains a `errors` array in Pydantic V2 format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数校验失败",
    "request_id": "...",
    "details": {
      "errors": [
        {
          "type": "missing",
          "loc": ["body", "package_id"],
          "msg": "Field required",
          "input": {}
        }
      ]
    }
  }
}
```

## Request ID

Every response includes a `request_id` that can be used to correlate logs and audit records. Pass `X-Request-Id` header to supply your own correlation ID.
