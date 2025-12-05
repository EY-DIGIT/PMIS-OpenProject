from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

try:
    from ..utils import ServiceResult
    from ..models import User
except ImportError:
    from utils import ServiceResult
    from models import User


class BaseService(ABC):
    """
    Abstract base class for all services.

    Based on OpenProject's BaseServices pattern.
    """

    def __init__(self, user: Optional[User] = None):
        """
        Initialize service.

        Args:
            user: Current user performing the action (for authorization)
        """
        self.user = user
        self.model: Any = None

    @abstractmethod
    def call(self, *args, **kwargs) -> ServiceResult:
        """Execute the service operation"""
        pass

    def authorized(self) -> bool:
        """
        Check if current user is authorized to perform this action.

        Returns:
            True if authorized, False otherwise
        """
        # Default implementation - override in subclasses
        return True


class BaseCreateService(BaseService):
    """
    Base service for creating resources.

    Based on OpenProject's BaseServices::Create
    """

    def __init__(self, user: Optional[User] = None):
        super().__init__(user)

    def call(self, params: Dict[str, Any]) -> ServiceResult:
        """
        Create a new resource.

        Args:
            params: Parameters for resource creation

        Returns:
            ServiceResult with created resource or errors
        """
        if not self.authorized():
            return ServiceResult.failure_result(
                message="User not authorized to perform this action"
            )

        # Set attributes
        result = self.set_attributes(params)
        if result.is_failure():
            return result

        # Validate
        result = self.validate_and_result()
        if result.is_failure():
            return result

        # Persist
        return self.persist(result)

    def set_attributes(self, params: Dict[str, Any]) -> ServiceResult:
        """Set attributes on the model"""
        # Override in subclasses
        return ServiceResult.success_result(self.model)

    def validate_and_result(self) -> ServiceResult:
        """Validate the model"""
        if self.model and hasattr(self.model, 'validate'):
            if self.model.validate():
                return ServiceResult.success_result(self.model)
            else:
                return ServiceResult.failure_result(
                    errors=self.model.errors,
                    message="Validation failed"
                )
        return ServiceResult.success_result(self.model)

    def persist(self, call_result: ServiceResult) -> ServiceResult:
        """Persist the model to storage"""
        # Override in subclasses to implement actual persistence
        return call_result

    def before_perform(self, params: Dict[str, Any]):
        """Hook called before the main operation"""
        pass

    def after_perform(self, result: ServiceResult):
        """Hook called after the main operation"""
        pass


class BaseUpdateService(BaseService):
    """
    Base service for updating resources.

    Based on OpenProject's BaseServices::Update
    """

    def __init__(self, user: Optional[User] = None, model: Any = None):
        super().__init__(user)
        self.model = model

    def call(self, params: Dict[str, Any]) -> ServiceResult:
        """
        Update an existing resource.

        Args:
            params: Parameters for resource update

        Returns:
            ServiceResult with updated resource or errors
        """
        if not self.authorized():
            return ServiceResult.failure_result(
                message="User not authorized to perform this action"
            )

        if not self.model:
            return ServiceResult.failure_result(
                message="No model provided for update"
            )

        # Before perform hook
        self.before_perform(params)

        # Set attributes
        result = self.set_attributes(params)
        if result.is_failure():
            return result

        # Validate
        result = self.validate_and_result()
        if result.is_failure():
            return result

        # Persist
        result = self.persist(result)

        # After perform hook
        self.after_perform(result)

        return result

    def set_attributes(self, params: Dict[str, Any]) -> ServiceResult:
        """Set attributes on the model"""
        # Override in subclasses
        return ServiceResult.success_result(self.model)

    def validate_and_result(self) -> ServiceResult:
        """Validate the model"""
        if self.model and hasattr(self.model, 'validate'):
            if self.model.validate():
                return ServiceResult.success_result(self.model)
            else:
                return ServiceResult.failure_result(
                    errors=self.model.errors,
                    message="Validation failed"
                )
        return ServiceResult.success_result(self.model)

    def persist(self, call_result: ServiceResult) -> ServiceResult:
        """Persist the model to storage"""
        # Override in subclasses to implement actual persistence
        return call_result

    def before_perform(self, params: Dict[str, Any]):
        """Hook called before the main operation"""
        pass

    def after_perform(self, result: ServiceResult):
        """Hook called after the main operation"""
        pass


class BaseDeleteService(BaseService):
    """
    Base service for deleting resources.

    Based on OpenProject's BaseServices::Delete
    """

    def __init__(self, user: Optional[User] = None, model: Any = None):
        super().__init__(user)
        self.model = model

    def call(self) -> ServiceResult:
        """
        Delete a resource.

        Returns:
            ServiceResult indicating success or failure
        """
        if not self.authorized():
            return ServiceResult.failure_result(
                message="User not authorized to perform this action"
            )

        if not self.model:
            return ServiceResult.failure_result(
                message="No model provided for deletion"
            )

        return self.destroy()

    @abstractmethod
    def destroy(self) -> ServiceResult:
        """Perform the actual deletion"""
        pass


class BaseSetAttributesService(BaseService):
    """
    Base service for setting attributes on a model.

    Based on OpenProject's BaseServices::SetAttributes
    """

    def __init__(self, user: Optional[User] = None, model: Any = None):
        super().__init__(user)
        self.model = model

    def call(self, params: Dict[str, Any]) -> ServiceResult:
        """
        Set attributes on the model.

        Args:
            params: Parameters to set

        Returns:
            ServiceResult with updated model
        """
        result = self.set_attributes(params)
        if result.is_failure():
            return result

        return self.validate_and_result()

    def set_attributes(self, params: Dict[str, Any]) -> ServiceResult:
        """Set attributes on the model"""
        # Override in subclasses
        return ServiceResult.success_result(self.model)

    def validate_and_result(self) -> ServiceResult:
        """Validate the model"""
        if self.model and hasattr(self.model, 'validate'):
            if self.model.validate():
                return ServiceResult.success_result(self.model)
            else:
                return ServiceResult.failure_result(
                    errors=self.model.errors,
                    message="Validation failed"
                )
        return ServiceResult.success_result(self.model)

    def set_default_attributes(self, params: Dict[str, Any]):
        """Set default attributes on the model"""
        # Override in subclasses
        pass
