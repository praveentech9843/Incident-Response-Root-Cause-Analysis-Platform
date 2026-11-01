from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., pattern=EMAIL_REGEX)
    role: str = Field(default="DEVELOPER")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., pattern=EMAIL_REGEX)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="DEVELOPER")


class UserUpdateRole(BaseModel):
    role: str = Field(..., pattern="^(ADMIN|DEVELOPER|VIEWER)$")


class UserUpdateStatus(BaseModel):
    is_active: bool


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    total: int
    users: List[UserResponse]
