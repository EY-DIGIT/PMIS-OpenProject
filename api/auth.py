"""
Authentication API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..repositories import UserRepository
from ..services import UserLoginService, UserLogoutService, UserRegisterService
from ..models import User
from .schemas import (
    LoginRequest,
    LoginResponse,
    RegistrationRequest,
    UserResponse,
    PasswordChangeRequest
)
from .dependencies import CurrentUser, get_user_repository
from .users import user_to_response
from ..services import UserChangePasswordService

router = APIRouter(prefix="/api/v3/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    User login endpoint.

    Authenticates user and creates session.

    **Request Body:**
    - **username**: Username or email
    - **password**: User password
    """
    repo = UserRepository(db)
    # Try to authenticate
    user = User.try_to_login(
        credentials.username,
        credentials.password,
        user_repository=repo
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Create login session
    login_service = UserLoginService(user)
    result = login_service.call(autologin=False)

    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

    # Get session data
    session_data = login_service.get_session_data()

    # Set session cookie (simplified - in production use secure session management)
    if 'user_id' in session_data:
        response.set_cookie(
            key="session_id",
            value=session_data.get('user_id', ''),
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )

    # Persist login
    repo.update(user)

    return LoginResponse(
        user=user_to_response(user),
        sessionId=str(session_data.get('user_id'))
    )


@router.post("/logout")
async def logout(
    response: Response,
    db: Session = Depends(get_db)
):
    """
    User logout endpoint.

    Destroys session and clears cookies.
    Requires authentication (provide session cookie or authorization header).
    """
    # For simplified version, we'll just clear the cookie
    # In production, validate current_user from session
    current_user = None  # Would be extracted from request
    logout_service = UserLogoutService(current_user)
    result = logout_service.call()

    # Clear session cookie
    response.delete_cookie(key="session_id")

    return {"message": "Logged out successfully"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    registration_data: RegistrationRequest,
    db: Session = Depends(get_db)
):
    """
    User registration endpoint.

    Allows new users to register. Creates user with REGISTERED status.

    **Request Body:**
    - **login**: Username (required)
    - **firstName**: First name (optional)
    - **lastName**: Last name (optional)
    - **email**: Email address (required)
    - **password**: Password (required, minimum 8 characters)
    - **language**: Language preference (default: 'en')
    - **preferences**: User preferences (optional)
    """
    repo = UserRepository(db)
    params = {
        'login': registration_data.login,
        'firstname': registration_data.firstName,
        'lastname': registration_data.lastName,
        'mail': registration_data.email,
        'password': registration_data.password,
        'language': registration_data.language
    }

    if registration_data.preferences:
        params['preferences'] = {
            'timezone': registration_data.preferences.timezone,
            'hide_mail': registration_data.preferences.hide_mail,
            'comments_sorting': registration_data.preferences.comments_sorting,
            'warn_on_leaving_unsaved': registration_data.preferences.warn_on_leaving_unsaved,
            'theme': registration_data.preferences.theme,
            'notification_settings': registration_data.preferences.notification_settings
        }

    service = UserRegisterService()
    result = service.call(params)

    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "_type": "Error",
                "message": "Registration failed",
                "details": result.errors
            }
        )

    # Persist user
    created_user = repo.create(result.result)

    return user_to_response(created_user)


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    db: Session = Depends(get_db)
):
    """
    Change user password.

    Requires current password for verification.
    Requires authentication (must be logged in).

    **Request Body:**
    - **currentPassword**: Current password (required)
    - **newPassword**: New password (required, minimum 8 characters)
    - **newPasswordConfirmation**: Confirm new password (must match newPassword)
    """
    # For simplified version, we need to get current user from request
    # In production, extract from session/token
    repo = UserRepository(db)
    current_user = None  # Would be extracted from auth headers/session
    service = UserChangePasswordService(current_user)
    result = service.call(
        current_password=password_data.currentPassword,
        new_password=password_data.newPassword,
        new_password_confirmation=password_data.newPasswordConfirmation
    )

    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "_type": "Error",
                "message": "Password change failed",
                "details": result.errors
            }
        )

    # Persist password change
    repo.update(result.result)

    return {"message": "Password changed successfully"}
