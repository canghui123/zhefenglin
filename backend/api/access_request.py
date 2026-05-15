"""申请制内测：访客留资端点。

公开 `/api/auth/register` 在生产环境关闭后，访客通过
`POST /api/auth/access-request` 提交意向；运营/admin 在后台审核后
用 `scripts/create_admin.py` 开通账号，并通过邮件/企微告知访客。

为防止邮箱枚举和刷单：
- 命中率限流（每 IP 每小时最多若干次，受 rate_limit_access_request_max_requests 控制）
- 无论是否重复都返回相同的 202 响应
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from config import settings
from db.session import get_db_session
from repositories import access_request_repo
from services import rate_limit_service


router = APIRouter(prefix="/api/auth", tags=["认证"])


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[\d+\-\s()]{6,20}$")


class AccessRequestIn(BaseModel):
    email: str = Field(..., max_length=255)
    company: str = Field(..., min_length=1, max_length=255)
    contact_name: str = Field(..., min_length=1, max_length=64)
    phone: Optional[str] = Field(None, max_length=32)
    scenario: Optional[str] = Field(None, max_length=1000)
    source: Optional[str] = Field(None, max_length=64)
    # 必须勾选"同意服务条款与隐私须知"
    agreed_to_terms: bool = False

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("请输入有效的邮箱地址")
        return v

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not _PHONE_RE.match(v):
            raise ValueError("请输入有效的联系电话")
        return v


class AccessRequestOut(BaseModel):
    status: str = "accepted"
    message: str = "已收到您的申请，我们会在 2 个工作日内联系您"


@router.post(
    "/access-request",
    response_model=AccessRequestOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_access_request(
    req: AccessRequestIn,
    request: Request,
    session: Session = Depends(get_db_session),
):
    rate_limit_service.enforce_request_limit(
        request,
        scope="auth.access_request",
        limit=settings.rate_limit_access_request_max_requests,
    )

    if not req.agreed_to_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先阅读并同意《服务使用须知》",
        )

    # 幂等：若该邮箱 24h 内已有 pending 申请，不新建，直接返回成功
    # —— 同时防止外部枚举（响应对"新/旧"无法区分）
    existing = access_request_repo.get_latest_pending_by_email(session, req.email)
    if existing is None:
        access_request_repo.create_request(
            session,
            email=req.email,
            company=req.company,
            contact_name=req.contact_name,
            phone=req.phone,
            scenario=req.scenario,
            source=req.source,
            terms_version=settings.terms_version,
        )
        session.commit()

    return AccessRequestOut()
