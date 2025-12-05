from typing import Dict, Any, Optional
from datetime import datetime, timezone
import re

from .base_service import (
    BaseCreateService,
    BaseUpdateService,
    BaseDeleteService,
    BaseSetAttributesService
)
from ..models import User, UserStatus, UserPreference
from ..utils import ServiceResult


class UserSetAttributesService(BaseSetAttributesService):
    """
    Service for setting attributes on a user.

    Based on OpenProject's Users::SetAttributesService
    """

    def __init__(self, user: Optional[User] = None, model: Optional[User] = None):
        super().__init__(user, model)
        self._preferences_params: Optional[Dict[str, Any]] = None

    def set_attributes(self, params: Dict[str, Any]) -> ServiceResult:
        """
        Set attributes on the user model.

        Args:
            params: Dictionary of attributes to set

        Returns:
            ServiceResult with updated user
        """
        # Extract preferences if present
        self._preferences_params = params.pop('preferences', None)

        # Set default attributes for new users
        if not self.model.id:
            self.set_default_attributes(params)

        # Set basic attributes
        for key, value in params.items():
            if hasattr(self.model, key):
                setattr(self.model, key, value)

        return ServiceResult.success_result(self.model)

    def validate_and_result(self) -> ServiceResult:
        """Validate the model and preferences"""
        result = super().validate_and_result()

        if result.is_failure():
            return result

        # Set and validate preferences if provided
        if self._preferences_params:
            pref_result = self.set_preferences()
            if pref_result.is_failure():
                result.merge_errors(pref_result.errors)
                return ServiceResult.failure_result(
                    errors=result.errors,
                    message="Preference validation failed"
                )

        return result

    def set_default_attributes(self, params: Dict[str, Any]):
        """
        Set default attributes for new users.

        Args:
            params: Parameters being set
        """
        # Assign name from email if invited and names not provided
        if self.model.is_invited() and self.model.mail:
            self.assign_name_from_mail(params)

        # Set default language
        if not self.model.language:
            self.assign_default_language()

        # Initialize preferences if not exists
        if not self.model.preference:
            self.model.preference = UserPreference(user_id=self.model.id)

    def assign_name_from_mail(self, params: Dict[str, Any]):
        """
        Generate name from email for invited users.

        Args:
            params: Current parameters being set
        """
        if not params.get('login') and self.model.mail:
            self.model.login = self.model.mail

        if not params.get('firstname') and not self.model.firstname:
            placeholder = self.placeholder_name(self.model.mail)
            self.model.firstname = placeholder

        if not params.get('lastname') and not self.model.lastname:
            domain = self.model.mail.split('@')[1] if '@' in self.model.mail else ''
            self.model.lastname = self.trim_name(domain)

    def assign_default_language(self):
        """Set default language"""
        # Would typically read from system configuration
        self.model.language = 'en'

    def placeholder_name(self, email: str) -> str:
        """
        Generate placeholder name from email.

        Args:
            email: Email address

        Returns:
            Placeholder name
        """
        if '@' in email:
            local_part = email.split('@')[0]
            return self.trim_name(local_part)
        return self.trim_name(email)

    def trim_name(self, name: str) -> str:
        """
        Trim name to reasonable length.

        Args:
            name: Name to trim

        Returns:
            Trimmed name
        """
        max_length = 30
        if len(name) > max_length:
            return name[:27] + '...'
        return name

    def set_preferences(self) -> ServiceResult:
        """
        Set user preferences.

        Returns:
            ServiceResult indicating success or failure
        """
        if not self.model.preference:
            self.model.preference = UserPreference(user_id=self.model.id)

        for key, value in self._preferences_params.items():
            if hasattr(self.model.preference, key):
                setattr(self.model.preference, key, value)

        return ServiceResult.success_result(self.model.preference)


class UserCreateService(BaseCreateService):
    """
    Service for creating users.

    Based on OpenProject's Users::CreateService
    """

    def __init__(self, user: Optional[User] = None):
        super().__init__(user)

    def call(self, params: Dict[str, Any]) -> ServiceResult:
        """
        Create a new user.

        Args:
            params: User parameters

        Returns:
            ServiceResult with created user or errors
        """
        # Create new user model
        self.model = User()

        # Use set attributes service
        set_attrs_service = UserSetAttributesService(self.user, self.model)
        result = set_attrs_service.call(params)

        if result.is_failure():
            return result

        self.model = result.result

        # Handle invited users specially
        if self.model.is_invited():
            return self.persist_invited(self.model)

        return self.persist(result)

    def persist_invited(self, new_user: User) -> ServiceResult:
        """
        Handle persistence for invited users.

        Args:
            new_user: The invited user

        Returns:
            ServiceResult
        """
        # Ensure email exists for invited users
        if not new_user.mail:
            return ServiceResult.failure_result(
                errors={'mail': ['Email is required for invited users']},
                message="Email is required for invited users"
            )

        # Would typically send invitation email here
        return self.invite_user(new_user)

    def invite_user(self, new_user: User) -> ServiceResult:
        """
        Send invitation to user.

        Args:
            new_user: User to invite

        Returns:
            ServiceResult
        """
        # In production, this would generate invitation token and send email
        # For now, just validate and return
        if new_user.validate():
            return ServiceResult.success_result(
                new_user,
                message="User invitation sent successfully"
            )
        else:
            return ServiceResult.failure_result(
                errors=new_user.errors,
                message="User invitation failed"
            )

    def persist(self, call_result: ServiceResult) -> ServiceResult:
        """
        Persist user to storage.

        Args:
            call_result: Result from previous operations

        Returns:
            ServiceResult
        """
        # In production, this would save to database
        # For this example, we'll just validate and return
        user = call_result.result

        if user.validate():
            # Simulate ID assignment
            if not user.id:
                user.id = hash(user.login) % 1000000

            user.created_at = datetime.now(timezone.utc)
            user.updated_at = datetime.now(timezone.utc)

            return ServiceResult.success_result(
                user,
                message="User created successfully"
            )
        else:
            return ServiceResult.failure_result(
                errors=user.errors,
                message="User creation failed"
            )


class UserUpdateService(BaseUpdateService):
    """
    Service for updating users.

    Based on OpenProject's Users::UpdateService
    """

    def __init__(self, user: Optional[User] = None, model: Optional[User] = None):
        super().__init__(user, model)

    def before_perform(self, params: Dict[str, Any]):
        """Hook before update"""
        # Could trigger custom hooks here
        super().before_perform(params)

    def set_attributes(self, params: Dict[str, Any]) -> ServiceResult:
        """Set attributes using the set attributes service"""
        set_attrs_service = UserSetAttributesService(self.user, self.model)
        return set_attrs_service.call(params)

    def persist(self, call_result: ServiceResult) -> ServiceResult:
        """
        Persist user updates.

        Args:
            call_result: Result from validation

        Returns:
            ServiceResult
        """
        user = call_result.result
        user.updated_at = datetime.now(timezone.utc)

        # Save user (in production, this would update database)
        if user.validate():
            # Also save preferences if they exist
            if user.preference:
                user.preference.updated_at = datetime.now(timezone.utc)

            return ServiceResult.success_result(
                user,
                message="User updated successfully"
            )
        else:
            return ServiceResult.failure_result(
                errors=user.errors,
                message="User update failed"
            )


class UserDeleteService(BaseDeleteService):
    """
    Service for deleting users.

    Based on OpenProject's Users::DeleteService
    """

    def __init__(self, user: Optional[User] = None, model: Optional[User] = None):
        super().__init__(user, model)

    def destroy(self) -> ServiceResult:
        """
        Delete a user (soft delete).

        Returns:
            ServiceResult indicating success
        """
        # Mark user as deleted
        self.model.status = UserStatus.DELETED
        self.model.updated_at = datetime.now(timezone.utc)

        # If deleting current user, handle logout
        if self.is_self_delete():
            self.logout()

        # In production, would queue background job for cleanup
        # For now, just return success
        return ServiceResult.success_result(
            self.model,
            message=f"User {self.model.login} deleted successfully"
        )

    def is_self_delete(self) -> bool:
        """Check if user is deleting themselves"""
        return self.user and self.user.id == self.model.id

    def logout(self):
        """Handle logout for self-delete"""
        # In production, would clear session
        pass


class UserLoginService:
    """
    Service for handling user login.

    Based on OpenProject's Users::LoginService
    """

    def __init__(self, user: User, request_info: Optional[Dict[str, Any]] = None):
        self.user = user
        self.request_info = request_info or {}
        self.session_data: Dict[str, Any] = {}

    def call(self, autologin: bool = False) -> ServiceResult:
        """
        Perform login operations.

        Args:
            autologin: Whether to create autologin token

        Returns:
            ServiceResult indicating success
        """
        # Record successful login
        self.user.record_successful_login()

        # Reset session for security
        self.reset_session()

        # Store user in session
        self.session_data['user_id'] = self.user.id
        self.session_data['last_activity'] = datetime.now(timezone.utc).isoformat()

        # Create autologin token if requested
        if autologin:
            self.set_autologin_cookie()

        # Log successful login
        self.log_successful_login()

        return ServiceResult.success_result(
            self.user,
            message=f"User {self.user.login} logged in successfully"
        )

    def reset_session(self):
        """Reset session for security"""
        # In production, would clear and regenerate session
        self.session_data.clear()

    def set_autologin_cookie(self):
        """Create autologin token and cookie"""
        # In production, would generate secure token and set HTTP-only cookie
        import secrets
        token = secrets.token_urlsafe(32)
        self.session_data['autologin_token'] = token

    def log_successful_login(self):
        """Log the successful login"""
        # In production, would write to audit log
        pass

    def get_session_data(self) -> Dict[str, Any]:
        """Get session data to be stored"""
        return self.session_data


class UserLogoutService:
    """
    Service for handling user logout.

    Based on OpenProject's Users::LogoutService
    """

    def __init__(self, user: User, session_data: Optional[Dict[str, Any]] = None):
        self.user = user
        self.session_data = session_data or {}

    def call(self) -> ServiceResult:
        """
        Perform logout operations.

        Returns:
            ServiceResult indicating success
        """
        # Clear session
        self.session_data.clear()

        # Clear autologin tokens
        self.drop_autologin_tokens()

        # Log logout
        self.log_logout()

        return ServiceResult.success_result(
            message=f"User {self.user.login} logged out successfully"
        )

    def drop_autologin_tokens(self):
        """Remove autologin tokens"""
        # In production, would invalidate all autologin tokens
        pass

    def log_logout(self):
        """Log the logout event"""
        # In production, would write to audit log
        pass


class UserChangePasswordService:
    """
    Service for changing user password.

    Based on OpenProject's Users::ChangePasswordService
    """

    def __init__(self, user: User):
        self.user = user

    def call(
        self,
        current_password: Optional[str],
        new_password: str,
        new_password_confirmation: str
    ) -> ServiceResult:
        """
        Change user password.

        Args:
            current_password: Current password (required for users)
            new_password: New password
            new_password_confirmation: Confirmation of new password

        Returns:
            ServiceResult indicating success or failure
        """
        # Check if password change is allowed
        if not self.user.change_password_allowed():
            return ServiceResult.failure_result(
                message="Password change not allowed for this user"
            )

        # Verify current password
        if current_password and not self.user.check_password(current_password):
            return ServiceResult.failure_result(
                errors={'current_password': ['Current password is incorrect']},
                message="Current password is incorrect"
            )

        # Check password confirmation
        if new_password != new_password_confirmation:
            return ServiceResult.failure_result(
                errors={'password_confirmation': ['Passwords do not match']},
                message="Passwords do not match"
            )

        # Validate password strength
        validation_result = self.validate_password_strength(new_password)
        if validation_result.is_failure():
            return validation_result

        # Set new password
        self.user.password = new_password
        self.user.force_password_change = False
        self.user.updated_at = datetime.now(timezone.utc)

        return ServiceResult.success_result(
            self.user,
            message="Password changed successfully"
        )

    def validate_password_strength(self, password: str) -> ServiceResult:
        """
        Validate password meets strength requirements.

        Args:
            password: Password to validate

        Returns:
            ServiceResult
        """
        errors = {}

        if len(password) < 8:
            errors.setdefault('password', []).append(
                'Password must be at least 8 characters long'
            )

        if not re.search(r'[A-Z]', password):
            errors.setdefault('password', []).append(
                'Password must contain at least one uppercase letter'
            )

        if not re.search(r'[a-z]', password):
            errors.setdefault('password', []).append(
                'Password must contain at least one lowercase letter'
            )

        if not re.search(r'[0-9]', password):
            errors.setdefault('password', []).append(
                'Password must contain at least one digit'
            )

        if errors:
            return ServiceResult.failure_result(
                errors=errors,
                message="Password does not meet strength requirements"
            )

        return ServiceResult.success_result()


class UserRegisterService:
    """
    Service for user self-registration.

    Based on OpenProject's Users::RegisterUserService
    """

    def __init__(self):
        pass

    def call(self, params: Dict[str, Any]) -> ServiceResult:
        """
        Register a new user.

        Args:
            params: Registration parameters

        Returns:
            ServiceResult with registered user or errors
        """
        # Set status to registered (pending activation)
        params['status'] = UserStatus.REGISTERED

        # Use create service
        create_service = UserCreateService()
        result = create_service.call(params)

        if result.is_success():
            # In production, would send activation email
            result.message = "Registration successful. Please check your email for activation instructions."

        return result
