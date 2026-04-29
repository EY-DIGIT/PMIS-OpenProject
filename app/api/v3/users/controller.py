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
    restore_user,
    authenticate_user,
    logout_user,
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
            admin=data.admin,
            vendor_id=data.vendorId,
            division=data.division,
            division_other=data.divisionOther,
            project_ids=data.projectIds,
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
    def logout(
        request: Request,
        db: Session
    ) -> JSONResponse:
        """
        Hard logout: revoke the access token (jti blacklist) AND clear the
        refresh-token jti on the user row. Idempotent.
        """
        user_id = get_current_user_id(request)
        if not user_id:
            error_payload = format_error_response(
                error_type="authentication_error",
                message="Not authenticated",
            )
            return BaseController.error(error_payload, status=401)

        result = logout_user(
            db=db,
            user_id=user_id,
            token_jti=getattr(request.state, "token_jti", None),
            token_exp=getattr(request.state, "token_exp", None),
        )
        if result.is_success():
            return BaseController.ok(
                format_success_response(result.data["message"])
            )
        error_payload = format_error_response(
            error_type=result.error_type,
            message=result.error,
        )
        return BaseController.error(error_payload, status=500)

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
            is_admin=is_admin,
            include_deleted=getattr(query, "includeDeleted", False),
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
            vendor_id=data.vendorId,
            division=data.division,
            division_other=data.divisionOther,
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
        actor_id = get_current_user_id(request)
        result = delete_user(db=db, user_id=user_id, actor_id=actor_id)

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
    def restore(
        request: Request,
        user_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Restore a soft-deleted user.

        Mirrors POST /vendors/{id}/restore. Idempotent on already-active
        users (returns 200 with the current snapshot).

        Requires: USERS_DELETE_ALL permission (admin only)
        """
        requesting_user_id = get_current_user_id(request)
        is_admin = getattr(request.state, "is_admin", False)

        result = restore_user(
            db=db,
            user_id=user_id,
            requesting_user_id=requesting_user_id,
            is_admin=is_admin,
        )

        if result.is_success():
            payload = format_user_response(result.data.to_dict())
            return BaseController.ok(payload)
        else:
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error,
                details=result.details,
            )
            if result.error_type == "not_found":
                status_code = 404
            elif result.error_type == "authorization_error":
                status_code = 403
            else:
                status_code = 500
            return BaseController.error(error_payload, status=status_code)

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
            # Decode the freshly-minted tokens to surface their expiry /
            # issued-at timestamps to the FE. Lets the client schedule a
            # preemptive refresh without having to decode the JWT itself.
            from .services.refresh import _exp_metadata
            access_meta = _exp_metadata(token_data["access_token"])
            refresh_meta = (
                _exp_metadata(token_data["refresh_token"])
                if token_data.get("refresh_token") else {}
            )
            # Keep HAL+JSON for the user inside the `data` payload.
            response_payload = {
                "_type": "Login",
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "token_type": token_data["token_type"],
                "accessTokenExpiresAt": access_meta.get("expiresAt"),
                "accessTokenIssuedAt": access_meta.get("issuedAt"),
                "refreshTokenExpiresAt": refresh_meta.get("expiresAt"),
                "refreshTokenIssuedAt": refresh_meta.get("issuedAt"),
                "expiresInSeconds": (
                    int(access_meta["exp"] - access_meta["iat"])
                    if access_meta.get("exp") and access_meta.get("iat") else None
                ),
                "user": format_user_response(token_data["user"].to_dict()),
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
        Public introspection endpoint. No auth middleware. RFC 7662-style
        read-only: returns token metadata without ever rotating. Use
        POST /users/refresh to rotate.
        """
        from .services.introspect import introspect_tokens

        result = introspect_tokens(
            db=db,
            access_token=data.access_token,
            refresh_token=data.refresh_token,
        )

        if not result.is_success():
            # Only happens for "no token provided" — a 422 from the schema
            # would be cleaner but the body is well-formed JSON, so the
            # service-layer 400 is appropriate.
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error,
            )
            status = 422 if result.error_type == "validation_error" else 401
            return BaseController.error(error_payload, status=status)

        payload = result.data
        payload["_type"] = "Introspect"
        return BaseController.ok(payload)

    @staticmethod
    def refresh(
        data,
        db: Session,
    ) -> JSONResponse:
        """Public refresh endpoint. Validates a refresh token and returns
        a freshly-rotated access + refresh pair plus expiry metadata.
        """
        from .services.refresh import refresh_tokens

        result = refresh_tokens(db=db, refresh_token=data.refresh_token)

        if not result.is_success():
            error_payload = format_error_response(
                error_type=result.error_type,
                message=result.error,
            )
            status = 422 if result.error_type == "validation_error" else 401
            return BaseController.error(error_payload, status=status)

        payload = result.data
        return BaseController.ok({
            "_type": "Refresh",
            "access_token": payload["access_token"],
            "refresh_token": payload["refresh_token"],
            "token_type": payload["token_type"],
            "accessTokenExpiresAt": payload.get("accessTokenExpiresAt"),
            "accessTokenIssuedAt": payload.get("accessTokenIssuedAt"),
            "refreshTokenExpiresAt": payload.get("refreshTokenExpiresAt"),
            "refreshTokenIssuedAt": payload.get("refreshTokenIssuedAt"),
            "expiresInSeconds": payload.get("expiresInSeconds"),
            "user": format_user_response(payload["user"].to_dict()),
        })
