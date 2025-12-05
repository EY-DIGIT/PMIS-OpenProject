# OpenProject → FastAPI Project Module Implementation Guide

**Version**: Based on OpenProject stable/16 branch
**Target**: Python 3.10+ / FastAPI / SQLAlchemy / PostgreSQL

---

## 1. Technical Overview

### 1.1 Core Components

```
┌──────────────────────────────────────────────────────────────┐
│                      PROJECT MODULE                           │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐         │
│  │  Project   │──│   Member    │──│ MemberRole   │         │
│  │            │  │             │  │              │         │
│  │ - name     │  │ - user_id   │  │ - role_id    │         │
│  │ - identifier│ │ - project_id│  │ - inherited_│         │
│  │ - active   │  │ - entity_*  │  │   from       │         │
│  │ - public   │  └─────────────┘  └──────────────┘         │
│  │ - parent_id│        │                  │                 │
│  │ - lft/rgt  │        │                  │                 │
│  └────────────┘        │                  │                 │
│       │                └──────────────────┘                 │
│       │                         │                            │
│       │                   ┌─────────┐                       │
│       │                   │  Role   │                       │
│       │                   │         │                       │
│       │                   │ - name  │                       │
│       │                   │ - perms │                       │
│       │                   └─────────┘                       │
│       │                                                      │
│  ┌────────────────┐                                         │
│  │ EnabledModule  │                                         │
│  │                │                                         │
│  │ - project_id   │                                         │
│  │ - name         │                                         │
│  └────────────────┘                                         │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Data Model Quick Reference

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **Project** | Core project entity | id, name, identifier, parent_id, lft/rgt, active, public |
| **Member** | User-Project junction | user_id, project_id, entity_type/id |
| **MemberRole** | Member-Role junction | member_id, role_id, inherited_from |
| **Role** | Permission container | name, builtin, permissions |
| **RolePermission** | Role-Permission junction | role_id, permission |
| **EnabledModule** | Project feature flags | project_id, name |

---

## 2. Database Schema

### 2.1 Core Tables DDL

```sql
-- Projects table with nested set for hierarchy
CREATE TABLE projects (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    identifier VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    public BOOLEAN NOT NULL DEFAULT true,
    active BOOLEAN NOT NULL DEFAULT true,
    templated BOOLEAN NOT NULL DEFAULT false,
    parent_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    lft INTEGER,  -- Nested set left boundary
    rgt INTEGER,  -- Nested set right boundary
    workspace_type VARCHAR(20) NOT NULL DEFAULT 'project',
    status_code INTEGER,
    status_explanation TEXT,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT identifier_format CHECK (identifier ~ '^[a-z0-9\-_]+$'),
    CONSTRAINT identifier_not_numeric CHECK (identifier !~ '^\d+$'),
    CONSTRAINT identifier_not_reserved CHECK (identifier NOT IN ('new', 'menu', 'queries', 'export_list_modal'))
);

CREATE INDEX idx_projects_active ON projects(active);
CREATE INDEX idx_projects_lft ON projects(lft);
CREATE INDEX idx_projects_rgt ON projects(rgt);
CREATE INDEX idx_projects_lft_rgt ON projects(lft, rgt);
CREATE INDEX idx_projects_parent_id ON projects(parent_id);

-- Members (junction between users/principals and projects)
CREATE TABLE members (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    entity_type VARCHAR(255),  -- Polymorphic: 'WorkPackage', 'ProjectQuery', or NULL
    entity_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_member_without_entity UNIQUE (user_id, project_id)
        WHERE entity_type IS NULL AND entity_id IS NULL,
    CONSTRAINT unique_member_with_entity UNIQUE (user_id, project_id, entity_type, entity_id)
);

CREATE INDEX idx_members_user_id ON members(user_id);
CREATE INDEX idx_members_project_id ON members(project_id);
CREATE INDEX idx_members_entity ON members(entity_type, entity_id);

-- Roles
CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(256) NOT NULL UNIQUE,
    position INTEGER NOT NULL DEFAULT 1,
    builtin INTEGER NOT NULL DEFAULT 0,
    type VARCHAR(30) NOT NULL DEFAULT 'Role',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Member-Role junction with inheritance tracking
CREATE TABLE member_roles (
    id BIGSERIAL PRIMARY KEY,
    member_id BIGINT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    inherited_from BIGINT REFERENCES member_roles(id) ON DELETE CASCADE,

    CONSTRAINT unique_member_role UNIQUE (member_id, role_id, inherited_from)
);

CREATE INDEX idx_member_roles_member_id ON member_roles(member_id);
CREATE INDEX idx_member_roles_role_id ON member_roles(role_id);
CREATE INDEX idx_member_roles_inherited_from ON member_roles(inherited_from);

-- Role Permissions
CREATE TABLE role_permissions (
    id BIGSERIAL PRIMARY KEY,
    permission VARCHAR(255) NOT NULL,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_role_permissions_role_id ON role_permissions(role_id);

-- Enabled Modules
CREATE TABLE enabled_modules (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,

    CONSTRAINT unique_enabled_module UNIQUE (project_id, name)
);

CREATE INDEX idx_enabled_modules_project_id ON enabled_modules(project_id);
CREATE INDEX idx_enabled_modules_name ON enabled_modules(name);
```

### 2.2 Enums

```python
from enum import Enum

class WorkspaceType(str, Enum):
    PROJECT = "project"
    PROGRAM = "program"
    PORTFOLIO = "portfolio"

class StatusCode(int, Enum):
    ON_TRACK = 0
    AT_RISK = 1
    OFF_TRACK = 2
    NOT_STARTED = 3
    FINISHED = 4
    DISCONTINUED = 5

class BuiltinRole(int, Enum):
    NON_BUILTIN = 0
    BUILTIN_NON_MEMBER = 1
    BUILTIN_ANONYMOUS = 2
```

---

## 3. SQLAlchemy Models

### 3.1 Project Model

```python
# models/project.py
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, validates
from datetime import datetime
import re

from .base import Base
from ..utils import slugify

class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    identifier = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    public = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
    templated = Column(Boolean, nullable=False, default=False)
    parent_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'))
    lft = Column(Integer)
    rgt = Column(Integer)
    workspace_type = Column(String(20), nullable=False, default='project')
    status_code = Column(Integer)
    status_explanation = Column(Text)
    settings = Column(JSONB, nullable=False, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent = relationship("Project", remote_side=[id], backref="children")
    members = relationship("Member", back_populates="project", cascade="all, delete-orphan")
    enabled_modules = relationship("EnabledModule", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_projects_active', 'active'),
        Index('idx_projects_lft', 'lft'),
        Index('idx_projects_rgt', 'rgt'),
        Index('idx_projects_lft_rgt', 'lft', 'rgt'),
        CheckConstraint("identifier ~ '^[a-z0-9\-_]+$'", name='identifier_format'),
        CheckConstraint("identifier !~ '^\d+$'", name='identifier_not_numeric'),
    )

    @validates('name')
    def validate_name(self, key, value):
        if not value or not value.strip():
            raise ValueError("Name cannot be empty")
        if len(value) > 255:
            raise ValueError("Name too long (max 255)")
        return value.strip()

    @validates('identifier')
    def validate_identifier(self, key, value):
        if not value:
            raise ValueError("Identifier required")
        if len(value) > 100:
            raise ValueError("Identifier too long (max 100)")
        if value.isdigit():
            raise ValueError("Identifier cannot be purely numeric")
        if not re.match(r'^[a-z0-9\-_]+$', value):
            raise ValueError("Identifier format invalid")
        if value in ['new', 'menu', 'queries', 'export_list_modal']:
            raise ValueError("Identifier is reserved")
        return value

    def is_visible(self, user):
        """Check if project visible to user"""
        return self.active and (self.public or user.admin or self.has_member(user))

    def has_member(self, user):
        """Check if user is member"""
        return any(m.user_id == user.id for m in self.members)

    def allows_to(self, user, permission: str):
        """Check if user has permission"""
        if user.admin:
            return True

        member = next((m for m in self.members if m.user_id == user.id), None)
        if not member:
            return self._check_non_member_permission(permission)

        return any(
            permission in role.get_permissions()
            for mr in member.member_roles
            for role in [mr.role] if role
        )

    def _check_non_member_permission(self, permission):
        """Check non-member role permissions for public projects"""
        if not self.public:
            return False
        # Implementation depends on role system setup
        return permission == 'view_project'

    def module_enabled(self, name: str):
        """Check if module enabled"""
        return any(m.name == name for m in self.enabled_modules)

    # Hierarchy helpers
    def ancestors(self, session):
        """Get all ancestor projects"""
        if not self.lft or not self.rgt:
            return []
        return session.query(Project).filter(
            Project.lft < self.lft,
            Project.rgt > self.rgt
        ).order_by(Project.lft).all()

    def descendants(self, session):
        """Get all descendant projects"""
        if not self.lft or not self.rgt:
            return []
        return session.query(Project).filter(
            Project.lft > self.lft,
            Project.rgt < self.rgt
        ).all()

    def is_leaf(self):
        """Check if project has no children"""
        return self.rgt - self.lft == 1 if self.lft and self.rgt else True

    def depth(self, session):
        """Get depth in hierarchy (0 = root)"""
        return len(self.ancestors(session))
```

### 3.2 Member & Role Models

```python
# models/member.py
from sqlalchemy import Column, Integer, String, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base

class Member(Base):
    __tablename__ = 'members'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'))
    entity_type = Column(String(255))
    entity_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    project = relationship("Project", back_populates="members")
    member_roles = relationship("MemberRole", back_populates="member", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_members_user_id', 'user_id'),
        Index('idx_members_project_id', 'project_id'),
        Index('idx_members_entity', 'entity_type', 'entity_id'),
    )

    @property
    def roles(self):
        """Get all roles (excluding invalid)"""
        return [mr.role for mr in self.member_roles if mr.role]

    @property
    def role_ids(self):
        """Get role IDs"""
        return [mr.role_id for mr in self.member_roles]

    def has_inherited_roles(self):
        """Check if member has inherited roles"""
        return any(mr.inherited_from is not None for mr in self.member_roles)


class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False, unique=True)
    position = Column(Integer, nullable=False, default=1)
    builtin = Column(Integer, nullable=False, default=0)
    type = Column(String(30), nullable=False, default='Role')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    member_roles = relationship("MemberRole", back_populates="role")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def get_permissions(self):
        """Get list of permission strings"""
        return [rp.permission for rp in self.role_permissions]

    def has_permission(self, permission: str):
        """Check if role has permission"""
        return permission in self.get_permissions()

    def is_builtin(self):
        """Check if built-in role"""
        return self.builtin != 0

    def is_deletable(self):
        """Check if can be deleted"""
        return not self.is_builtin() and len(self.member_roles) == 0


class MemberRole(Base):
    __tablename__ = 'member_roles'

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey('members.id', ondelete='CASCADE'), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    inherited_from = Column(Integer, ForeignKey('member_roles.id', ondelete='CASCADE'))

    # Relationships
    member = relationship("Member", back_populates="member_roles")
    role = relationship("Role", back_populates="member_roles")

    __table_args__ = (
        Index('idx_member_roles_member_id', 'member_id'),
        Index('idx_member_roles_role_id', 'role_id'),
        Index('idx_member_roles_inherited_from', 'inherited_from'),
    )


class RolePermission(Base):
    __tablename__ = 'role_permissions'

    id = Column(Integer, primary_key=True)
    permission = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    role = relationship("Role", back_populates="role_permissions")

    __table_args__ = (
        Index('idx_role_permissions_role_id', 'role_id'),
    )


class EnabledModule(Base):
    __tablename__ = 'enabled_modules'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="enabled_modules")

    __table_args__ = (
        Index('idx_enabled_modules_project_id', 'project_id'),
        Index('idx_enabled_modules_name', 'name'),
    )
```

---

## 4. Pydantic Schemas

```python
# schemas/project.py
from pydantic import BaseModel, Field, validator, constr
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class WorkspaceTypeEnum(str, Enum):
    project = "project"
    program = "program"
    portfolio = "portfolio"

class StatusCodeEnum(int, Enum):
    on_track = 0
    at_risk = 1
    off_track = 2
    not_started = 3
    finished = 4
    discontinued = 5

class ProjectBase(BaseModel):
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
        if v.isdigit():
            raise ValueError("Identifier cannot be purely numeric")
        if v in ['new', 'menu', 'queries', 'export_list_modal']:
            raise ValueError("Identifier is reserved")
        return v

class ProjectCreate(ProjectBase):
    """Schema for creating project"""
    pass

class ProjectUpdate(BaseModel):
    """Schema for updating project"""
    name: Optional[constr(min_length=1, max_length=255)] = None
    description: Optional[str] = None
    public: Optional[bool] = None
    active: Optional[bool] = None
    parent_id: Optional[int] = None
    status_code: Optional[StatusCodeEnum] = None
    status_explanation: Optional[str] = None
    settings: Optional[Dict] = None

class ProjectResponse(ProjectBase):
    """Schema for project response"""
    id: int
    lft: Optional[int] = None
    rgt: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Member Schemas
class MemberBase(BaseModel):
    user_id: int
    project_id: int
    role_ids: List[int] = Field(min_items=1)

class MemberCreate(MemberBase):
    pass

class MemberUpdate(BaseModel):
    role_ids: List[int] = Field(min_items=1)

class RoleInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class MemberResponse(BaseModel):
    id: int
    user_id: int
    project_id: int
    roles: List[RoleInfo]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Role Schemas
class RoleBase(BaseModel):
    name: constr(min_length=1, max_length=256)
    position: int = 1

class RoleCreate(RoleBase):
    permissions: List[str] = []

class RoleUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=256)] = None
    position: Optional[int] = None
    permissions: Optional[List[str]] = None

class RoleResponse(RoleBase):
    id: int
    builtin: int
    permissions: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

---

## 5. Service Layer

```python
# services/project_service.py
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models import Project, Member, MemberRole, Role, EnabledModule
from ..schemas import ProjectCreate, ProjectUpdate
from ..utils import ServiceResult

DEFAULT_MODULES = ['work_package_tracking', 'wiki', 'calendar', 'board']

class ProjectService:
    """Service for project operations"""

    def __init__(self, db: Session, user):
        self.db = db
        self.user = user

    def create_project(self, data: ProjectCreate) -> ServiceResult:
        """Create new project with validation and initialization"""
        # 1. Authorization
        if not self._can_create_project(data.parent_id):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to create project']}
            )

        # 2. Validate identifier uniqueness
        if self.db.query(Project).filter_by(identifier=data.identifier).first():
            return ServiceResult.failure_result(
                errors={'identifier': ['Identifier already exists']}
            )

        # 3. Validate parent if specified
        if data.parent_id:
            parent = self.db.query(Project).get(data.parent_id)
            if not parent:
                return ServiceResult.failure_result(
                    errors={'parent_id': ['Parent project not found']}
                )

        try:
            # 4. Create project
            project = Project(**data.dict())
            self.db.add(project)
            self.db.flush()

            # 5. Initialize project (members, modules)
            self._initialize_project(project)

            # 6. Update nested set values if has parent
            if project.parent_id:
                self._update_nested_set_on_create(project)

            self.db.commit()
            self.db.refresh(project)

            return ServiceResult.success_result(
                project,
                message="Project created successfully"
            )
        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'database': [str(e)]}
            )

    def update_project(self, project_id: int, data: ProjectUpdate) -> ServiceResult:
        """Update project"""
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']}
            )

        # Authorization
        if not project.allows_to(self.user, 'edit_project'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized']}
            )

        # Special check for archiving
        if data.active is not None and data.active != project.active:
            if not project.allows_to(self.user, 'archive_project'):
                return ServiceResult.failure_result(
                    errors={'authorization': ['Not authorized to archive']}
                )

        try:
            # Update fields
            for field, value in data.dict(exclude_unset=True).items():
                setattr(project, field, value)

            self.db.commit()
            self.db.refresh(project)

            return ServiceResult.success_result(
                project,
                message="Project updated successfully"
            )
        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'database': [str(e)]}
            )

    def archive_project(self, project_id: int) -> ServiceResult:
        """Archive project and all subprojects"""
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']}
            )

        if not project.allows_to(self.user, 'archive_project'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized']}
            )

        try:
            # Archive project
            project.active = False

            # Archive all active subprojects
            for child in project.children:
                if child.active:
                    child.active = False

            self.db.commit()

            return ServiceResult.success_result(
                project,
                message="Project archived successfully"
            )
        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'database': [str(e)]}
            )

    def copy_project(self, source_id: int, data: ProjectCreate,
                    copy_options: Dict[str, bool]) -> ServiceResult:
        """Copy project with selective data"""
        source = self.db.query(Project).get(source_id)
        if not source:
            return ServiceResult.failure_result(
                errors={'source': ['Source project not found']}
            )

        if not source.allows_to(self.user, 'copy_projects'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to copy']}
            )

        try:
            # Create new project
            project = Project(**data.dict())

            # Copy settings and status from source
            project.settings = source.settings.copy()
            if copy_options.get('status', False):
                project.status_code = source.status_code
                project.status_explanation = source.status_explanation

            self.db.add(project)
            self.db.flush()

            # Copy modules
            if copy_options.get('modules', True):
                for module in source.enabled_modules:
                    new_module = EnabledModule(project_id=project.id, name=module.name)
                    self.db.add(new_module)

            # Copy members
            if copy_options.get('members', False):
                for member in source.members:
                    new_member = Member(user_id=member.user_id, project_id=project.id)
                    self.db.add(new_member)
                    self.db.flush()

                    for mr in member.member_roles:
                        if not mr.inherited_from:  # Only copy direct roles
                            new_mr = MemberRole(member_id=new_member.id, role_id=mr.role_id)
                            self.db.add(new_mr)
            else:
                # At minimum, add creator as admin
                self._initialize_project(project)

            self.db.commit()
            self.db.refresh(project)

            return ServiceResult.success_result(
                project,
                message="Project copied successfully"
            )
        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'database': [str(e)]}
            )

    def _can_create_project(self, parent_id: Optional[int]) -> bool:
        """Check if user can create project"""
        if self.user.admin:
            return True

        # Check global permission (implementation depends on setup)
        # For now, allow if has parent and has add_subprojects permission
        if parent_id:
            parent = self.db.query(Project).get(parent_id)
            if parent and parent.allows_to(self.user, 'add_subprojects'):
                return True

        return False

    def _initialize_project(self, project: Project):
        """Initialize new project with defaults"""
        # Add creator as admin member
        admin_role = self.db.query(Role).filter_by(name="Project admin").first()
        if not admin_role:
            # Fallback: create basic admin role
            admin_role = Role(name="Project admin", position=1)
            self.db.add(admin_role)
            self.db.flush()

        member = Member(user_id=self.user.id, project_id=project.id)
        self.db.add(member)
        self.db.flush()

        member_role = MemberRole(member_id=member.id, role_id=admin_role.id)
        self.db.add(member_role)

        # Enable default modules
        for module_name in DEFAULT_MODULES:
            module = EnabledModule(project_id=project.id, name=module_name)
            self.db.add(module)

    def _update_nested_set_on_create(self, project: Project):
        """Update nested set values when creating child project"""
        # Simplified nested set update
        # In production, use library like sqlalchemy-mptt
        parent = project.parent
        if parent:
            project.lft = parent.rgt
            project.rgt = parent.rgt + 1

            # Update all affected nodes
            self.db.query(Project).filter(
                Project.lft >= parent.rgt
            ).update({Project.lft: Project.lft + 2})

            self.db.query(Project).filter(
                Project.rgt >= parent.rgt
            ).update({Project.rgt: Project.rgt + 2})
```

```python
# services/member_service.py
from typing import List
from sqlalchemy.orm import Session

from ..models import Member, MemberRole, Project, User, Group, GroupUser
from ..schemas import MemberCreate, MemberUpdate
from ..utils import ServiceResult

class MemberService:
    """Service for membership operations"""

    def __init__(self, db: Session, user):
        self.db = db
        self.user = user

    def add_member(self, project_id: int, data: MemberCreate) -> ServiceResult:
        """Add member to project"""
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']}
            )

        if not project.allows_to(self.user, 'manage_members'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized']}
            )

        # Validate principal
        principal = self.db.query(User).get(data.user_id)
        if not principal:
            return ServiceResult.failure_result(
                errors={'user': ['User not found']}
            )

        if principal.status != 1:  # Not active
            return ServiceResult.failure_result(
                errors={'user': ['User is not active']}
            )

        # Check if already member
        existing = self.db.query(Member).filter_by(
            user_id=data.user_id,
            project_id=project_id
        ).first()
        if existing:
            return ServiceResult.failure_result(
                errors={'member': ['User is already a member']}
            )

        try:
            # Create member
            member = Member(user_id=data.user_id, project_id=project_id)
            self.db.add(member)
            self.db.flush()

            # Add roles
            for role_id in data.role_ids:
                member_role = MemberRole(member_id=member.id, role_id=role_id)
                self.db.add(member_role)

            # Handle group membership (if principal is group)
            if isinstance(principal, Group):
                self._create_inherited_roles(member, principal, data.role_ids)

            self.db.commit()
            self.db.refresh(member)

            return ServiceResult.success_result(
                member,
                message="Member added successfully"
            )
        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'database': [str(e)]}
            )

    def update_member(self, member_id: int, data: MemberUpdate) -> ServiceResult:
        """Update member roles"""
        member = self.db.query(Member).get(member_id)
        if not member:
            return ServiceResult.failure_result(
                errors={'member': ['Member not found']}
            )

        if not member.project.allows_to(self.user, 'manage_members'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized']}
            )

        try:
            # Remove existing direct roles (keep inherited)
            for mr in member.member_roles:
                if mr.inherited_from is None:
                    self.db.delete(mr)

            # Add new roles
            for role_id in data.role_ids:
                member_role = MemberRole(member_id=member.id, role_id=role_id)
                self.db.add(member_role)

            self.db.commit()
            self.db.refresh(member)

            return ServiceResult.success_result(
                member,
                message="Member updated successfully"
            )
        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'database': [str(e)]}
            )

    def remove_member(self, member_id: int) -> ServiceResult:
        """Remove member from project"""
        member = self.db.query(Member).get(member_id)
        if not member:
            return ServiceResult.failure_result(
                errors={'member': ['Member not found']}
            )

        if not member.project.allows_to(self.user, 'manage_members'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized']}
            )

        try:
            # Check for inherited roles
            if member.has_inherited_roles():
                # Only remove direct roles
                for mr in list(member.member_roles):
                    if mr.inherited_from is None:
                        self.db.delete(mr)
            else:
                # Remove entire member
                self.db.delete(member)

            self.db.commit()

            return ServiceResult.success_result(
                message="Member removed successfully"
            )
        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'database': [str(e)]}
            )

    def _create_inherited_roles(self, group_member: Member, group: Group, role_ids: List[int]):
        """Create inherited roles for group users"""
        for group_user in group.group_users:
            # Get or create member for user
            user_member = self.db.query(Member).filter_by(
                user_id=group_user.user_id,
                project_id=group_member.project_id
            ).first()

            if not user_member:
                user_member = Member(
                    user_id=group_user.user_id,
                    project_id=group_member.project_id
                )
                self.db.add(user_member)
                self.db.flush()

            # Create inherited roles
            for role_id in role_ids:
                # Find the group's member_role
                group_mr = self.db.query(MemberRole).filter_by(
                    member_id=group_member.id,
                    role_id=role_id
                ).first()

                # Create inherited role
                inherited_mr = MemberRole(
                    member_id=user_member.id,
                    role_id=role_id,
                    inherited_from=group_mr.id
                )
                self.db.add(inherited_mr)
```

---

## 6. FastAPI Routers

```python
# routers/projects.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import Project
from ..schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from ..services import ProjectService
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/v3/projects", tags=["projects"])

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    public: Optional[bool] = Query(None, description="Filter by public status"),
    parent_id: Optional[int] = Query(None, description="Filter by parent project"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    offset: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all visible projects"""
    query = db.query(Project)

    # Visibility filter
    if not current_user.admin:
        user_project_ids = [m.project_id for m in current_user.members if m.project_id]
        query = query.filter(
            (Project.public == True) | (Project.id.in_(user_project_ids))
        )

    # Apply filters
    if active is not None:
        query = query.filter(Project.active == active)
    if public is not None:
        query = query.filter(Project.public == public)
    if parent_id is not None:
        query = query.filter(Project.parent_id == parent_id)

    # Sorting
    sort_column = getattr(Project, sort_by, Project.name)
    query = query.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())

    # Pagination
    projects = query.offset(offset).limit(page_size).all()

    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get single project"""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.is_visible(current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new project"""
    service = ProjectService(db, current_user)
    result = service.create_project(data)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update project"""
    service = ProjectService(db, current_user)
    result = service.update_project(project_id, data)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Archive project"""
    service = ProjectService(db, current_user)
    result = service.archive_project(project_id)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.post("/{project_id}/copy", response_model=ProjectResponse)
def copy_project(
    project_id: int,
    data: ProjectCreate,
    copy_members: bool = Query(False),
    copy_modules: bool = Query(True),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Copy project"""
    service = ProjectService(db, current_user)
    copy_options = {
        'members': copy_members,
        'modules': copy_modules,
    }
    result = service.copy_project(project_id, data, copy_options)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result
```

```python
# routers/members.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Member, Project
from ..schemas import MemberCreate, MemberUpdate, MemberResponse
from ..services import MemberService
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/v3", tags=["memberships"])

@router.get("/projects/{project_id}/memberships", response_model=List[MemberResponse])
def list_project_memberships(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List project memberships"""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.allows_to(current_user, 'view_members'):
        raise HTTPException(status_code=403, detail="Not authorized")

    return project.members


@router.post("/projects/{project_id}/memberships", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_membership(
    project_id: int,
    data: MemberCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Add member to project"""
    data.project_id = project_id
    service = MemberService(db, current_user)
    result = service.add_member(project_id, data)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.patch("/memberships/{member_id}", response_model=MemberResponse)
def update_membership(
    member_id: int,
    data: MemberUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update member roles"""
    service = MemberService(db, current_user)
    result = service.update_member(member_id, data)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.delete("/memberships/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_membership(
    member_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Remove member from project"""
    service = MemberService(db, current_user)
    result = service.remove_member(member_id)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return None
```

---

## 7. Integration with User Module

### 7.1 Shared Models

The User model from your existing user_service should be extended to support project relationships:

```python
# In user_service/models/user.py - add:

from sqlalchemy.orm import relationship

class User(Base):
    # ... existing fields ...

    # Add relationship to members
    members = relationship("Member", back_populates="user", foreign_keys="Member.user_id")

    @property
    def projects(self):
        """Get all projects user is member of"""
        return [m.project for m in self.members if m.project]
```

### 7.2 Authentication Integration

```python
# dependencies/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from user_service.models import User

security = HTTPBearer()

def get_current_user(
    credentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials

    # Validate JWT token (implement your token validation)
    user_id = validate_token(token)  # Your implementation

    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    if user.status != 1:  # Not active
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )

    return user
```

### 7.3 Permission System Integration

```python
# utils/permissions.py
from typing import List

# Core project permissions
PROJECT_PERMISSIONS = {
    'view_project': 'View project',
    'edit_project': 'Edit project settings',
    'edit_project_attributes': 'Edit project custom fields',
    'manage_members': 'Manage project members',
    'view_members': 'View project members',
    'add_subprojects': 'Create subprojects',
    'archive_project': 'Archive project',
    'copy_projects': 'Copy project',
}

# Global permissions
GLOBAL_PERMISSIONS = {
    'add_project': 'Create new projects',
    'add_portfolios': 'Create portfolios',
    'add_programs': 'Create programs',
}

def seed_default_roles(db):
    """Seed default roles with permissions"""
    from ..models import Role, RolePermission

    roles_data = [
        {
            'name': 'Project admin',
            'position': 1,
            'permissions': [
                'view_project', 'edit_project', 'edit_project_attributes',
                'manage_members', 'view_members', 'add_subprojects',
                'archive_project', 'copy_projects'
            ]
        },
        {
            'name': 'Member',
            'position': 2,
            'permissions': ['view_project', 'view_members']
        },
        {
            'name': 'Reader',
            'position': 3,
            'permissions': ['view_project']
        }
    ]

    for role_data in roles_data:
        role = Role(name=role_data['name'], position=role_data['position'])
        db.add(role)
        db.flush()

        for perm in role_data['permissions']:
            rp = RolePermission(role_id=role.id, permission=perm)
            db.add(rp)

    db.commit()
```

---

## 8. Angular Integration

### 8.1 API Service

```typescript
// src/app/core/services/project-api.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Project {
  id: number;
  identifier: string;
  name: string;
  description?: string;
  active: boolean;
  public: boolean;
  status_code?: number;
  status_explanation?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectFilters {
  active?: boolean;
  public?: boolean;
  parent_id?: number;
}

@Injectable({
  providedIn: 'root'
})
export class ProjectApiService {
  private baseUrl = '/api/v3/projects';

  constructor(private http: HttpClient) {}

  listProjects(
    filters?: ProjectFilters,
    offset: number = 0,
    pageSize: number = 20
  ): Observable<Project[]> {
    let params = new HttpParams()
      .set('offset', offset.toString())
      .set('pageSize', pageSize.toString());

    if (filters) {
      if (filters.active !== undefined) {
        params = params.set('active', filters.active.toString());
      }
      if (filters.public !== undefined) {
        params = params.set('public', filters.public.toString());
      }
      if (filters.parent_id) {
        params = params.set('parent_id', filters.parent_id.toString());
      }
    }

    return this.http.get<Project[]>(this.baseUrl, { params });
  }

  getProject(id: number): Observable<Project> {
    return this.http.get<Project>(`${this.baseUrl}/${id}`);
  }

  createProject(project: Partial<Project>): Observable<Project> {
    return this.http.post<Project>(this.baseUrl, project);
  }

  updateProject(id: number, updates: Partial<Project>): Observable<Project> {
    return this.http.patch<Project>(`${this.baseUrl}/${id}`, updates);
  }

  archiveProject(id: number): Observable<Project> {
    return this.http.post<Project>(`${this.baseUrl}/${id}/archive`, {});
  }

  copyProject(
    id: number,
    newData: Partial<Project>,
    options?: { copyMembers?: boolean; copyModules?: boolean }
  ): Observable<Project> {
    let params = new HttpParams();
    if (options?.copyMembers) {
      params = params.set('copy_members', 'true');
    }
    if (options?.copyModules) {
      params = params.set('copy_modules', 'true');
    }

    return this.http.post<Project>(
      `${this.baseUrl}/${id}/copy`,
      newData,
      { params }
    );
  }
}
```

### 8.2 Membership Service

```typescript
// src/app/core/services/membership-api.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Member {
  id: number;
  user_id: number;
  project_id: number;
  roles: { id: number; name: string }[];
  created_at: string;
  updated_at: string;
}

@Injectable({
  providedIn: 'root'
})
export class MembershipApiService {
  private baseUrl = '/api/v3';

  constructor(private http: HttpClient) {}

  listProjectMembers(projectId: number): Observable<Member[]> {
    return this.http.get<Member[]>(
      `${this.baseUrl}/projects/${projectId}/memberships`
    );
  }

  addMember(
    projectId: number,
    userId: number,
    roleIds: number[]
  ): Observable<Member> {
    return this.http.post<Member>(
      `${this.baseUrl}/projects/${projectId}/memberships`,
      { user_id: userId, project_id: projectId, role_ids: roleIds }
    );
  }

  updateMember(memberId: number, roleIds: number[]): Observable<Member> {
    return this.http.patch<Member>(
      `${this.baseUrl}/memberships/${memberId}`,
      { role_ids: roleIds }
    );
  }

  removeMember(memberId: number): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/memberships/${memberId}`);
  }
}
```

### 8.3 Component Example

```typescript
// src/app/modules/projects/project-list/project-list.component.ts
import { Component, OnInit } from '@angular/core';
import { ProjectApiService, Project } from '../../../core/services/project-api.service';

@Component({
  selector: 'app-project-list',
  template: `
    <div class="project-list">
      <h2>Projects</h2>

      <div class="filters">
        <label>
          <input type="checkbox" [(ngModel)]="showArchived" (change)="loadProjects()">
          Show archived
        </label>
      </div>

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Identifier</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let project of projects">
            <td>{{ project.name }}</td>
            <td>{{ project.identifier }}</td>
            <td>
              <span [class.archived]="!project.active">
                {{ project.active ? 'Active' : 'Archived' }}
              </span>
            </td>
            <td>
              <button (click)="viewProject(project)">View</button>
              <button (click)="editProject(project)">Edit</button>
              <button *ngIf="project.active" (click)="archiveProject(project)">
                Archive
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
  styles: [`
    .archived { color: #999; }
  `]
})
export class ProjectListComponent implements OnInit {
  projects: Project[] = [];
  showArchived = false;

  constructor(private projectService: ProjectApiService) {}

  ngOnInit() {
    this.loadProjects();
  }

  loadProjects() {
    this.projectService.listProjects({
      active: this.showArchived ? undefined : true
    }).subscribe(
      projects => this.projects = projects
    );
  }

  viewProject(project: Project) {
    // Navigate to project view
  }

  editProject(project: Project) {
    // Navigate to project edit
  }

  archiveProject(project: Project) {
    if (confirm(`Archive project "${project.name}"?`)) {
      this.projectService.archiveProject(project.id).subscribe(
        () => this.loadProjects()
      );
    }
  }
}
```

---

## 9. Migration Strategy

### 9.1 Phase 1: Setup (Week 1)

1. **Database Setup**
   - Create project module tables
   - Seed default roles and permissions
   - Link to existing user tables

2. **Core Models**
   - Implement SQLAlchemy models
   - Add relationships to User model
   - Test model interactions

### 9.2 Phase 2: Backend API (Week 2-3)

1. **Basic CRUD**
   - Project create/read/update/delete
   - Member management
   - Permission checking

2. **Advanced Features**
   - Project hierarchies
   - Project copy
   - Archive/unarchive

### 9.3 Phase 3: Frontend Integration (Week 4)

1. **Update Angular Services**
   - Point to new FastAPI endpoints
   - Test with existing components

2. **Component Updates**
   - Minimal changes (mostly service injection)
   - Update data models if needed

### 9.4 Phase 4: Testing & Deployment (Week 5)

1. **Testing**
   - Unit tests
   - Integration tests
   - E2E tests with Angular

2. **Deployment**
   - Run both backends (Rails + FastAPI) with Nginx
   - Gradual rollout

---

## 10. File Structure

```
project_service/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── base.py
│   ├── project.py
│   ├── member.py
│   ├── role.py
│   └── enabled_module.py
├── schemas/
│   ├── __init__.py
│   ├── project.py
│   ├── member.py
│   └── role.py
├── services/
│   ├── __init__.py
│   ├── project_service.py
│   └── member_service.py
├── routers/
│   ├── __init__.py
│   ├── projects.py
│   └── members.py
├── dependencies/
│   ├── __init__.py
│   └── auth.py
├── utils/
│   ├── __init__.py
│   ├── permissions.py
│   ├── nested_set.py
│   └── service_result.py
└── main.py
```

---

## 11. Key Permissions Reference

```python
# Core project permissions
PERMISSIONS = {
    'view_project': {
        'description': 'View project',
        'public': True,
        'require': None
    },
    'edit_project': {
        'description': 'Edit project settings',
        'public': False,
        'require': 'member'
    },
    'manage_members': {
        'description': 'Manage project members',
        'public': False,
        'require': 'member'
    },
    'add_subprojects': {
        'description': 'Create subprojects',
        'public': False,
        'require': 'member'
    },
    'archive_project': {
        'description': 'Archive project',
        'public': False,
        'require': 'member'
    },
    'copy_projects': {
        'description': 'Copy project',
        'public': False,
        'require': 'member'
    },
}
```

---

## 12. Testing Strategy

### 12.1 Unit Tests

```python
# tests/test_project_service.py
import pytest
from sqlalchemy.orm import Session

from project_service.services import ProjectService
from project_service.schemas import ProjectCreate

def test_create_project(db: Session, admin_user):
    """Test project creation"""
    service = ProjectService(db, admin_user)

    data = ProjectCreate(
        name="Test Project",
        identifier="test-project",
        description="Test description"
    )

    result = service.create_project(data)

    assert result.is_success()
    assert result.result.name == "Test Project"
    assert result.result.identifier == "test-project"
    assert len(result.result.members) == 1  # Creator is member

def test_create_project_duplicate_identifier(db: Session, admin_user):
    """Test duplicate identifier rejection"""
    service = ProjectService(db, admin_user)

    data = ProjectCreate(
        name="Test Project",
        identifier="test-project"
    )

    # Create first project
    result1 = service.create_project(data)
    assert result1.is_success()

    # Try to create duplicate
    result2 = service.create_project(data)
    assert result2.is_failure()
    assert 'identifier' in result2.errors
```

### 12.2 Integration Tests

```python
# tests/test_project_api.py
from fastapi.testclient import TestClient

def test_list_projects(client: TestClient, auth_header):
    """Test project list endpoint"""
    response = client.get("/api/v3/projects", headers=auth_header)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_create_project_api(client: TestClient, auth_header):
    """Test project creation via API"""
    project_data = {
        "name": "API Test Project",
        "identifier": "api-test",
        "description": "Created via API"
    }

    response = client.post(
        "/api/v3/projects",
        json=project_data,
        headers=auth_header
    )

    assert response.status_code == 201
    data = response.json()
    assert data['name'] == "API Test Project"
    assert data['identifier'] == "api-test"
```

---

## Summary

This implementation guide provides:

1. ✅ **Complete data models** matching OpenProject stable/16
2. ✅ **SQLAlchemy models** with all relationships and constraints
3. ✅ **Pydantic schemas** for request/response validation
4. ✅ **Service layer** with business logic and authorization
5. ✅ **FastAPI routers** with OpenProject-compatible endpoints
6. ✅ **User module integration** via shared auth and models
7. ✅ **Angular integration** examples and migration path
8. ✅ **Permission system** with RBAC support
9. ✅ **Testing strategy** with unit and integration tests

**Next Steps:**
1. Copy models to your `user_service` directory structure
2. Run migrations to create tables
3. Seed default roles and permissions
4. Test endpoints with existing Angular frontend
5. Gradually migrate frontend components

**Key Differences from Rails:**
- Nested set updates simplified (consider using `sqlalchemy-mptt` library)
- No automatic callbacks (handle in services)
- JWT auth instead of session cookies (more scalable)
- Pydantic validation instead of ActiveRecord validations
