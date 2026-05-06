from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserUpdate,
    UserRead,
    PasswordChange,
)
from app.services.auth_service import authenticate_user, hash_password, verify_password
from app.core.security import create_access_token
from app.core.dependencies import get_current_user
from app.models.user import User
from typing import List

router = APIRouter()

VALID_ROLES = {"admin", "manager", "employee"}


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用",
        )
    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/users", response_model=UserRead)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role 必须是 {sorted(VALID_ROLES)} 之一")
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        dept=payload.dept,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/users", response_model=List[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"role 必须是 {sorted(VALID_ROLES)} 之一")
        # Prevent the last admin from demoting themselves
        if user.role == "admin" and payload.role != "admin" and user.id == current_user.id:
            others = await db.execute(
                select(User).where(User.role == "admin", User.id != user.id, User.is_active.is_(True))
            )
            if not others.scalars().first():
                raise HTTPException(status_code=400, detail="不能移除最后一个管理员")
        user.role = payload.role
    if payload.dept is not None:
        user.dept = payload.dept or None
    if payload.email is not None:
        user.email = payload.email or None
    if payload.is_active is not None:
        if user.id == current_user.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="不能禁用自己")
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-disable a user (sets is_active = False). Hard delete is intentionally not exposed."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = False
    await db.commit()
    return {"message": "用户已禁用"}


@router.post("/change-password")
async def change_password(
    payload: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return {"message": "密码修改成功"}
