"""
Services package - Business logic layer.

Organized by module for better structure and maintainability.
"""

try:
    from .base_service import (
        BaseService,
        BaseCreateService,
        BaseUpdateService,
        BaseDeleteService,
        BaseSetAttributesService
    )
    # Import from new module-based structure
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
except ImportError:
    # Fallback for absolute imports
    from services.base_service import (
        BaseService,
        BaseCreateService,
        BaseUpdateService,
        BaseDeleteService,
        BaseSetAttributesService
    )
    from services.users import (
        UserCreateService,
        UserUpdateService,
        UserDeleteService,
        UserLoginService,
        UserLogoutService,
        UserChangePasswordService,
        UserRegisterService,
    )
    from services.projects import ProjectService
    from services.members import MemberService
    from services.meetings import (
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
