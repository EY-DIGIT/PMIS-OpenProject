"""
Project Members controller - orchestrates requests and responses.
"""
from typing import List, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .schemas import (
    ProjectMemberAddRequest,
    ProjectMemberUpdateRequest,
    ProjectMembersListQuery
)
from .services import (
    add_project_member,
    list_project_members,
    update_project_member,
    delete_project_member,
)
from ....core.response import (
    format_collection_response,
)
from ....core.base_controller import BaseController
from ....infrastructure.db.repositories.user_repository import UserRepository


class ProjectMembersController:
    """Controller for project member operations."""

    @staticmethod
    def _format_membership_response(membership_data: dict, base_url: str = "/api/v3") -> dict:
        """
        Format a single membership response in HAL+JSON format.

        Args:
            membership_data: Membership data dictionary
            base_url: Base API URL

        Returns:
            HAL+JSON formatted response
        """
        membership_id = membership_data.get("id")
        project_id = membership_data.get("project_id")
        user_id = membership_data.get("user_id")

        response = {
            "_type": "Membership",
            "_links": {
                "self": {
                    "href": f"{base_url}/memberships/{membership_id}"
                },
                "project": {
                    "href": f"{base_url}/projects/{project_id}"
                },
                "user": {
                    "href": f"{base_url}/users/{user_id}"
                }
            },
            "id": membership_id,
            "projectId": project_id,
            "userId": user_id,
            "createdAt": membership_data.get("created_at"),
            "updatedAt": membership_data.get("updated_at"),
        }

        # Add embedded roles
        roles = membership_data.get("roles", [])
        if roles:
            response["_embedded"] = {
                "roles": [{"id": i, "name": role} for i, role in enumerate(roles)]
            }

        return response

    @staticmethod
    def add_member(
        request: Request,
        project_id: str,
        data: ProjectMemberAddRequest,
        db: Session
    ) -> JSONResponse:
        """
        Add a user to a project.

        Args:
            request: FastAPI request
            project_id: Project ID
            data: Member creation data
            db: Database session

        Returns:
            JSONResponse with created membership
        """
        # Extract user ID from request
        user_id = data.user.get("id")
        if not user_id:
            error_payload = {
                "_type": "Error",
                "errorIdentifier": "validation_error",
                "message": "User ID is required"
            }
            return BaseController.error(error_payload, status=422)

        # Extract roles
        roles = []
        if data.roles:
            for role_ref in data.roles:
                if isinstance(role_ref, dict) and "name" in role_ref:
                    roles.append(role_ref["name"])

        # Call service
        result = add_project_member(
            db=db,
            project_id=project_id,
            user_id=user_id,
            roles=roles,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "already_exists":
                status = 409
            elif result.error_type == "not_found":
                status = 404
            elif result.error_type == "validation_error":
                status = 422

            error_payload = {
                "_type": "Error",
                "errorIdentifier": result.error_type,
                "message": result.error
            }

            return BaseController.error(error_payload, status=status)

        # Format response
        membership_dict = result.data.to_dict()
        formatted = ProjectMembersController._format_membership_response(membership_dict, "/api/v3")

        return BaseController.created(data=formatted)

    @staticmethod
    def list_members(
        request: Request,
        project_id: str,
        query: ProjectMembersListQuery,
        db: Session
    ) -> JSONResponse:
        """
        List members of a project.

        Args:
            request: FastAPI request
            project_id: Project ID
            query: Query parameters
            db: Database session

        Returns:
            JSONResponse with paginated members
        """
        # Call service
        result = list_project_members(
            db=db,
            project_id=project_id,
            page=query.offset,
            page_size=query.pageSize,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404
            elif result.error_type == "validation_error":
                status = 422

            error_payload = {
                "_type": "Error",
                "errorIdentifier": result.error_type,
                "message": result.error
            }

            return BaseController.error(error_payload, status=status)

        # Extract memberships and total
        memberships, total = result.data

        # Format memberships
        formatted_memberships = [
            ProjectMembersController._format_membership_response(m.to_dict(), "/api/v3")
            for m in memberships
        ]

        # Build pagination links
        total_pages = (total + query.pageSize - 1) // query.pageSize
        links = {
            "self": {"href": f"/api/v3/projects/{project_id}/memberships?offset={query.offset}&pageSize={query.pageSize}"}
        }

        if query.offset > 1:
            links["first"] = {"href": f"/api/v3/projects/{project_id}/memberships?offset=1&pageSize={query.pageSize}"}
            links["prev"] = {"href": f"/api/v3/projects/{project_id}/memberships?offset={query.offset - 1}&pageSize={query.pageSize}"}

        if query.offset < total_pages:
            links["next"] = {"href": f"/api/v3/projects/{project_id}/memberships?offset={query.offset + 1}&pageSize={query.pageSize}"}
            links["last"] = {"href": f"/api/v3/projects/{project_id}/memberships?offset={total_pages}&pageSize={query.pageSize}"}

        response = {
            "_type": "Collection",
            "_links": links,
            "total": total,
            "count": len(formatted_memberships),
            "pageSize": query.pageSize,
            "offset": query.offset,
            "_embedded": {
                "elements": formatted_memberships
            }
        }

        return BaseController.ok(data=response)

    @staticmethod
    def update_member(
        request: Request,
        membership_id: int,
        data: ProjectMemberUpdateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Update a membership's roles.

        Args:
            request: FastAPI request
            membership_id: Membership ID
            data: Update data
            db: Database session

        Returns:
            JSONResponse with updated membership
        """
        # Extract roles
        roles = []
        if data.roles:
            for role_ref in data.roles:
                if isinstance(role_ref, dict) and "name" in role_ref:
                    roles.append(role_ref["name"])

        # Call service
        result = update_project_member(
            db=db,
            membership_id=membership_id,
            roles=roles,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404
            elif result.error_type == "validation_error":
                status = 422

            error_payload = {
                "_type": "Error",
                "errorIdentifier": result.error_type,
                "message": result.error
            }

            return BaseController.error(error_payload, status=status)

        # Format response
        membership_dict = result.data.to_dict()
        formatted = ProjectMembersController._format_membership_response(membership_dict, "/api/v3")

        return BaseController.ok(data=formatted)

    @staticmethod
    def remove_member(
        request: Request,
        membership_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Remove a member from a project.

        Doc 44 round 7: a project_admin cannot unassign themselves
        from a project they admin. Self-removal via this endpoint is
        refused for project_admin callers acting on their own row.
        super_admin / admin / org_admin can still remove anyone
        (including a project_admin who's themselves).
        """
        # Doc 44 round 7 self-unassign guard. The legacy
        # ``project_members`` table was retired in favour of URA;
        # the membership row referenced by ``membership_id`` is now
        # a URA row (the repository surfaces its primary key as the
        # legacy ``id`` to keep the URL surface unchanged).
        from ....infrastructure.db.models.role import RoleModel
        from ....infrastructure.db.models.user_role_assignment import (
            UserRoleAssignmentModel,
        )
        from ....core.dependencies import get_current_user_id
        caller_id = get_current_user_id(request)
        membership = (
            db.query(UserRoleAssignmentModel)
            .filter(UserRoleAssignmentModel.id == membership_id)
            .filter(UserRoleAssignmentModel.project_id.isnot(None))
            .first()
        )
        if membership is not None and caller_id == membership.user_id:
            # Caller is removing their own membership — refuse if they
            # hold project_admin on this project (they can't unassign
            # themselves from a project they admin per spec).
            holds_pa = (
                db.query(UserRoleAssignmentModel)
                .join(RoleModel, RoleModel.id == UserRoleAssignmentModel.role_id)
                .filter(
                    UserRoleAssignmentModel.user_id == caller_id,
                    UserRoleAssignmentModel.project_id == membership.project_id,
                    RoleModel.name == "project_admin",
                )
                .first()
            )
            # Higher tiers (admin / super_admin globally) bypass this
            # guard — they're not "self-unassigning AS project_admin"
            # in the spec's sense.
            from ....infrastructure.db.repositories.rbac_repository import (
                RbacRepository,
            )
            is_admin_global = RbacRepository(db).user_has_admin_role(caller_id)
            if holds_pa and not is_admin_global:
                return BaseController.error(
                    {
                        "_type": "Error",
                        "errorIdentifier": "forbidden",
                        "message": (
                            "Project admin cannot unassign themselves "
                            "from a project they administer."
                        ),
                    },
                    status=403,
                )

        # Call service
        result = delete_project_member(
            db=db,
            membership_id=membership_id,
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

        return BaseController.no_content()
