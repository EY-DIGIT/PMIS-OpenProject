"""
User routes - URL definitions with permission bindings.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from .controller import UserController
from .schemas import (
    UserCreateRequest,
    UserUpdateRequest,
    UserPasswordUpdateRequest,
    LoginRequest,
    UserListQuery
)
from .permissions import (
    USERS_CREATE,
    USERS_READ,
    USERS_READ_ALL,
    USERS_UPDATE,
    USERS_DELETE_ALL
)
from ....core.middleware.rbac import require_permission, require_authenticated
from ....infrastructure.db.session import get_db

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/login",
    summary="Authenticate user",
    description="Authenticate user and receive JWT token"
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Authenticate user and return access token.

    No authentication required for this endpoint.
    """
    response, status_code = UserController.login(data, db)
    return response


@router.get(
    "/me",
    dependencies=[require_authenticated()],
    summary="Get current user",
    description="Get currently authenticated user"
)
def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current authenticated user.

    Requires: Authentication
    """
    response, status_code = UserController.get_me(request, db)
    return response


@router.post(
    "",
    dependencies=[require_permission(USERS_CREATE)],
    summary="Create user",
    description="Create a new user",
    status_code=201
)
def create_user(
    request: Request,
    data: UserCreateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new user.

    Requires: USERS_CREATE permission (admin only)
    """
    response, status_code = UserController.create(request, data, db)
    return response


@router.get(
    "",
    dependencies=[require_permission(USERS_READ_ALL)],
    summary="List users",
    description="List all users with pagination"
)
def list_users(
    request: Request,
    offset: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List users with pagination.

    Requires: USERS_READ_ALL permission (admin only)
    """
    query = UserListQuery(offset=offset, pageSize=pageSize, status=status)
    response, status_code = UserController.list(request, query, db)
    return response


@router.get(
    "/{user_id}",
    dependencies=[require_permission(USERS_READ)],
    summary="Get user",
    description="Get user by ID"
)
def get_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get user by ID.

    Requires: USERS_READ permission
    - Members can view themselves and active users
    - Admins can view all users
    """
    response, status_code = UserController.get(request, user_id, db)
    return response


@router.patch(
    "/{user_id}",
    dependencies=[require_permission(USERS_UPDATE)],
    summary="Update user",
    description="Update user details"
)
def update_user(
    request: Request,
    user_id: int,
    data: UserUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update user details.

    Requires: USERS_UPDATE permission
    - Members can update themselves (excluding admin flag and status)
    - Admins can update all users
    """
    response, status_code = UserController.update(request, user_id, data, db)
    return response


@router.patch(
    "/{user_id}/password",
    dependencies=[require_permission(USERS_UPDATE)],
    summary="Update user password",
    description="Update user password"
)
def update_user_password(
    request: Request,
    user_id: int,
    data: UserPasswordUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update user password.

    Requires: USERS_UPDATE permission
    - Members can update their own password
    - Admins can update any user's password
    """
    response, status_code = UserController.update_password(request, user_id, data, db)
    return response


@router.delete(
    "/{user_id}",
    dependencies=[require_permission(USERS_DELETE_ALL)],
    summary="Delete user",
    description="Delete user by ID"
)
def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete user by ID.

    Requires: USERS_DELETE_ALL permission (admin only)
    """
    response, status_code = UserController.delete(request, user_id, db)
    return response
