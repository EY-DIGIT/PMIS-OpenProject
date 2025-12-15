"""
Projects Controller - Handles project-related requests.
"""

from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.user import User
from services.projects import ProjectService
from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse


class ProjectsController:
    """Controller for project operations"""

    @staticmethod
    def list_projects(db: Session, current_user: User, **filters) -> List:
        """List projects with filters"""
        # Implementation delegated to service
        service = ProjectService(db, current_user)
        # For now, return empty list - implement as needed
        return []

    @staticmethod
    def get_project(db: Session, project_id: int, current_user: User):
        """Get a specific project"""
        service = ProjectService(db, current_user)
        # Implementation needed
        raise HTTPException(status_code=404, detail="Project not found")

    @staticmethod
    def create_project(db: Session, project_data: ProjectCreate, current_user: User):
        """Create a new project"""
        service = ProjectService(db, current_user)
        result = service.create_project(project_data)

        if result.is_failure():
            raise HTTPException(status_code=422, detail=result.errors)

        return result.result

    @staticmethod
    def update_project(db: Session, project_id: int, project_data: ProjectUpdate, current_user: User):
        """Update a project"""
        service = ProjectService(db, current_user)
        result = service.update_project(project_id, project_data)

        if result.is_failure():
            raise HTTPException(status_code=422, detail=result.errors)

        return result.result

    @staticmethod
    def delete_project(db: Session, project_id: int, current_user: User):
        """Delete a project"""
        service = ProjectService(db, current_user)
        result = service.delete_project(project_id)

        if result.is_failure():
            raise HTTPException(status_code=422, detail=result.errors)
