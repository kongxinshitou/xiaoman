from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "employee"          # admin | manager | employee
    dept: Optional[str] = None      # department code (see /admin/depts)


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    dept: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None  # admin can reset another user's password


class UserRead(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    role: str
    dept: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
