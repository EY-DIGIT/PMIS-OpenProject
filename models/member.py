"""
Member and related models - Handles project membership and roles.

Based on OpenProject stable/16 branch Member, MemberRole, Role, and RolePermission models.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

try:
    from ..database import Base
except ImportError:
    try:
        from database import Base
    except ImportError:
        from db_models import Base


class Member(Base):
    """
    Member model - Junction between User and Project.

    Supports both project-level membership and entity-specific membership
    (e.g., specific work package or query).

    Attributes:
        id: Primary key
        user_id: Reference to User (principal)
        project_id: Reference to Project (optional for entity-specific)
        entity_type: Type of entity (WorkPackage, ProjectQuery, or None)
        entity_id: ID of entity (if entity_type is set)
    """
    __tablename__ = 'members'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'))
    entity_type = Column(String(255))
    entity_id = Column(Integer)
    created_at = Column(Integer, default=lambda: int(datetime.utcnow().timestamp()))
    updated_at = Column(Integer, default=lambda: int(datetime.utcnow().timestamp()), onupdate=lambda: int(datetime.utcnow().timestamp()))

    # Relationships
    user = relationship("DBUser", foreign_keys=[user_id], backref="members")
    project = relationship("Project", back_populates="members")
    member_roles = relationship("MemberRole", back_populates="member", cascade="all, delete-orphan")

    # Table args with indexes
    __table_args__ = (
        Index('idx_members_user_id', 'user_id'),
        Index('idx_members_project_id', 'project_id'),
        Index('idx_members_entity', 'entity_type', 'entity_id'),
    )

    @property
    def roles(self):
        """Get all roles for this member (excluding invalid)"""
        return [mr.role for mr in self.member_roles if mr.role]

    @property
    def role_ids(self):
        """Get list of role IDs"""
        return [mr.role_id for mr in self.member_roles]

    def has_inherited_roles(self):
        """Check if member has any inherited roles (from group)"""
        return any(mr.inherited_from is not None for mr in self.member_roles)

    def __repr__(self):
        return f"<Member(id={self.id}, user_id={self.user_id}, project_id={self.project_id})>"


class MemberRole(Base):
    """
    MemberRole model - Junction between Member and Role.

    Supports role inheritance tracking via inherited_from field.

    Attributes:
        id: Primary key
        member_id: Reference to Member
        role_id: Reference to Role
        inherited_from: Reference to parent MemberRole (for group inheritance)
    """
    __tablename__ = 'member_roles'

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey('members.id', ondelete='CASCADE'), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    inherited_from = Column(Integer, ForeignKey('member_roles.id', ondelete='CASCADE'))

    # Relationships
    member = relationship("Member", back_populates="member_roles")
    role = relationship("Role", back_populates="member_roles")

    # Table args with indexes
    __table_args__ = (
        Index('idx_member_roles_member_id', 'member_id'),
        Index('idx_member_roles_role_id', 'role_id'),
        Index('idx_member_roles_inherited_from', 'inherited_from'),
    )

    def __repr__(self):
        inherited = f", inherited_from={self.inherited_from}" if self.inherited_from else ""
        return f"<MemberRole(id={self.id}, member_id={self.member_id}, role_id={self.role_id}{inherited})>"


class Role(Base):
    """
    Role model - Container for permissions.

    Roles can be custom or built-in. Built-in roles include:
    - Non-member (builtin=1)
    - Anonymous (builtin=2)

    Attributes:
        id: Primary key
        name: Role name (unique)
        position: Display order
        builtin: Built-in role type (0=custom, 1=non-member, 2=anonymous)
        type: STI type (default: 'Role')
    """
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False, unique=True)
    position = Column(Integer, nullable=False, default=1)
    builtin = Column(Integer, nullable=False, default=0)
    type = Column(String(30), nullable=False, default='Role')
    created_at = Column(Integer, default=lambda: int(datetime.utcnow().timestamp()))
    updated_at = Column(Integer, default=lambda: int(datetime.utcnow().timestamp()), onupdate=lambda: int(datetime.utcnow().timestamp()))

    # Relationships
    member_roles = relationship("MemberRole", back_populates="role")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def get_permissions(self):
        """Get list of permission strings for this role"""
        return [rp.permission for rp in self.role_permissions]

    def has_permission(self, permission: str):
        """Check if role has a specific permission"""
        return permission in self.get_permissions()

    def is_builtin(self):
        """Check if this is a built-in role"""
        return self.builtin != 0

    def is_deletable(self):
        """Check if role can be deleted (not built-in and no members)"""
        return not self.is_builtin() and len(self.member_roles) == 0

    def __repr__(self):
        builtin_str = f", builtin={self.builtin}" if self.builtin else ""
        return f"<Role(id={self.id}, name='{self.name}'{builtin_str})>"


class RolePermission(Base):
    """
    RolePermission model - Links roles to permissions.

    Permissions are stored as strings (e.g., 'view_project', 'edit_project').

    Attributes:
        id: Primary key
        permission: Permission string
        role_id: Reference to Role
    """
    __tablename__ = 'role_permissions'

    id = Column(Integer, primary_key=True)
    permission = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(Integer, default=lambda: int(datetime.utcnow().timestamp()))
    updated_at = Column(Integer, default=lambda: int(datetime.utcnow().timestamp()), onupdate=lambda: int(datetime.utcnow().timestamp()))

    # Relationships
    role = relationship("Role", back_populates="role_permissions")

    # Table args with indexes
    __table_args__ = (
        Index('idx_role_permissions_role_id', 'role_id'),
    )

    def __repr__(self):
        return f"<RolePermission(id={self.id}, permission='{self.permission}', role_id={self.role_id})>"
