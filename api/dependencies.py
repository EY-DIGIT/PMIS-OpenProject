"""
API dependencies and dependency injection.
"""

from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
try:
    from ..database import get_db
    from ..models import User, UserStatus
    from ..repositories import UserRepository
except ImportError:
    from database import get_db
    from models import User, UserStatus
    from repositories import UserRepository


security_basic = HTTPBasic(auto_error=False)
security_bearer = HTTPBearer(auto_error=False)


def get_user_repository(db: Session = Depends(get_db, use_cache=True)) -> UserRepository:
    """Get user repository instance"""
    return UserRepository(db)


async def get_current_user_optional(
    credentials: Optional[HTTPBasicCredentials] = Depends(security_basic),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_requested_with: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current authenticated user (optional).

    Supports multiple authentication methods:
    1. API Key (Basic Auth with username='apikey')
    2. Bearer Token (OAuth2/JWT)
    3. Session-based (Angular client with X-Requested-With header)
    """
    repo = UserRepository(db)

    # Method 1: API Key authentication
    if credentials:
        if credentials.username == 'apikey':
            user = repo.find_by_api_key(credentials.password)
            if user and user.is_active():
                return user
        else:
            # Try username/password
            user = repo.find_by_login_or_email(credentials.username)
            if user and user.check_password(credentials.password) and user.is_active():
                return user

    # Method 2: Bearer token (OAuth2/JWT)
    if bearer:
        # For now, treat bearer token as API token
        user = repo.find_by_api_token(bearer.credentials)
        if user and user.is_active():
            return user

    # Method 3: Session-based (for Angular client)
    if x_requested_with == "XMLHttpRequest":
        # Session would be managed by middleware
        # For now, return None - would integrate with session storage
        pass

    return None


async def get_current_user(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """Get current authenticated user (required)"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic, Bearer"},
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current authenticated admin user"""
    if not current_user.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user


def require_manage_user_permission(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require manage_user global permission"""
    # In a full implementation, check actual permissions
    if not current_user.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires manage_user global permission"
        )
    return current_user


# Type aliases for dependency injection with include_in_schema=False to hide from docs
from fastapi.params import Depends as DependsClass

def _get_current_user_dep():
    return Depends(get_current_user, use_cache=True)

def _get_current_user_optional_dep():
    return Depends(get_current_user_optional, use_cache=True)

def _get_current_admin_user_dep():
    return Depends(get_current_admin_user, use_cache=True)

def _require_manage_user_permission_dep():
    return Depends(require_manage_user_permission, use_cache=True)

def _get_user_repository_dep():
    return Depends(get_user_repository, use_cache=True)

CurrentUser = Annotated[User, _get_current_user_dep()]
CurrentUserOptional = Annotated[Optional[User], _get_current_user_optional_dep()]
AdminUser = Annotated[User, _get_current_admin_user_dep()]
ManageUserPermission = Annotated[User, _require_manage_user_permission_dep()]
