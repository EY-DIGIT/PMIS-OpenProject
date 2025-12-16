"""
User controller - orchestrates requests and responses.
"""
from typing import Dict, Any
from fastapi import Request
from sqlalchemy.orm import Session
from .schemas import (
    UserCreateRequest,
    UserUpdateRequest,
    UserPasswordUpdateRequest,
    LoginRequest,
    UserListQuery
)
from .services import (
    create_user,
    get_user_by_id,
    list_users,
    update_user,
    update_password,
    delete_user,
    authenticate_user
)
from ....core.response import (
    format_user_response,
    format_collection_response,
    format_error_response,
    format_success_response
)
from ....core.dependencies import get_current_user_id
from ....core.errors import get_http_status


class UserController:
    """Controller for user operations."""

    @staticmethod
    def create(
        request: Request,
        data: UserCreateRequest,
        db: Session
    ) -> tuple[Dict[str, Any], int]:
        """
        Create a new user.

        Args:
            request: FastAPI request
            data: User creation data
            db: Database session

        Returns:
            Tuple of (response dict, status code)
        """
        result = create_user(
            db=db,
            login=data.login,
            email=data.email,
            password=data.password,
            first_name=data.firstName,
            last_name=data.lastName,
            admin=data.admin
        )

        if result.is_success():
            response = format_user_response(result.data.to_dict())
            return response, 201
        else:
            response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            status_code = 422 if result.error_type == "validation_error" else 409
            return response, status_code

    @staticmethod
    def get(
        request: Request,
        user_id: int,
        db: Session
    ) -> tuple[Dict[str, Any], int]:
        """
        Get user by ID.

        Args:
            request: FastAPI request
            user_id: User ID
            db: Database session

        Returns:
            Tuple of (response dict, status code)
        """
        requesting_user_id = get_current_user_id(request)
        is_admin = getattr(request.state, "is_admin", False)

        result = get_user_by_id(
            db=db,
            user_id=user_id,
            requesting_user_id=requesting_user_id,
            is_admin=is_admin
        )

        if result.is_success():
            response = format_user_response(result.data.to_dict())
            return response, 200
        else:
            response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            return response, 404

    @staticmethod
    def get_me(
        request: Request,
        db: Session
    ) -> tuple[Dict[str, Any], int]:
        """
        Get current user.

        Args:
            request: FastAPI request
            db: Database session

        Returns:
            Tuple of (response dict, status code)
        """
        user_id = get_current_user_id(request)

        if not user_id:
            response = format_error_response(
                error_type="authentication_error",
                message="Not authenticated"
            )
            return response, 401

        result = get_user_by_id(
            db=db,
            user_id=user_id,
            requesting_user_id=user_id,
            is_admin=True  # Users can always view themselves
        )

        if result.is_success():
            response = format_user_response(result.data.to_dict())
            return response, 200
        else:
            response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            return response, 404

    @staticmethod
    def list(
        request: Request,
        query: UserListQuery,
        db: Session
    ) -> tuple[Dict[str, Any], int]:
        """
        List users.

        Args:
            request: FastAPI request
            query: Query parameters
            db: Database session

        Returns:
            Tuple of (response dict, status code)
        """
        is_admin = getattr(request.state, "is_admin", False)

        result = list_users(
            db=db,
            page=query.offset,
            page_size=query.pageSize,
            status=query.status,
            is_admin=is_admin
        )

        if result.is_success():
            paginated = result.data
            user_dicts = [user.to_dict() for user in paginated.items]

            response = format_collection_response(
                items=user_dicts,
                total=paginated.total,
                page=paginated.page,
                page_size=paginated.page_size,
                collection_type="users"
            )
            return response, 200
        else:
            response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            status_code = 422 if result.error_type == "validation_error" else 500
            return response, status_code

    @staticmethod
    def update(
        request: Request,
        user_id: int,
        data: UserUpdateRequest,
        db: Session
    ) -> tuple[Dict[str, Any], int]:
        """
        Update user.

        Args:
            request: FastAPI request
            user_id: User ID
            data: Update data
            db: Database session

        Returns:
            Tuple of (response dict, status code)
        """
        requesting_user_id = get_current_user_id(request)
        is_admin = getattr(request.state, "is_admin", False)

        result = update_user(
            db=db,
            user_id=user_id,
            email=data.email,
            first_name=data.firstName,
            last_name=data.lastName,
            admin=data.admin,
            status=data.status,
            requesting_user_id=requesting_user_id,
            is_admin=is_admin
        )

        if result.is_success():
            response = format_user_response(result.data.to_dict())
            return response, 200
        else:
            response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )

            if result.error_type == "not_found":
                status_code = 404
            elif result.error_type == "authorization_error":
                status_code = 403
            elif result.error_type == "validation_error":
                status_code = 422
            else:
                status_code = 500

            return response, status_code

    @staticmethod
    def update_password(
        request: Request,
        user_id: int,
        data: UserPasswordUpdateRequest,
        db: Session
    ) -> tuple[Dict[str, Any], int]:
        """
        Update user password.

        Args:
            request: FastAPI request
            user_id: User ID
            data: Password update data
            db: Database session

        Returns:
            Tuple of (response dict, status code)
        """
        requesting_user_id = get_current_user_id(request)
        is_admin = getattr(request.state, "is_admin", False)

        result = update_password(
            db=db,
            user_id=user_id,
            new_password=data.password,
            requesting_user_id=requesting_user_id,
            is_admin=is_admin
        )

        if result.is_success():
            response = format_success_response("Password updated successfully")
            return response, 200
        else:
            response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )

            if result.error_type == "not_found":
                status_code = 404
            elif result.error_type == "authorization_error":
                status_code = 403
            elif result.error_type == "validation_error":
                status_code = 422
            else:
                status_code = 500

            return response, status_code

    @staticmethod
    def delete(
        request: Request,
        user_id: int,
        db: Session
    ) -> tuple[Dict[str, Any], int]:
        """
        Delete user.

        Args:
            request: FastAPI request
            user_id: User ID
            db: Database session

        Returns:
            Tuple of (response dict, status code)
        """
        result = delete_user(db=db, user_id=user_id)

        if result.is_success():
            response = format_success_response(f"User {user_id} deleted successfully")
            return response, 200
        else:
            response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            status_code = 404 if result.error_type == "not_found" else 500
            return response, status_code

    @staticmethod
    def login(
        data: LoginRequest,
        db: Session
    ) -> tuple[Dict[str, Any], int]:
        """
        Authenticate user and return token.

        Args:
            data: Login credentials
            db: Database session

        Returns:
            Tuple of (response dict, status code)
        """
        result = authenticate_user(
            db=db,
            login=data.login,
            password=data.password
        )

        if result.is_success():
            token_data = result.data
            response = {
                "_type": "Login",
                "access_token": token_data["access_token"],
                "token_type": token_data["token_type"],
                "user": format_user_response(token_data["user"].to_dict())
            }
            return response, 200
        else:
            response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            return response, 401
