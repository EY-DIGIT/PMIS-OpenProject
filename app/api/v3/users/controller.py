"""
User controller - orchestrates requests and responses.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
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
from ....core.base_controller import BaseController
from ....core.dependencies import get_current_user_id


class UserController:
    """Controller for user operations."""

    @staticmethod
    def create(
        request: Request,
        data: UserCreateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Create a new user.

        Args:
            request: FastAPI request
            data: User creation data
            db: Database session

        Returns:
            JSONResponse
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
            payload = format_user_response(result.data.to_dict())
            resp = BaseController.created(payload)
            return resp
        else:
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            status_code = 422 if result.error_type == "validation_error" else 409
            resp = BaseController.error(error_payload, status=status_code)
            return resp

    @staticmethod
    def get(
        request: Request,
        user_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Get user by ID.

        Args:
            request: FastAPI request
            user_id: User ID
            db: Database session

        Returns:
            JSONResponse
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
            payload = format_user_response(result.data.to_dict())
            return BaseController.ok(payload)
        else:
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            resp = BaseController.error(error_payload, status=404)
            return resp

    @staticmethod
    def get_me(
        request: Request,
        db: Session
    ) -> JSONResponse:
        """
        Get current user.

        Args:
            request: FastAPI request
            db: Database session

        Returns:
            JSONResponse
        """
        user_id = get_current_user_id(request)

        if not user_id:
            error_payload = format_error_response(
                error_type="authentication_error",
                message="Not authenticated"
            )
            resp = BaseController.error(error_payload, status=401)
            return resp

        result = get_user_by_id(
            db=db,
            user_id=user_id,
            requesting_user_id=user_id,
            is_admin=True  # Users can always view themselves
        )

        if result.is_success():
            payload = format_user_response(result.data.to_dict())
            resp = BaseController.ok(payload)
            return resp
        else:
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            resp = BaseController.error(error_payload, status=404)
            return resp

    @staticmethod
    def list(
        request: Request,
        query: UserListQuery,
        db: Session
    ) -> JSONResponse:
        """
        List users.

        Args:
            request: FastAPI request
            query: Query parameters
            db: Database session

        Returns:
            JSONResponse
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

            payload = format_collection_response(
                items=user_dicts,
                total=paginated.total,
                page=paginated.page,
                page_size=paginated.page_size,
                collection_type="users"
            )
            resp = BaseController.ok(payload)
            return resp
        else:
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            status_code = 422 if result.error_type == "validation_error" else 500
            resp = BaseController.error(error_payload, status=status_code)
            return resp

    @staticmethod
    def update(
        request: Request,
        user_id: int,
        data: UserUpdateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Update user.

        Args:
            request: FastAPI request
            user_id: User ID
            data: Update data
            db: Database session

        Returns:
            JSONResponse
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
            payload = format_user_response(result.data.to_dict())
            resp = BaseController.ok(payload)
            return resp
        else:
            error_payload = format_error_response(
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

            resp = BaseController.error(error_payload, status=status_code)
            return resp

    @staticmethod
    def update_password(
        request: Request,
        user_id: int,
        data: UserPasswordUpdateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Update user password.

        Args:
            request: FastAPI request
            user_id: User ID
            data: Password update data
            db: Database session

        Returns:
            JSONResponse
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
            payload = format_success_response("Password updated successfully")
            resp = BaseController.ok(payload)
            return resp
        else:
            error_payload = format_error_response(
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

            resp = BaseController.error(error_payload, status=status_code)
            return resp

    @staticmethod
    def delete(
        request: Request,
        user_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Delete user.

        Args:
            request: FastAPI request
            user_id: User ID
            db: Database session

        Returns:
            JSONResponse
        """
        result = delete_user(db=db, user_id=user_id)

        if result.is_success():
            payload = format_success_response(f"User {user_id} deleted successfully")
            resp = BaseController.ok(payload)
            return resp
        else:
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            status_code = 404 if result.error_type == "not_found" else 500
            resp = BaseController.error(error_payload, status=status_code)
            return resp

    @staticmethod
    def login(
        data: LoginRequest,
        db: Session
    ) -> JSONResponse:
        """
        Authenticate user and return token.

        Args:
            data: Login credentials
            db: Database session

        Returns:
            JSONResponse
        """
        result = authenticate_user(
            db=db,
            login=data.login,
            password=data.password
        )

        if result.is_success():
            token_data = result.data
            # Keep HAL+JSON for the user inside the `data` payload.
            response_payload = {
                "_type": "Login",
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "token_type": token_data["token_type"],
                "user": format_user_response(token_data["user"].to_dict())
            }
            # Opt-in envelope using BaseController helper which calls `api_response()` internally.
            resp = BaseController.ok(response_payload)
            return resp
        else:
            error_response = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details
            )
            resp = BaseController.error(error_response, status=401)
            return resp

    @staticmethod
    def introspect(
        data,
        db: Session
    ) -> JSONResponse:
        """
        Public introspection endpoint. No auth middleware.
        """
        from .services.introspect import introspect_tokens

        result = introspect_tokens(db=db, access_token=data.access_token, refresh_token=data.refresh_token)

        if result.is_success():
            payload = result.data
            # When active-only response
            if payload.get("active"):
                resp_payload = {"_type": "Introspect", "active": True, "user": format_user_response(payload["user"].to_dict())}
                return BaseController.ok(resp_payload)

            # When rotation issued new tokens
            resp_payload = {
                "_type": "Introspect",
                "access_token": payload.get("access_token"),
                "refresh_token": payload.get("refresh_token"),
                "token_type": payload.get("token_type"),
                "user": format_user_response(payload["user"].to_dict())
            }
            return BaseController.ok(resp_payload)
        else:
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error
            )
            return BaseController.error(error_payload, status=401)
