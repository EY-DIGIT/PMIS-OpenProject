"""
Project repository for database operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from ...db.models.project import ProjectModel
from ....domain.projects.project import Project


class ProjectRepository:
    """Repository for Project database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def _to_domain(self, model: ProjectModel) -> Project:
        """
        Convert database model to domain model.

        Args:
            model: Database model

        Returns:
            Domain model
        """
        return Project(
            id=model.id,
            identifier=model.identifier,
            name=model.name,
            description=model.description,
            active=model.active,
            public=model.public,
            status_explanation=model.status_explanation,
            created_at=model.created_at,
            updated_at=model.updated_at,
            parent_id=model.parent_id,
            status=model.status,
            owner=model.owner,
            category=model.category,
            start_date=model.start_date,
            end_date=model.end_date,
        )

    def create(
        self,
        identifier: str,
        name: str,
        description: Optional[str] = None,
        active: bool = True,
        public: bool = False,
        status_explanation: Optional[str] = None,
        parent_id: Optional[int] = None,
        status: str = "new",
        owner: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[object] = None,
        end_date: Optional[object] = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            identifier: Project identifier (unique)
            name: Project name
            description: Project description
            active: Whether project is active
            public: Whether project is public
            status_explanation: Project status explanation
            parent_id: Parent project ID
            status: Project status (see PROJECT_STATUS_CHOICES in schemas.py)
            owner: Project owner username
            category: Project category (see PROJECT_CATEGORY_CHOICES in schemas.py)
            start_date: Project start date
            end_date: Project end date

        Returns:
            Created project domain model
        """
        project_model = ProjectModel(
            identifier=identifier,
            name=name,
            description=description,
            active=active,
            public=public,
            status_explanation=status_explanation,
            parent_id=parent_id,
            status=status,
            owner=owner,
            category=category,
            start_date=start_date,
            end_date=end_date,
        )

        self.db.add(project_model)
        self.db.commit()
        self.db.refresh(project_model)

        return self._to_domain(project_model)

    def get_by_id(self, project_id: int) -> Optional[Project]:
        """
        Get project by ID.

        Args:
            project_id: Project ID

        Returns:
            Project if found, None otherwise
        """
        model = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        return self._to_domain(model) if model else None

    def get_by_identifier(self, identifier: str) -> Optional[Project]:
        """
        Get project by identifier.

        Args:
            identifier: Project identifier

        Returns:
            Project if found, None otherwise
        """
        model = self.db.query(ProjectModel).filter(ProjectModel.identifier == identifier).first()
        return self._to_domain(model) if model else None

    def list_all(self, offset: int = 0, limit: int = 20) -> Tuple[List[Project], int]:
        """
        List all projects with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of projects, total count)
        """
        total = self.db.query(func.count(ProjectModel.id)).scalar()
        models = self.db.query(ProjectModel).offset(offset).limit(limit).all()
        projects = [self._to_domain(m) for m in models]
        return projects, total

    def list_active(self, offset: int = 0, limit: int = 20) -> Tuple[List[Project], int]:
        """
        List active projects with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of active projects, total count)
        """
        total = self.db.query(func.count(ProjectModel.id)).filter(ProjectModel.active == True).scalar()
        models = self.db.query(ProjectModel).filter(ProjectModel.active == True).offset(offset).limit(limit).all()
        projects = [self._to_domain(m) for m in models]
        return projects, total

    def list_public(self, offset: int = 0, limit: int = 20) -> Tuple[List[Project], int]:
        """
        List public projects with pagination.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of public projects, total count)
        """
        total = self.db.query(func.count(ProjectModel.id)).filter(ProjectModel.public == True).scalar()
        models = self.db.query(ProjectModel).filter(ProjectModel.public == True).offset(offset).limit(limit).all()
        projects = [self._to_domain(m) for m in models]
        return projects, total

    def exists_by_identifier(self, identifier: str) -> bool:
        """
        Check if project with identifier exists.

        Args:
            identifier: Project identifier

        Returns:
            True if exists, False otherwise
        """
        return self.db.query(ProjectModel).filter(ProjectModel.identifier == identifier).first() is not None

    def exists_by_id(self, project_id: int) -> bool:
        """
        Check if project with ID exists.

        Args:
            project_id: Project ID

        Returns:
            True if exists, False otherwise
        """
        return self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first() is not None

    def update(
        self,
        project_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        active: Optional[bool] = None,
        public: Optional[bool] = None,
        status_explanation: Optional[str] = None,
        parent_id: Optional[int] = None,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[object] = None,
        end_date: Optional[object] = None,
    ) -> Optional[Project]:
        """
        Update a project.

        Args:
            project_id: Project ID
            name: New name
            description: New description
            active: New active status
            public: New public status
            status_explanation: New status explanation
            parent_id: New parent project ID
            status: New status
            owner: New owner username
            category: New category
            start_date: New start date
            end_date: New end date

        Returns:
            Updated project if found, None otherwise
        """
        model = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not model:
            return None

        if name is not None:
            model.name = name
        if description is not None:
            model.description = description
        if active is not None:
            model.active = active
        if public is not None:
            model.public = public
        if status_explanation is not None:
            model.status_explanation = status_explanation
        if parent_id is not None:
            model.parent_id = parent_id
        if status is not None:
            model.status = status
        if owner is not None:
            model.owner = owner
        if category is not None:
            model.category = category
        if start_date is not None:
            model.start_date = start_date
        if end_date is not None:
            model.end_date = end_date

        self.db.commit()
        self.db.refresh(model)

        return self._to_domain(model)

    def delete(self, project_id: int) -> bool:
        """
        Delete a project.

        Args:
            project_id: Project ID

        Returns:
            True if deleted, False if not found
        """
        model = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not model:
            return False

        self.db.delete(model)
        self.db.commit()

        return True
