"""
Work Package controller - orchestrates requests and responses.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .schemas import (
    WorkPackageCreateRequest,
    WorkPackageUpdateRequest,
    WorkPackageListQuery
)
from .services import (
    create_work_package,
    get_work_package_by_id,
    get_work_package_by_project_and_id,
    list_work_packages_by_project,
    update_work_package,
    delete_work_package,
)
from ....core.base_controller import BaseController
from ....infrastructure.db.repositories.work_package_repository import WorkPackageRepository


class WorkPackageController:
    """Controller for work package operations."""

    @staticmethod
    def _format_work_package(wp: dict, base_url: str = "/api/v3") -> dict:
        """Build HAL+JSON for a single work package (controller-level)."""
        wp_id = wp.get("id")
        project_id = wp.get("project_id")

        response = {
            "_type": "WorkPackage",
            "_links": {
                "self": {
                    "href": f"{base_url}/work_packages/{wp_id}",
                    "title": wp.get("subject")
                },
                "project": {"href": f"{base_url}/projects/{project_id}"}
            },
            "id": wp_id,
            "subject": wp.get("subject"),
            "description": wp.get("description"),
            "projectId": project_id,
            "parentId": wp.get("parent_id"),
            "assigneeId": wp.get("assignee_id"),
            "typeId": wp.get("type_id"),
            "status": wp.get("status"),
            "priority": wp.get("priority"),
            "doneRatio": wp.get("done_ratio"),
            "startDate": wp.get("start_date"),
            "endDate": wp.get("end_date"),
            "createdAt": wp.get("created_at"),
            "updatedAt": wp.get("updated_at"),
        }

        if wp.get("parent_id"):
            response["_links"]["parent"] = {"href": f"{base_url}/work_packages/{wp.get('parent_id')}"}

        if wp.get("assignee_id"):
            response["_links"]["assignee"] = {"href": f"{base_url}/users/{wp.get('assignee_id')}"}

        if wp.get("type_id"):
            response["_links"]["type"] = {"href": f"{base_url}/work_package_types/{wp.get('type_id')}"}

        return response

    @staticmethod
    def create_in_project(
        request: Request,
        project_id: int,
        data: WorkPackageCreateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Create a new work package in a project.

        Args:
            request: FastAPI request
            project_id: Project ID
            data: Work package creation data
            db: Database session

        Returns:
            JSONResponse with created work package
        """
        result = create_work_package(
            db=db,
            project_id=project_id,
            subject=data.subject,
            description=data.description,
            parent_id=data.parentId,
            assignee_id=data.assigneeId,
            type_id=data.typeId,
            status=data.status,
            priority=data.priority,
            done_ratio=data.doneRatio,
            start_date=data.startDate,
            end_date=data.endDate,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404
            return BaseController.error(
                error_payload={"message": result.error, "type": result.error_type},
                status=status
            )

        wp_dict = result.data.to_dict()
        response_data = WorkPackageController._format_work_package(wp_dict, base_url="/api/v3")
        return BaseController.created(response_data)

    @staticmethod
    def get(
        request: Request,
        work_package_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Get a work package by ID.

        Args:
            request: FastAPI request
            work_package_id: Work package ID
            db: Database session

        Returns:
            JSONResponse with work package
        """
        result = get_work_package_by_id(db, work_package_id)

        if not result.is_success():
            return BaseController.error(
                error_payload={"message": result.error, "type": result.error_type},
                status=404
            )

        wp_dict = result.data.to_dict()
        response_data = WorkPackageController._format_work_package(wp_dict, base_url="/api/v3")
        return BaseController.ok(response_data)

    @staticmethod
    def get_in_project(
        request: Request,
        project_id: int,
        work_package_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Get a work package by project and ID.

        Args:
            request: FastAPI request
            project_id: Project ID
            work_package_id: Work package ID
            db: Database session

        Returns:
            JSONResponse with work package
        """
        result = get_work_package_by_project_and_id(db, project_id, work_package_id)

        if not result.is_success():
            status = 404
            return BaseController.error(
                error_payload={"message": result.error, "type": result.error_type},
                status=status
            )

        wp_dict = result.data.to_dict()
        response_data = WorkPackageController._format_work_package(wp_dict, base_url="/api/v3")
        return BaseController.ok(response_data)

    @staticmethod
    def list(
        request: Request,
        project_id: int,
        query: WorkPackageListQuery,
        db: Session
    ) -> JSONResponse:
        """
        List work packages in a project.

        Args:
            request: FastAPI request
            project_id: Project ID
            query: Query parameters
            db: Database session

        Returns:
            JSONResponse with work packages collection
        """
        result = list_work_packages_by_project(
            db=db,
            project_id=project_id,
            offset=query.offset,
            limit=query.pageSize,
            parent_id=query.parentId,
            type_name=query.type,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404
            return BaseController.error(
                error_payload={"message": result.error, "type": result.error_type},
                status=status
            )

        work_packages, total = result.data
        items = [wp.to_dict() for wp in work_packages]

        # Build collection HAL for project-scoped work packages
        page = query.offset
        page_size = query.pageSize
        total_pages = (total + page_size - 1) // page_size if page_size else 1
        base_collection = f"/api/v3/projects/{project_id}/work_packages"

        links = {"self": {"href": f"{base_collection}?offset={page}&pageSize={page_size}"}}
        if page > 1:
            links["first"] = {"href": f"{base_collection}?offset=1&pageSize={page_size}"}
            links["prev"] = {"href": f"{base_collection}?offset={page - 1}&pageSize={page_size}"}
        if page < total_pages:
            links["next"] = {"href": f"{base_collection}?offset={page + 1}&pageSize={page_size}"}
            links["last"] = {"href": f"{base_collection}?offset={total_pages}&pageSize={page_size}"}

        embedded = [WorkPackageController._format_work_package(i, base_url="/api/v3") for i in items]

        collection_payload = {
            "_type": "Collection",
            "_links": links,
            "total": total,
            "count": len(items),
            "pageSize": page_size,
            "offset": page,
            "_embedded": {"elements": embedded}
        }

        return BaseController.ok(collection_payload)

    @staticmethod
    def update(
        request: Request,
        work_package_id: int,
        data: WorkPackageUpdateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Update a work package.

        Args:
            request: FastAPI request
            work_package_id: Work package ID
            data: Work package update data
            db: Database session

        Returns:
            JSONResponse with updated work package
        """
        # Build kwargs — only pass dates if explicitly provided in request
        update_kwargs = dict(
            db=db,
            work_package_id=work_package_id,
            subject=data.subject,
            description=data.description,
            assignee_id=data.assigneeId,
            type_id=data.typeId,
            status=data.status,
            priority=data.priority,
            done_ratio=data.doneRatio,
        )
        if data.startDate is not None:
            update_kwargs["start_date"] = data.startDate
        if data.endDate is not None:
            update_kwargs["end_date"] = data.endDate
        result = update_work_package(**update_kwargs)

        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404
            return BaseController.error(
                error_payload={"message": result.error, "type": result.error_type},
                status=status
            )

        wp_dict = result.data.to_dict()
        response_data = WorkPackageController._format_work_package(wp_dict, base_url="/api/v3")
        return BaseController.ok(response_data)

    @staticmethod
    def delete(
        request: Request,
        work_package_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Delete a work package.

        Args:
            request: FastAPI request
            work_package_id: Work package ID
            db: Database session

        Returns:
            JSONResponse with success status
        """
        result = delete_work_package(db, work_package_id)

        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404
            return BaseController.error(
                error_payload={"message": result.error, "type": result.error_type},
                status=status
            )

        return BaseController.no_content()

    # ----- tree / children -----

    @staticmethod
    def _build_tree(flat_list, root_id, formatter):
        """Assemble a flat list of work-package dicts into a nested tree."""
        by_parent = {}
        for wp in flat_list:
            pid = wp.parent_id
            by_parent.setdefault(pid, []).append(wp)

        def _recurse(parent_id):
            children = by_parent.get(parent_id, [])
            result = []
            for child in children:
                node = formatter(child.to_dict())
                node["_embedded"] = {"children": _recurse(child.id)}
                result.append(node)
            return result

        return _recurse(root_id)

    @staticmethod
    def get_children(
        request: Request,
        work_package_id: int,
        db: Session
    ) -> JSONResponse:
        """Return the full nested subtree under a work package."""
        repository = WorkPackageRepository(db)

        root = repository.get_by_id(work_package_id)
        if not root:
            return BaseController.error(
                error_payload={"message": f"Work package {work_package_id} not found", "type": "not_found"},
                status=404
            )

        descendants = repository.get_children_recursive(work_package_id)
        root_formatted = WorkPackageController._format_work_package(root.to_dict())
        root_formatted["_embedded"] = {
            "children": WorkPackageController._build_tree(
                descendants, work_package_id, WorkPackageController._format_work_package
            )
        }

        return BaseController.ok(root_formatted)
