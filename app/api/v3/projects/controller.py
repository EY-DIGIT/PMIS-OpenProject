"""
Project controller - orchestrates requests and responses.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .schemas import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectListQuery
)
from .services import (
    create_project,
    get_project_by_id,
    list_projects,
    update_project,
    delete_project
)
from ....core.response import (
    format_project_response,
    format_collection_response,
)
from ....core.base_controller import BaseController
from ....core.dependencies import get_current_user_id


class ProjectController:
    """Controller for project operations."""

    @staticmethod
    def create(
        request: Request,
        data: ProjectCreateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Create a new project.

        Args:
            request: FastAPI request
            data: Project creation data
            db: Database session

        Returns:
            JSONResponse with created project
        """
        # Call service
        result = create_project(
            db=db,
            identifier=data.identifier,
            name=data.name,
            description=data.description,
            active=data.active,
            public=data.public,
            status_explanation=data.statusExplanation,
            parent_id=data.parentId,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "already_exists":
                status = 409
            elif result.error_type == "not_found":
                status = 404

            error_payload = {
                "_type": "Error",
                "errorIdentifier": result.error_type,
                "message": result.error
            }

            return BaseController.error(error_payload, status=status)

        # Format response
        project_dict = result.data.to_dict()
        formatted = format_project_response(project_dict, "/api/v3")

        return BaseController.created(data=formatted)

    @staticmethod
    def list(
        request: Request,
        query: ProjectListQuery,
        db: Session
    ) -> JSONResponse:
        """
        List projects with pagination.

        Args:
            request: FastAPI request
            query: Query parameters
            db: Database session

        Returns:
            JSONResponse with paginated projects
        """
        # Call service
        result = list_projects(
            db=db,
            page=query.offset,
            page_size=query.pageSize,
            active=query.active,
            public=query.public,
        )

        if not result.is_success():
            error_payload = {
                "_type": "Error",
                "errorIdentifier": result.error_type,
                "message": result.error
            }

            return BaseController.error(error_payload, status=500)

        # Format response
        paginated = result.data
        project_dicts = [p.to_dict() for p in paginated.items]
        formatted = format_collection_response(
            items=project_dicts,
            total=paginated.total,
            page=paginated.page,
            page_size=paginated.page_size,
            base_url="/api/v3",
            collection_type="projects"
        )

        return BaseController.ok(data=formatted)

    @staticmethod
    def get(
        request: Request,
        project_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Get project by ID.

        Args:
            request: FastAPI request
            project_id: Project ID
            db: Database session

        Returns:
            JSONResponse with project
        """
        # Call service
        result = get_project_by_id(db, project_id)

        if not result.is_success():
            error_payload = {
                "_type": "Error",
                "errorIdentifier": result.error_type,
                "message": result.error
            }

            return BaseController.error(error_payload, status=404)

        # Format response
        project_dict = result.data.to_dict()
        formatted = format_project_response(project_dict, "/api/v3")

        return BaseController.ok(data=formatted)

    @staticmethod
    def update(
        request: Request,
        project_id: int,
        data: ProjectUpdateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Update project details.

        Args:
            request: FastAPI request
            project_id: Project ID
            data: Project update data
            db: Database session

        Returns:
            JSONResponse with updated project
        """
        # Call service
        result = update_project(
            db=db,
            project_id=project_id,
            name=data.name,
            description=data.description,
            active=data.active,
            public=data.public,
            status_explanation=data.statusExplanation,
            parent_id=data.parentId,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404

            error_payload = {
                "_type": "Error",
                "errorIdentifier": result.error_type,
                "message": result.error
            }

            return BaseController.error(error_payload, status=status)

        # Format response
        project_dict = result.data.to_dict()
        formatted = format_project_response(project_dict, "/api/v3")

        return BaseController.ok(data=formatted)

    @staticmethod
    def delete(
        request: Request,
        project_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Delete project by ID.

        Args:
            request: FastAPI request
            project_id: Project ID
            db: Database session

        Returns:
            JSONResponse with success
        """
        # Call service
        result = delete_project(db, project_id)

        if not result.is_success():
            error_payload = {
                "_type": "Error",
                "errorIdentifier": result.error_type,
                "message": result.error
            }

            return BaseController.error(error_payload, status=404)

        return BaseController.no_content()
