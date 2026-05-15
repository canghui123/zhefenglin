"""列出待审核的内测申请。

用法::

    cd backend
    python -m scripts.list_access_requests
    python -m scripts.list_access_requests --status pending
    python -m scripts.list_access_requests --status all --limit 50

审核通过后用 `python -m scripts.create_admin` 或手工 INSERT 设置
`access_requests.status = 'approved'` 并发送开通邮件。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from sqlalchemy import select

from db.session import get_sessionmaker, reset_engine
from db.models.access_request import AccessRequest


def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List access requests")
    parser.add_argument(
        "--status",
        choices=("pending", "approved", "rejected", "contacted", "all"),
        default="pending",
    )
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    reset_engine()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        stmt = select(AccessRequest).order_by(AccessRequest.created_at.desc())
        if args.status != "all":
            stmt = stmt.where(AccessRequest.status == args.status)
        stmt = stmt.limit(args.limit)
        rows = list(session.scalars(stmt).all())

    if not rows:
        print(f"(无 {args.status} 申请)")
        return 0

    print(
        f"{'ID':>4}  {'状态':<10}  {'邮箱':<32}  {'公司':<24}  {'联系人':<12}  {'提交时间':<16}"
    )
    print("-" * 110)
    for r in rows:
        print(
            f"{r.id:>4}  {r.status:<10}  {r.email:<32.32}  {r.company:<24.24}  "
            f"{r.contact_name:<12.12}  {_fmt(r.created_at):<16}"
        )
    print(f"\n共 {len(rows)} 条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
