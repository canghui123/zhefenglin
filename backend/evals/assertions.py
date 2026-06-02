"""B2 — 评测断言库。

设计原则:
- 断言只 print 失败原因,不抛异常(框架收集结果统一报告)
- 每个断言函数返回 (passed: bool, message: str)
- 断言类型用 YAML 里的 dict 表达,便于业务方扩展

支持的断言:
| 名称                  | 期望参数                           | 含义                           |
|-----------------------|------------------------------------|--------------------------------|
| field_equals          | path: str, value: Any              | output 某字段 == value         |
| field_in_range        | path: str, min: number, max: number| 数值字段 in [min, max]         |
| find_text             | in: str, substr: str               | 某 list/str 字段含子串         |
| find_any_text         | in: str, substrings: [str]         | 某字段含列表中任意一个子串     |
| list_length_min       | path: str, count: int              | 列表长度 >= count              |
| list_length_max       | path: str, count: int              | 列表长度 <= count              |
| forbidden_text        | in: str, substr: str               | 某字段**不应**含子串(语义反转)  |
"""

from __future__ import annotations

from typing import Any


def _get_path(data: Any, path: str) -> Any:
    """点分路径访问嵌套字段。

    示例:
        _get_path(obj, "summary") -> obj.summary or obj["summary"]
        _get_path(obj, "summary.tradeability_level") -> 深一层
    """
    cur = data
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def field_equals(output: Any, path: str, value: Any) -> tuple[bool, str]:
    actual = _get_path(output, path)
    ok = actual == value
    return ok, f"{path} = {actual!r}, expected {value!r}"


def field_in_range(output: Any, path: str, min: float, max: float) -> tuple[bool, str]:
    actual = _get_path(output, path)
    if actual is None or not isinstance(actual, (int, float)):
        return False, f"{path} = {actual!r}, not a number"
    ok = min <= actual <= max
    return ok, f"{path} = {actual}, expected in [{min}, {max}]"


def find_text(output: Any, in_: str, substr: str) -> tuple[bool, str]:
    """在某 list[str] 或 str 字段里查找子串。

    YAML 里 'in' 是关键字,所以 Python 函数参数用 in_。
    """
    field = _get_path(output, in_)
    if field is None:
        return False, f"{in_} 字段为 None,无法查找 {substr!r}"
    if isinstance(field, str):
        ok = substr in field
        return ok, f"在 {in_} 中查找 {substr!r}:{'找到' if ok else '未找到'}"
    if isinstance(field, list):
        ok = any(substr in str(item) for item in field)
        return ok, f"在 {in_}({len(field)} 项)中查找 {substr!r}:{'找到' if ok else '未找到'}"
    return False, f"{in_} 类型 {type(field).__name__} 不支持子串查找"


def find_any_text(output: Any, in_: str, substrings: list[str]) -> tuple[bool, str]:
    field = _get_path(output, in_)
    if field is None:
        return False, f"{in_} 字段为 None"
    text_blob = ""
    if isinstance(field, str):
        text_blob = field
    elif isinstance(field, list):
        text_blob = " | ".join(str(item) for item in field)
    matched = [s for s in substrings if s in text_blob]
    ok = bool(matched)
    return ok, f"在 {in_} 中查找任一 {substrings}:{'找到 ' + str(matched) if ok else '一个都没找到'}"


def list_length_min(output: Any, path: str, count: int) -> tuple[bool, str]:
    field = _get_path(output, path)
    actual = len(field) if isinstance(field, (list, str)) else None
    ok = actual is not None and actual >= count
    return ok, f"{path} 长度 = {actual}, expected >= {count}"


def list_length_max(output: Any, path: str, count: int) -> tuple[bool, str]:
    field = _get_path(output, path)
    actual = len(field) if isinstance(field, (list, str)) else None
    ok = actual is not None and actual <= count
    return ok, f"{path} 长度 = {actual}, expected <= {count}"


def forbidden_text(output: Any, in_: str, substr: str) -> tuple[bool, str]:
    """语义反转:某字段**不应**含子串。用于检查违禁语句(如"自动批准")。"""
    found_ok, _ = find_text(output, in_, substr)
    # 找到 -> 断言失败,没找到 -> 断言通过
    passed = not found_ok
    return passed, f"禁词 {substr!r} 在 {in_} 中{'出现(违禁!)' if found_ok else '未出现(OK)'}"


# 断言名 -> handler 映射,案例 YAML 直接用名字引用
ASSERTION_HANDLERS = {
    "field_equals": field_equals,
    "field_in_range": field_in_range,
    "find_text": find_text,
    "find_any_text": find_any_text,
    "list_length_min": list_length_min,
    "list_length_max": list_length_max,
    "forbidden_text": forbidden_text,
}


def run_assertion(output: Any, assertion: dict) -> tuple[bool, str, str]:
    """跑一条断言。assertion = {名称: 参数 dict}。

    返回:(passed, name, message)
    """
    if len(assertion) != 1:
        return False, "?", f"断言格式错误,应为 {{name: {{params...}}}},实际 {assertion}"
    name, params = next(iter(assertion.items()))
    handler = ASSERTION_HANDLERS.get(name)
    if not handler:
        return False, name, f"未知断言类型 {name!r}"
    if not isinstance(params, dict):
        return False, name, f"参数必须是 dict,实际 {type(params).__name__}"

    # YAML 'in' 关键字处理
    kwargs = dict(params)
    if "in" in kwargs:
        kwargs["in_"] = kwargs.pop("in")

    try:
        passed, msg = handler(output, **kwargs)
        return passed, name, msg
    except Exception as exc:  # noqa: BLE001
        return False, name, f"断言执行异常:{type(exc).__name__}: {exc}"
