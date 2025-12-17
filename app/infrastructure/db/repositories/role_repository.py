"""
Role repository for database operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from ...db.models.role import RoleModel
from ....domain.roles.role import Role


class RoleRepository:
    """Repository for Role database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def _to_domain(self, model: RoleModel) -> Role:
        """
        Convert database model to domain model.

        Args:
            model: Database model

        Returns:
            Domain model
        """
        return Role(
            id=model.id,
            name=model.name,
            permissions=model.permissions if isinstance(model.permissions, list) else [],
            builtin=model.builtin,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create(
        self,
        name: str,
        permissions: List[str],
        builtin: bool = False
    ) -> Role:
        """
        Create a new role.

        Args:
            name: Role name
            permissions: List of permissions
            builtin: Whether role is builtin

        Returns:
            Created role domain model
        """
        role_model = RoleModel(
            name=name,
            permissions=permissions,
            builtin=builtin,
        )

        self.db.add(role_model)
        self.db.commit()
        self.db.refresh(role_model)

        return self._to_domain(role_model)

    def get_by_id(self, role_id: int) -> Optional[Role]:
        """
        Get role by ID.

        Args:
            role_id: Role ID

        Returns:
            Role domain model if found, None otherwise
        """
        role_model = self.db.query(RoleModel).filter(RoleModel.id == role_id).first()

        if role_model:
            return self._to_domain(role_model)

        return None

    def get_by_name(self, name: str) -> Optional[Role]:
        """
        Get role by name.

        Args:
            name: Role name

        Returns:
            Role domain model if found, None otherwise
        """
        role_model = self.db.query(RoleModel).filter(RoleModel.name == name).first()

        if role_model:
            return self._to_domain(role_model)

        return None

    def list(self, offset: int = 0, limit: int = 20) -> Tuple[List[Role], int]:
        """
        List roles with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of roles, total count)
        """
        query = self.db.query(RoleModel)
        total = query.count()

        roles = query.offset(offset).limit(limit).all()

        return [self._to_domain(role) for role in roles], total

    def update(
        self,
        role_id: int,
        name: Optional[str] = None,
        permissions: Optional[List[str]] = None
    ) -> Optional[Role]:
        """
        Update a role.

        Args:
            role_id: Role ID
            name: New role name
            permissions: New permissions list

        Returns:
            Updated role domain model if found, None otherwise
        """
        role_model = self.db.query(RoleModel).filter(RoleModel.id == role_id).first()

        if not role_model:
            return None

        if name is not None:
            role_model.name = name

        if permissions is not None:
            role_model.permissions = permissions

        self.db.commit()
        self.db.refresh(role_model)

        return self._to_domain(role_model)

    def delete(self, role_id: int) -> bool:
        """
        Delete a role.

        Args:
            role_id: Role ID

        Returns:
            True if role was deleted, False otherwise
        """
        role_model = self.db.query(RoleModel).filter(RoleModel.id == role_id).first()

        if not role_model:
            return False

        self.db.delete(role_model)
        self.db.commit()

        return True

    def exists_by_name(self, name: str) -> bool:
        """
        Check if role exists by name.

        Args:
            name: Role name

        Returns:
            True if role exists, False otherwise
        """
        return self.db.query(
            self.db.query(RoleModel).filter(RoleModel.name == name).exists()
        ).scalar()

    def exists_by_id(self, role_id: int) -> bool:
        """
        Check if role exists by ID.

        Args:
            role_id: Role ID

        Returns:
            True if role exists, False otherwise
        """
        return self.db.query(
            self.db.query(RoleModel).filter(RoleModel.id == role_id).exists()
        ).scalar()
