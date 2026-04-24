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
from services.auth_service import AuthError, authenticate, revoke
from services.password_service import hash_password


router = APIRouter(prefix="/api/auth", tags=["认证"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None

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
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        return v


class UserOut(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    role: str
    last_login_at: Optional[datetime] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        role=u.role,
        last_login_at=u.last_login_at,
    )


@router.post("/register", response_model=LoginResponse)
def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db_session),
):
    existing = user_repo.get_user_by_email(session, email=req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已被注册",
        )

    new_user = user_repo.create_user(
        session,
        email=req.email,
        password_hash=hash_password(req.password),
        role="viewer",
        display_name=req.display_name or req.email.split("@")[0],
    )

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
        secure=False,
        path="/",
    )

    return LoginResponse(
        access_token=issued.access_token,
        expires_at=issued.expires_at,
        user=_user_out(issued.user),
    )


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db_session),
):
    try:
        issued = authenticate(
            session,
            email=req.email,
            password=req.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AuthError:
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
                after={"email": req.email},
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

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
        secure=False,  # set to True behind HTTPS in production
        path="/",
    )

    return LoginResponse(
        access_token=issued.access_token,
        expires_at=issued.expires_at,
        user=_user_out(issued.user),
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
def me(user: User = Depends(get_current_user)):
    return _user_out(user)
