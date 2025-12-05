"""
Project model - Core project entity with hierarchy support.

Based on OpenProject stable/16 branch Project model.
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Index, CheckConstraint, JSON
from sqlalchemy.orm import relationship, validates
from datetime import datetime
import re

try:
    from ..database import Base
except ImportError:
    try:
        from database import Base
    except ImportError:
        from db_models import Base


class Project(Base):
    """
    Project model with hierarchy support via nested set.

    Attributes:
        id: Primary key
        name: Project name (required, max 255 chars)
        identifier: URL-safe unique identifier (lowercase, alphanumeric, dash, underscore)
        description: Optional project description
        public: Whether project is publicly visible
        active: Whether project is active (archived if False)
        templated: Whether project is a template
        parent_id: Parent project for hierarchy
        lft: Left boundary for nested set
        rgt: Right boundary for nested set
        workspace_type: Type of workspace (project/program/portfolio)
        status_code: Project status (0-5)
        status_explanation: Optional status explanation
        settings: JSON settings object
    """
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
    settings = Column(JSON, nullable=False, default=lambda: {})
    created_at = Column(Integer, default=lambda: int(datetime.utcnow().timestamp()))
    updated_at = Column(Integer, default=lambda: int(datetime.utcnow().timestamp()), onupdate=lambda: int(datetime.utcnow().timestamp()))

    # Relationships
    parent = relationship("Project", remote_side=[id], backref="children", foreign_keys=[parent_id])
    members = relationship("Member", back_populates="project", cascade="all, delete-orphan")
    enabled_modules = relationship("EnabledModule", back_populates="project", cascade="all, delete-orphan")

    # Table args with indexes and constraints
    __table_args__ = (
        Index('idx_projects_active', 'active'),
        Index('idx_projects_lft', 'lft'),
        Index('idx_projects_rgt', 'rgt'),
        Index('idx_projects_lft_rgt', 'lft', 'rgt'),
        Index('idx_projects_parent_id', 'parent_id'),
    )

    @validates('name')
    def validate_name(self, key, value):
        """Validate project name"""
        if not value or not value.strip():
            raise ValueError("Name cannot be empty")
        if len(value) > 255:
            raise ValueError("Name too long (max 255 characters)")
        return value.strip()

    @validates('identifier')
    def validate_identifier(self, key, value):
        """Validate project identifier"""
        if not value:
            raise ValueError("Identifier is required")
        if len(value) > 100:
            raise ValueError("Identifier too long (max 100 characters)")
        if value.isdigit():
            raise ValueError("Identifier cannot be purely numeric")
        if not re.match(r'^[a-z0-9\-_]+$', value):
            raise ValueError("Identifier must contain only lowercase letters, numbers, dashes, and underscores")
        if value in ['new', 'menu', 'queries', 'export_list_modal']:
            raise ValueError(f"Identifier '{value}' is reserved")
        return value

    def is_visible(self, user):
        """Check if project is visible to user"""
        if not self.active:
            return False
        if self.public:
            return True
        if user.admin:
            return True
        return self.has_member(user)

    def has_member(self, user):
        """Check if user is a member of this project"""
        return any(m.user_id == user.id for m in self.members)

    def allows_to(self, user, permission: str):
        """
        Check if user has specific permission in this project.

        Args:
            user: User object
            permission: Permission string (e.g., 'edit_project')

        Returns:
            True if user has permission, False otherwise
        """
        # Admins have all permissions
        if user.admin:
            return True

        # Find user's membership
        member = next((m for m in self.members if m.user_id == user.id), None)

        if not member:
            # Check non-member role for public projects
            if self.public and permission == 'view_project':
                return True
            return False

        # Check if any of the member's roles has the permission
        for member_role in member.member_roles:
            if member_role.role and permission in member_role.role.get_permissions():
                return True

        return False

    def module_enabled(self, name: str):
        """Check if a module is enabled for this project"""
        return any(m.name == name for m in self.enabled_modules)

    def ancestors(self, session):
        """Get all ancestor projects (parents, grandparents, etc.)"""
        if not self.lft or not self.rgt:
            return []
        return session.query(Project).filter(
            Project.lft < self.lft,
            Project.rgt > self.rgt
        ).order_by(Project.lft).all()

    def descendants(self, session):
        """Get all descendant projects (children, grandchildren, etc.)"""
        if not self.lft or not self.rgt:
            return []
        return session.query(Project).filter(
            Project.lft > self.lft,
            Project.rgt < self.rgt
        ).all()

    def is_leaf(self):
        """Check if project has no children"""
        if not self.lft or not self.rgt:
            return True
        return self.rgt - self.lft == 1

    def depth(self, session):
        """Get depth in hierarchy (0 = root)"""
        return len(self.ancestors(session))

    def is_archived(self):
        """Check if project is archived"""
        return not self.active

    def __repr__(self):
        return f"<Project(id={self.id}, identifier='{self.identifier}', name='{self.name}', active={self.active})>"
