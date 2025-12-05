"""
Pydantic schemas for Role model.
"""
from pydantic import BaseModel, constr
from typing import List, Optional


class RoleBase(BaseModel):
    """Base role schema"""
    name: constr(min_length=1, max_length=256)
    position: int = 1


class RoleCreate(RoleBase):
    """Schema for creating a new role"""
    permissions: List[str] = []


class RoleUpdate(BaseModel):
    """Schema for updating a role"""
    name: Optional[constr(min_length=1, max_length=256)] = None
    position: Optional[int] = None
    permissions: Optional[List[str]] = None


class RoleResponse(RoleBase):
    """Schema for role response"""
    id: int
    builtin: int
    permissions: List[str]
    created_at: int
    updated_at: int

    class Config:
        from_attributes = True
