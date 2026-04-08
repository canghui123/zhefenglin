"""Authentication endpoints — login, logout, me."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import SESSION_COOKIE_NAME, get_current_user
from services.auth_service import AuthError, authenticate, revoke


router = APIRouter(prefix="/api/auth", tags=["认证"])


class LoginRequest(BaseModel):
    email: str
    password: str


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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
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
