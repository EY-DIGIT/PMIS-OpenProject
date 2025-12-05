"""
Pydantic schemas for Project model.
"""
from pydantic import BaseModel, Field, validator, constr
from typing import Optional, Dict
from enum import Enum


class WorkspaceTypeEnum(str, Enum):
    """Workspace type enumeration"""
    project = "project"
    program = "program"
    portfolio = "portfolio"


class StatusCodeEnum(int, Enum):
    """Project status code enumeration"""
    on_track = 0
    at_risk = 1
    off_track = 2
    not_started = 3
    finished = 4
    discontinued = 5


class ProjectBase(BaseModel):
    """Base project schema with common fields"""
    name: constr(min_length=1, max_length=255)
    identifier: constr(min_length=1, max_length=100, pattern=r'^[a-z0-9\-_]+$')
    description: Optional[str] = None
    public: bool = True
    active: bool = True
    templated: bool = False
    parent_id: Optional[int] = None
    workspace_type: WorkspaceTypeEnum = WorkspaceTypeEnum.project
    status_code: Optional[StatusCodeEnum] = None
    status_explanation: Optional[str] = None
    settings: Dict = Field(default_factory=dict)

    @validator('identifier')
    def validate_identifier(cls, v):
        """Additional validation for identifier"""
        if v.isdigit():
            raise ValueError("Identifier cannot be purely numeric")
        if v in ['new', 'menu', 'queries', 'export_list_modal']:
            raise ValueError(f"Identifier '{v}' is reserved")
        return v

    class Config:
        use_enum_values = True


class ProjectCreate(ProjectBase):
    """Schema for creating a new project"""
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project"""
    name: Optional[constr(min_length=1, max_length=255)] = None
    description: Optional[str] = None
    public: Optional[bool] = None
    active: Optional[bool] = None
    parent_id: Optional[int] = None
    status_code: Optional[StatusCodeEnum] = None
    status_explanation: Optional[str] = None
    settings: Optional[Dict] = None

    class Config:
        use_enum_values = True


class ProjectResponse(ProjectBase):
    """Schema for project response"""
    id: int
    lft: Optional[int] = None
    rgt: Optional[int] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

    class Config:
        from_attributes = True
        use_enum_values = True
