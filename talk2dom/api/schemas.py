from pydantic import BaseModel, UUID4, EmailStr
from typing import Optional, List
from datetime import datetime


class LocatorRequest(BaseModel):
    url: str
    html: str
    user_instruction: str
    conversation_history: Optional[List[List[str]]] = None
    # model: Optional[str] = "gpt-4o"
    # model_provider: Optional[str] = "openai"


class LocatorResponse(BaseModel):
    selector_type: str
    selector_value: str


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID4
    name: str
    description: Optional[str] = None
    owner_id: UUID4
    created_at: datetime
    owner_email: Optional[str] = None
    member_count: Optional[int] = None
    api_calls: Optional[int] = None
    is_active: Optional[bool] = None

    class Config:
        orm_mode = True


class InviteRequest(BaseModel):
    email: EmailStr
    role: Optional[str] = "member"  # or 'admin'


class MemberResponse(BaseModel):
    user_id: UUID4
    email: EmailStr
    role: str

    class Config:
        orm_mode = True


class InviteResponse(BaseModel):
    id: UUID4
    email: str
    invited_by_user_id: UUID4
    created_at: datetime
    accepted: bool

    class Config:
        orm_mode = True


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
