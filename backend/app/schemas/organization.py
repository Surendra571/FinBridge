"""
Organization and Member Management Pydantic v2 Schemas.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

RoleType = Literal["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"]


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    settings: Optional[dict] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        clean = v.strip().lower()
        if not all(c.isalnum() or c in "-_" for c in clean):
            raise ValueError("Slug must contain only alphanumeric characters, dashes, and underscores")
        return clean

    @field_validator("base_currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.strip().upper()


class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    base_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    settings: Optional[dict] = None


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    base_currency: str
    settings: dict
    is_active: bool
    created_at: datetime


class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: RoleType = "ACCOUNTANT"


class MemberRoleUpdateRequest(BaseModel):
    role: RoleType


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class OrganizationMemberListResponse(BaseModel):
    organization: OrganizationResponse
    members: List[MemberResponse]
