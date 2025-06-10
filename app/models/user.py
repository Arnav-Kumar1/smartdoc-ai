from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from pydantic import EmailStr
from sqlalchemy import Boolean, Column

class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    email: str = Field(unique=True, index=True)
    username: str = Field(index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False, sa_column=Column(Boolean, default=False))
    gemini_api_key: Optional[str] = Field(default=None)

class UserCreate(SQLModel):
    email: str
    username: str
    password: str
    gemini_api_key: str

class UserLogin(SQLModel):
    email: str
    password: str

class UserResponse(SQLModel):
    id: UUID
    email: str
    username: str
    created_at: datetime
    is_active: bool
    is_admin: bool