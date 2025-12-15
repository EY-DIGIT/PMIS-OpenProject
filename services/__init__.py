"""
Services package - Business logic layer.

Organized by module for better structure and maintainability.
"""

from .base_service import (
    BaseService,
    BaseCreateService,
    BaseUpdateService,
    BaseDeleteService,
    BaseSetAttributesService,
)

# Import from module-based structure (explicit relative imports only)
from .users import (
    UserCreateService,
    UserUpdateService,
    UserDeleteService,
    UserLoginService,
    UserLogoutService,
    UserChangePasswordService,
    UserRegisterService,
)
from .projects import ProjectService
from .members import MemberService
from .meetings import (
    MeetingCreateService,
    MeetingUpdateService,
    MeetingDeleteService,
    MeetingListService,
)

__all__ = [
    # Base services
    'BaseService',
    'BaseCreateService',
    'BaseUpdateService',
    'BaseDeleteService',
    'BaseSetAttributesService',
    # User services
    'UserCreateService',
    'UserUpdateService',
    'UserDeleteService',
    'UserLoginService',
    'UserLogoutService',
    'UserChangePasswordService',
    'UserRegisterService',
    # Project services
    'ProjectService',
    # Member services
    'MemberService',
    # Meeting services
    'MeetingCreateService',
    'MeetingUpdateService',
    'MeetingDeleteService',
    'MeetingListService',
]
