"""
Project Members request/response schemas.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class MembershipRoleCreate(BaseModel):
    """Role reference for membership creation."""
    id: Optional[int] = None
    name: Optional[str] = None


class ProjectMemberAddRequest(BaseModel):
    """Request to add a user to a project."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user": {"id": 5},
                "roles": [
                    {"id": 1},
                    {"id": 2}
                ]
            }
        }
    )
    
    user: dict = Field(..., description="User reference")
    roles: List[dict] = Field(default_factory=list, description="Roles for the member")


class ProjectMemberUpdateRequest(BaseModel):
    """Request to update a membership."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "roles": [
                    {"id": 1},
                    {"id": 3}
                ]
            }
        }
    )
    
    roles: List[dict] = Field(..., description="New roles for the member")


class ProjectMembersListQuery(BaseModel):
    """Query parameters for listing project members."""
    offset: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(default=20, ge=1, le=100, description="Items per page")
