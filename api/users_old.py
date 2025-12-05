"""
User API endpoints matching OpenProject API v3.

Implements the following endpoints:
- GET /api/v3/users - List users
- POST /api/v3/users - Create user
- GET /api/v3/users/{id} - View user
- PATCH /api/v3/users/{id} - Update user
- DELETE /api/v3/users/{id} - Delete user
- POST /api/v3/users/{id}/lock - Lock user
- POST /api/v3/users/{id}/unlock - Unlock user
- GET /api/v3/users/schema - View user schema
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, List
from ..database import get_db
from ..repositories import UserRepository
from ..services import (
    UserCreateService,
    UserUpdateService,
    UserDeleteService,
    UserChangePasswordService
)
from ..models import User, UserStatus
from .schemas import (
    UserResponse,
    UserCollectionResponse,
    UserCreate,
    UserUpdate,
    UserSchemaResponse,
    ErrorResponse,
    HALLink,
    HALLinks,
    LockResponse,
    UnlockResponse,
    UserStatusEnum
)
from .dependencies import (
    CurrentUser,
    CurrentUserOptional,
    ManageUserPermission,
    get_user_repository
)

router = APIRouter(prefix="/api/v3/users", tags=["users"])


def user_to_response(user: User, base_url: str = "http://localhost:8000") -> UserResponse:
    """Convert User model to UserResponse"""
    return UserResponse(
        id=user.id,
        login=user.login,
        firstName=user.firstname,
        lastName=user.lastname,
        name=user.name(),
        email=user.mail or "",
        admin=user.admin,
        status=UserStatusEnum(user.status.name.lower()),
        language=user.language,
        identityUrl=None,
        createdAt=user.created_at,
        updatedAt=user.updated_at,
        _links=HALLinks(
            self=HALLink(href=f"{base_url}/api/v3/users/{user.id}")
        )
    )


@router.get("", response_model=UserCollectionResponse)
async def list_users(
    offset: int = Query(0, ge=0, description="Page number"),
    pageSize: int = Query(20, ge=1, le=100, description="Elements per page"),
    filters: Optional[str] = Query(None, description="JSON filter conditions"),
    sortBy: Optional[str] = Query(None, description="JSON sort criteria"),
    current_user: User = Depends(ManageUserPermission),
    repo: UserRepository = Depends(get_user_repository)
):
    """
    List users.

    Requires administrator privileges or manage_user global permission.
    """
    # Parse filters if provided (simplified implementation)
    status_filter = None
    search_filter = None

    users, total = repo.list_users(
        offset=offset,
        limit=pageSize,
        status=status_filter,
        search=search_filter
    )

    user_responses = [user_to_response(user) for user in users]

    return UserCollectionResponse(
        total=total,
        count=len(user_responses),
        pageSize=pageSize,
        offset=offset,
        _embedded={"elements": user_responses},
        _links=HALLinks(
            self=HALLink(href=f"/api/v3/users?offset={offset}&pageSize={pageSize}")
        )
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(ManageUserPermission),
    repo: UserRepository = Depends(get_user_repository),
    db: Session = Depends(get_db)
):
    """
    Create a new user.

    Requires administrator privileges.
    """
    # Convert status enum to UserStatus
    status_map = {
        "active": UserStatus.ACTIVE,
        "registered": UserStatus.REGISTERED,
        "invited": UserStatus.INVITED,
        "locked": UserStatus.LOCKED
    }

    # Prepare parameters for create service
    params = {
        'login': user_data.login,
        'firstname': user_data.firstName,
        'lastname': user_data.lastName,
        'mail': user_data.email,
        'password': user_data.password,
        'status': status_map.get(user_data.status.value, UserStatus.ACTIVE),
        'admin': user_data.admin,
        'language': user_data.language
    }

    if user_data.preferences:
        params['preferences'] = {
            'timezone': user_data.preferences.timezone,
            'hide_mail': user_data.preferences.hide_mail,
            'comments_sorting': user_data.preferences.comments_sorting,
            'warn_on_leaving_unsaved': user_data.preferences.warn_on_leaving_unsaved,
            'theme': user_data.preferences.theme,
            'notification_settings': user_data.preferences.notification_settings
        }

    # Create user using service
    service = UserCreateService(user=current_user)
    result = service.call(params)

    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "_type": "Error",
                "errorIdentifier": "urn:openproject-org:api:v3:errors:PropertyConstraintViolation",
                "message": "Validation failed",
                "details": result.errors
            }
        )

    # Persist to database
    created_user = repo.create(result.result)

    return user_to_response(created_user)


@router.get("/schema", response_model=UserSchemaResponse)
async def get_user_schema(
    current_user: Optional[User] = Depends(CurrentUserOptional)
):
    """
    Get the user schema definition.

    Returns property definitions and validation rules.
    """
    return UserSchemaResponse(
        login={
            "type": "String",
            "name": "Login",
            "required": True,
            "minLength": 1,
            "maxLength": 256,
            "hasDefault": False,
            "writable": True
        },
        firstName={
            "type": "String",
            "name": "First name",
            "required": False,
            "minLength": 0,
            "maxLength": 256,
            "hasDefault": False,
            "writable": True
        },
        lastName={
            "type": "String",
            "name": "Last name",
            "required": False,
            "minLength": 0,
            "maxLength": 256,
            "hasDefault": False,
            "writable": True
        },
        email={
            "type": "String",
            "name": "Email",
            "required": True,
            "hasDefault": False,
            "writable": True
        },
        admin={
            "type": "Boolean",
            "name": "Administrator",
            "required": False,
            "hasDefault": True,
            "writable": True
        },
        status={
            "type": "String",
            "name": "Status",
            "required": False,
            "hasDefault": True,
            "writable": True,
            "_links": {}
        },
        language={
            "type": "String",
            "name": "Language",
            "required": False,
            "hasDefault": True,
            "writable": True
        },
        password={
            "type": "String",
            "name": "Password",
            "required": True,
            "minLength": 8,
            "hasDefault": False,
            "writable": True
        },
        _links=HALLinks(
            self=HALLink(href="/api/v3/users/schema")
        )
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str = Path(..., description="User ID or 'me' for current user"),
    current_user: Optional[User] = Depends(CurrentUserOptional),
    repo: UserRepository = Depends(get_user_repository)
):
    """
    Get a user by ID.

    - **user_id**: The user ID (numeric) or use 'me' for the current user

    Example: `/api/v3/users/123456` or `/api/v3/users/me`
    """
    if user_id == "me":
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        return user_to_response(current_user)

    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    user = repo.find_by_id(user_id_int)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    return user_to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int = Path(..., description="User ID to update"),
    user_data: UserUpdate = ...,
    current_user: User = Depends(ManageUserPermission),
    repo: UserRepository = Depends(get_user_repository)
):
    """
    Update a user.

    - **user_id**: The numeric ID of the user to update
    - Requires administrator privileges or manage_user permission
    """
    user = repo.find_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Build update parameters
    params = {}
    if user_data.login is not None:
        params['login'] = user_data.login
    if user_data.firstName is not None:
        params['firstname'] = user_data.firstName
    if user_data.lastName is not None:
        params['lastname'] = user_data.lastName
    if user_data.email is not None:
        params['mail'] = user_data.email
    if user_data.language is not None:
        params['language'] = user_data.language
    if user_data.admin is not None:
        params['admin'] = user_data.admin
    if user_data.status is not None:
        status_map = {
            "active": UserStatus.ACTIVE,
            "registered": UserStatus.REGISTERED,
            "invited": UserStatus.INVITED,
            "locked": UserStatus.LOCKED
        }
        params['status'] = status_map.get(user_data.status.value, user.status)

    if user_data.preferences is not None:
        params['preferences'] = {
            'timezone': user_data.preferences.timezone,
            'hide_mail': user_data.preferences.hide_mail,
            'comments_sorting': user_data.preferences.comments_sorting,
            'warn_on_leaving_unsaved': user_data.preferences.warn_on_leaving_unsaved,
            'theme': user_data.preferences.theme,
            'notification_settings': user_data.preferences.notification_settings
        }

    # Update using service
    service = UserUpdateService(user=current_user, model=user)
    result = service.call(params)

    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "_type": "Error",
                "message": "Validation failed",
                "details": result.errors
            }
        )

    # Persist changes
    updated_user = repo.update(result.result)

    return user_to_response(updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_user(
    user_id: int = Path(..., description="User ID to delete"),
    current_user: User = Depends(ManageUserPermission),
    repo: UserRepository = Depends(get_user_repository)
):
    """
    Delete a user.

    - **user_id**: The numeric ID of the user to delete
    - Performs a soft delete by setting status to DELETED
    - Requires administrator privileges
    """
    user = repo.find_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Delete using service
    service = UserDeleteService(user=current_user, model=user)
    result = service.call()

    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": result.message}
        )

    # Persist deletion
    repo.delete(user_id)

    return {}  # Empty response with 202 Accepted


@router.post("/{user_id}/lock", response_model=LockResponse)
async def lock_user(
    user_id: int = Path(..., description="User ID to lock"),
    current_user: User = Depends(ManageUserPermission),
    repo: UserRepository = Depends(get_user_repository)
):
    """
    Lock a user account.

    - **user_id**: The numeric ID of the user to lock
    - Prevents the user from logging in
    - Requires administrator privileges
    """
    user = repo.find_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    if user.is_locked():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User is already locked"
        )

    user.lock()
    repo.update(user)

    return LockResponse()


@router.post("/{user_id}/unlock", response_model=UnlockResponse)
async def unlock_user(
    user_id: int = Path(..., description="User ID to unlock"),
    current_user: User = Depends(ManageUserPermission),
    repo: UserRepository = Depends(get_user_repository)
):
    """
    Unlock a user account.

    - **user_id**: The numeric ID of the user to unlock
    - Allows a locked user to log in again
    - Requires administrator privileges
    """
    user = repo.find_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    if not user.is_locked():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User is not locked"
        )

    user.unlock()
    repo.update(user)

    return UnlockResponse()
