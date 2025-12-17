"""
Project Member repository for database operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from ...db.models.project_member import ProjectMemberModel
from ....domain.project_members.membership import Membership


class ProjectMemberRepository:
    """Repository for Project Member database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def _to_domain(self, model: ProjectMemberModel) -> Membership:
        """
        Convert database model to domain model.

        Args:
            model: Database model

        Returns:
            Domain model
        """
        return Membership(
            id=model.id,
            project_id=model.project_id,
            user_id=model.user_id,
            roles=model.roles or [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create(
        self,
        project_id: int,
        user_id: int,
        roles: List[str],
    ) -> Membership:
        """
        Create a new project member.

        Args:
            project_id: Project ID
            user_id: User ID
            roles: List of role names

        Returns:
            Created membership domain model
        """
        member_model = ProjectMemberModel(
            project_id=project_id,
            user_id=user_id,
            roles=roles or [],
        )

        self.db.add(member_model)
        self.db.commit()
        self.db.refresh(member_model)

        return self._to_domain(member_model)

    def get_by_id(self, membership_id: int) -> Optional[Membership]:
        """
        Get membership by ID.

        Args:
            membership_id: Membership ID

        Returns:
            Membership if found, None otherwise
        """
        model = self.db.query(ProjectMemberModel).filter(
            ProjectMemberModel.id == membership_id
        ).first()
        return self._to_domain(model) if model else None

    def get_by_project_and_user(self, project_id: int, user_id: int) -> Optional[Membership]:
        """
        Get membership by project and user.

        Args:
            project_id: Project ID
            user_id: User ID

        Returns:
            Membership if found, None otherwise
        """
        model = self.db.query(ProjectMemberModel).filter(
            ProjectMemberModel.project_id == project_id,
            ProjectMemberModel.user_id == user_id,
        ).first()
        return self._to_domain(model) if model else None

    def list_by_project(
        self,
        project_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Membership], int]:
        """
        List memberships for a project with pagination.

        Args:
            project_id: Project ID
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (memberships, total count)
        """
        query = self.db.query(ProjectMemberModel).filter(
            ProjectMemberModel.project_id == project_id
        )

        total = query.count()

        offset = (page - 1) * page_size
        models = query.offset(offset).limit(page_size).all()

        memberships = [self._to_domain(model) for model in models]

        return memberships, total

    def list_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Membership], int]:
        """
        List memberships for a user with pagination.

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (memberships, total count)
        """
        query = self.db.query(ProjectMemberModel).filter(
            ProjectMemberModel.user_id == user_id
        )

        total = query.count()

        offset = (page - 1) * page_size
        models = query.offset(offset).limit(page_size).all()

        memberships = [self._to_domain(model) for model in models]

        return memberships, total

    def update(
        self,
        membership_id: int,
        roles: List[str],
    ) -> Optional[Membership]:
        """
        Update a membership's roles.

        Args:
            membership_id: Membership ID
            roles: New list of role names

        Returns:
            Updated membership if found, None otherwise
        """
        model = self.db.query(ProjectMemberModel).filter(
            ProjectMemberModel.id == membership_id
        ).first()

        if not model:
            return None

        model.roles = roles or []
        self.db.commit()
        self.db.refresh(model)

        return self._to_domain(model)

    def delete(self, membership_id: int) -> bool:
        """
        Delete a membership.

        Args:
            membership_id: Membership ID

        Returns:
            True if deleted, False if not found
        """
        model = self.db.query(ProjectMemberModel).filter(
            ProjectMemberModel.id == membership_id
        ).first()

        if not model:
            return False

        self.db.delete(model)
        self.db.commit()

        return True

    def delete_by_project_and_user(self, project_id: int, user_id: int) -> bool:
        """
        Delete a membership by project and user.

        Args:
            project_id: Project ID
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        model = self.db.query(ProjectMemberModel).filter(
            ProjectMemberModel.project_id == project_id,
            ProjectMemberModel.user_id == user_id,
        ).first()

        if not model:
            return False

        self.db.delete(model)
        self.db.commit()

        return True

    def exists(self, project_id: int, user_id: int) -> bool:
        """
        Check if a membership exists.

        Args:
            project_id: Project ID
            user_id: User ID

        Returns:
            True if membership exists
        """
        return self.db.query(
            self.db.query(ProjectMemberModel).filter(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id,
            ).exists()
        ).scalar()
