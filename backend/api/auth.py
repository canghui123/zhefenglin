"""Authentication endpoints — login, logout, register, me."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from config import settings
from db.models.user import User
from db.session import get_db_session
from dependencies.auth import SESSION_COOKIE_NAME, get_current_user
from repositories import user_repo, tenant_repo
from services import audit_service  # noqa: F401
from services import entitlement_service
from services import trial_onboarding
from services.auth_service import AuthError, authenticate, revoke
from services.password_service import hash_password
from services.password_policy import WeakPasswordError, validate_password_strength
from services import rate_limit_service
from services.runtime_security import is_production_like


router = APIRouter(prefix="/api/auth", tags=["认证"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None
    # 用户必须勾选"同意服务条款与隐私须知"；后端强制校验，防止绕过前端
    agreed_to_terms: bool = False

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("请输入有效的邮箱地址")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        # 粗校验（长度下限）；强度由 register 入口调用 password_policy 精校
        if not isinstance(v, str) or len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        return v


class UserOut(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    role: str
    last_login_at: Optional[datetime] = None
    feature_capabilities: dict[str, bool] = {}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


def _user_out(session: Session, u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        role=u.role,
        last_login_at=u.last_login_at,
        feature_capabilities=entitlement_service.build_feature_capabilities(
            session, tenant_id=u.default_tenant_id
        ),
    )


@router.post("/register", response_model=LoginResponse)
def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db_session),
):
    # 生产期建议关闭公开注册，引导走 /api/auth/access-request 申请制
    if not settings.allow_public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前仅支持邀请注册，请先提交申请",
        )

    rate_limit_service.enforce_request_limit(
        request,
        scope="auth.register",
        limit=settings.rate_limit_register_max_requests,
    )
    if not req.agreed_to_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先阅读并同意《服务使用须知》",
        )
    # 强度校验：长度 ≥ 10，三类字符，非常见弱密，不含邮箱名
    try:
        validate_password_strength(
            req.password, email=req.email, display_name=req.display_name
        )
    except WeakPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    existing = user_repo.get_user_by_email(session, email=req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已被注册",
        )

    display_name = req.display_name or req.email.split("@")[0]
    # SaaS 试用模式 → user.role=operator(独立 tenant 内可做业务,
    # 但 admin 后台仍由 user.role=admin 把守)。legacy 模式 → viewer,
    # 保留原 access-request 审核流程的最小权限默认。
    initial_role = (
        "operator" if trial_onboarding.is_trial_mode_enabled() else "viewer"
    )
    new_user = user_repo.create_user(
        session,
        email=req.email,
        password_hash=hash_password(req.password),
        role=initial_role,
        display_name=display_name,
    )
    # 记录用户同意服务条款的时间 + 版本，留存合规证据
    new_user.terms_accepted_at = datetime.now(timezone.utc)
    new_user.terms_version = settings.terms_version

    # task #5: SaaS 默认走"独立试用 tenant + trial_poc 订阅";私有化部署可设
    # TRIAL_ONBOARDING_MODE=legacy 退回到老的"挂到 default 租户" 行为。
    if trial_onboarding.is_trial_mode_enabled():
        trial_onboarding.create_trial_environment(
            session,
            user=new_user,
            display_name=display_name,
            trial_days=int(getattr(settings, "trial_days", 30)),
            monthly_budget_limit=float(getattr(settings, "trial_monthly_budget_limit", 200.0)),
        )
    else:
        # legacy: 所有注册用户挂到 default_registration_tenant_code,viewer 角色
        default_tenant = tenant_repo.get_or_create_tenant(
            session,
            code=settings.default_registration_tenant_code.strip() or "default",
            name=settings.default_registration_tenant_name.strip() or "默认租户",
        )
        user_repo.set_default_tenant(session, new_user.id, default_tenant.id)
        tenant_repo.create_membership(
            session, user_id=new_user.id, tenant_id=default_tenant.id, role="viewer"
        )
    session.commit()

    issued = authenticate(
        session,
        email=req.email,
        password=req.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    max_age = max(
        int((issued.expires_at - datetime.now(timezone.utc)).total_seconds()),
        0,
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=issued.access_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=is_production_like(),
        path="/",
    )

    return LoginResponse(
        access_token=issued.access_token,
        expires_at=issued.expires_at,
        user=_user_out(session, issued.user),
    )


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db_session),
):
    rate_limit_service.enforce_request_limit(
        request,
        scope="auth.login",
        limit=settings.rate_limit_login_max_requests,
    )
    # 账号粒度锁定：如果连续失败超过阈值，直接拒绝，哪怕密码这次正确
    # —— 防止 IP 轮换的凭据填充攻击绕过 IP 级限流
    rate_limit_service.check_and_raise_if_locked("auth.login", req.email)

    try:
        issued = authenticate(
            session,
            email=req.email,
            password=req.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AuthError:
        fails = rate_limit_service.record_login_failure("auth.login", req.email)
        # Best-effort failure audit so brute-force shows up in the log.
        try:
            audit_service.record(
                session,
                request,
                action="login",
                tenant_id=None,
                user_id=None,
                resource_type="user",
                resource_id=None,
                status="failure",
                after={"email": req.email, "fails": fails},
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    # 登录成功：清零失败计数
    rate_limit_service.record_login_success("auth.login", req.email)

    audit_service.record(
        session,
        request,
        action="login",
        tenant_id=issued.user.default_tenant_id,
        user_id=issued.user.id,
        resource_type="user",
        resource_id=issued.user.id,
        after={"email": issued.user.email, "role": issued.user.role},
    )

    # Set HttpOnly cookie so the browser carries the session automatically.
    max_age = max(
        int((issued.expires_at - datetime.now(timezone.utc)).total_seconds()),
        0,
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=issued.access_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=is_production_like(),
        path="/",
    )

    return LoginResponse(
        access_token=issued.access_token,
        expires_at=issued.expires_at,
        user=_user_out(session, issued.user),
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_db_session),
):
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    auth_header = request.headers.get("authorization")
    token: Optional[str] = None
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif cookie:
        token = cookie

    if token:
        revoke(session, token)

    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    return _user_out(session, user)
