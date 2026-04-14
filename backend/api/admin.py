"""Admin endpoints — user management."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role


router = APIRouter(prefix="/api/admin", tags=["管理"])


class UserOut(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: str
    last_login_at: Optional[str] = None


class RoleUpdate(BaseModel):
    role: str


class ActiveUpdate(BaseModel):
    is_active: bool


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at.isoformat() if u.created_at else "",
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )


@router.get("/users", response_model=List[UserOut])
def list_users(
    session: Session = Depends(get_db_session),
    _admin: User = Depends(require_role("admin")),
):
    users = session.scalars(select(User).order_by(User.id)).all()
    return [_user_out(u) for u in users]


@router.put("/users/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: int,
    req: RoleUpdate,
    session: Session = Depends(get_db_session),
    admin: User = Depends(require_role("admin")),
):
    if req.role not in ("viewer", "operator", "manager", "admin"):
        raise HTTPException(status_code=400, detail="无效的角色")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id and req.role != "admin":
        raise HTTPException(status_code=400, detail="不能降低自己的权限")
    user.role = req.role
    session.flush()
    return _user_out(user)


@router.put("/users/{user_id}/active", response_model=UserOut)
def toggle_active(
    user_id: int,
    req: ActiveUpdate,
    session: Session = Depends(get_db_session),
    admin: User = Depends(require_role("admin")),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id and not req.is_active:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")
    user.is_active = req.is_active
    session.flush()
    return _user_out(user)
