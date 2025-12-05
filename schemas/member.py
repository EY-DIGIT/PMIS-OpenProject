"""
Pydantic schemas for Member model.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional


class MemberBase(BaseModel):
    """Base member schema"""
    user_id: int
    project_id: int
    role_ids: List[int] = Field(..., min_items=1, description="At least one role is required")


class MemberCreate(MemberBase):
    """Schema for creating a new member"""
    pass


class MemberUpdate(BaseModel):
    """Schema for updating member roles"""
    role_ids: List[int] = Field(..., min_items=1, description="At least one role is required")


class RoleInfo(BaseModel):
    """Basic role information"""
    id: int
    name: str

    class Config:
        from_attributes = True


class MemberResponse(BaseModel):
    """Schema for member response"""
    id: int
    user_id: int
    project_id: int
    roles: List[RoleInfo]
    created_at: int
    updated_at: int

    class Config:
        from_attributes = True
