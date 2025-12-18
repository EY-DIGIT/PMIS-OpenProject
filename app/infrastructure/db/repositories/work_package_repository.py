"""
Work Package repository for database operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from ...db.models.work_package import WorkPackageModel
from ....domain.work_packages.work_package import WorkPackage


class WorkPackageRepository:
    """Repository for Work Package database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def _to_domain(self, model: WorkPackageModel) -> WorkPackage:
        """
        Convert database model to domain model.

        Args:
            model: Database model

        Returns:
            Domain model
        """
        return WorkPackage(
            id=model.id,
            subject=model.subject,
            description=model.description,
            project_id=model.project_id,
            parent_id=model.parent_id,
            assignee_id=model.assignee_id,
            status=model.status,
            priority=model.priority,
            done_ratio=model.done_ratio,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create(
        self,
        subject: str,
        project_id: int,
        description: Optional[str] = None,
        parent_id: Optional[int] = None,
        assignee_id: Optional[int] = None,
        status: str = "new",
        priority: str = "normal",
        done_ratio: int = 0,
    ) -> WorkPackage:
        """
        Create a new work package.

        Args:
            subject: Work package subject/title
            project_id: Project ID
            description: Work package description
            parent_id: Parent work package ID (for subtasks)
            assignee_id: Assigned user ID
            status: Work package status
            priority: Work package priority
            done_ratio: Completion percentage (0-100)

        Returns:
            Created work package domain model
        """
        wp_model = WorkPackageModel(
            subject=subject,
            description=description,
            project_id=project_id,
            parent_id=parent_id,
            assignee_id=assignee_id,
            status=status,
            priority=priority,
            done_ratio=done_ratio,
        )
        self.db.add(wp_model)
        self.db.commit()
        self.db.refresh(wp_model)
        return self._to_domain(wp_model)

    def get_by_id(self, work_package_id: int) -> Optional[WorkPackage]:
        """
        Get work package by ID.

        Args:
            work_package_id: Work package ID

        Returns:
            Work package or None
        """
        model = self.db.query(WorkPackageModel).filter(
            WorkPackageModel.id == work_package_id
        ).first()
        return self._to_domain(model) if model else None

    def get_by_project_and_id(
        self,
        project_id: int,
        work_package_id: int
    ) -> Optional[WorkPackage]:
        """
        Get work package by project and ID.

        Args:
            project_id: Project ID
            work_package_id: Work package ID

        Returns:
            Work package or None
        """
        model = self.db.query(WorkPackageModel).filter(
            and_(
                WorkPackageModel.project_id == project_id,
                WorkPackageModel.id == work_package_id
            )
        ).first()
        return self._to_domain(model) if model else None

    def list_by_project(
        self,
        project_id: int,
        offset: int = 1,
        limit: int = 20,
        parent_id: Optional[int] = None,
    ) -> Tuple[List[WorkPackage], int]:
        """
        List work packages by project.

        Args:
            project_id: Project ID
            offset: Page number (1-indexed)
            limit: Items per page
            parent_id: Optional parent work package ID (filter subtasks)

        Returns:
            Tuple of (work packages list, total count)
        """
        query = self.db.query(WorkPackageModel).filter(
            WorkPackageModel.project_id == project_id
        )

        if parent_id is not None:
            query = query.filter(WorkPackageModel.parent_id == parent_id)

        total = query.count()

        models = query.offset((offset - 1) * limit).limit(limit).all()
        work_packages = [self._to_domain(m) for m in models]

        return work_packages, total

    def list_subtasks(
        self,
        parent_id: int,
    ) -> List[WorkPackage]:
        """
        Get all subtasks of a work package.

        Args:
            parent_id: Parent work package ID

        Returns:
            List of subtasks
        """
        models = self.db.query(WorkPackageModel).filter(
            WorkPackageModel.parent_id == parent_id
        ).all()
        return [self._to_domain(m) for m in models]

    def exists_by_id(self, work_package_id: int) -> bool:
        """
        Check if work package exists.

        Args:
            work_package_id: Work package ID

        Returns:
            True if exists
        """
        return self.db.query(
            self.db.query(WorkPackageModel).filter(
                WorkPackageModel.id == work_package_id
            ).exists()
        ).scalar()

    def exists_by_project_and_id(
        self,
        project_id: int,
        work_package_id: int
    ) -> bool:
        """
        Check if work package exists in project.

        Args:
            project_id: Project ID
            work_package_id: Work package ID

        Returns:
            True if exists
        """
        return self.db.query(
            self.db.query(WorkPackageModel).filter(
                and_(
                    WorkPackageModel.project_id == project_id,
                    WorkPackageModel.id == work_package_id
                )
            ).exists()
        ).scalar()

    def update(
        self,
        work_package_id: int,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        assignee_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        done_ratio: Optional[int] = None,
    ) -> Optional[WorkPackage]:
        """
        Update a work package.

        Args:
            work_package_id: Work package ID
            subject: New subject
            description: New description
            assignee_id: New assignee ID
            status: New status
            priority: New priority
            done_ratio: New completion percentage

        Returns:
            Updated work package or None
        """
        model = self.db.query(WorkPackageModel).filter(
            WorkPackageModel.id == work_package_id
        ).first()

        if not model:
            return None

        if subject is not None:
            model.subject = subject
        if description is not None:
            model.description = description
        if assignee_id is not None:
            model.assignee_id = assignee_id
        if status is not None:
            model.status = status
        if priority is not None:
            model.priority = priority
        if done_ratio is not None:
            model.done_ratio = done_ratio

        self.db.commit()
        self.db.refresh(model)
        return self._to_domain(model)

    def delete(self, work_package_id: int) -> bool:
        """
        Delete a work package.

        Args:
            work_package_id: Work package ID

        Returns:
            True if deleted, False if not found
        """
        model = self.db.query(WorkPackageModel).filter(
            WorkPackageModel.id == work_package_id
        ).first()

        if not model:
            return False

        self.db.delete(model)
        self.db.commit()
        return True
