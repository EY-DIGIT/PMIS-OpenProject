"""
User Service - Python implementation of OpenProject's User Service

Based on OpenProject stable/16 branch user management system.
"""

from .models import (
    User,
    AnonymousUser,
    DeletedUser,
    SystemUser,
    PlaceholderUser,
    UserPassword,
    UserPreference,
    UserStatus
)

from .services import (
    UserCreateService,
    UserUpdateService,
    UserDeleteService,
    UserSetAttributesService,
    UserLoginService,
    UserLogoutService,
    UserChangePasswordService,
    UserRegisterService
)

from .utils import ServiceResult

__version__ = '1.0.0'

__all__ = [
    # Models
    'User',
    'AnonymousUser',
    'DeletedUser',
    'SystemUser',
    'PlaceholderUser',
    'UserPassword',
    'UserPreference',
    'UserStatus',

    # Services
    'UserCreateService',
    'UserUpdateService',
    'UserDeleteService',
    'UserSetAttributesService',
    'UserLoginService',
    'UserLogoutService',
    'UserChangePasswordService',
    'UserRegisterService',

    # Utils
    'ServiceResult',
]
