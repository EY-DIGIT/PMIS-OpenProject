from typing import Any, Dict, List, Optional


class ServiceResult:
    """
    Result object returned by service operations.

    Based on OpenProject's ServiceResult pattern.
    """

    def __init__(
        self,
        success: bool = True,
        result: Any = None,
        errors: Optional[Dict[str, List[str]]] = None,
        message: Optional[str] = None
    ):
        self.success = success
        self.result = result
        self.errors = errors or {}
        self.message = message

    def is_success(self) -> bool:
        """Check if operation was successful"""
        return self.success

    def is_failure(self) -> bool:
        """Check if operation failed"""
        return not self.success

    def add_error(self, field: str, message: str):
        """Add an error to a specific field"""
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(message)

    def merge_errors(self, other_errors: Dict[str, List[str]]):
        """Merge errors from another source"""
        for field, messages in other_errors.items():
            if field not in self.errors:
                self.errors[field] = []
            self.errors[field].extend(messages)

    @classmethod
    def success_result(cls, result: Any = None, message: Optional[str] = None) -> 'ServiceResult':
        """Create a success result"""
        return cls(success=True, result=result, message=message)

    @classmethod
    def failure_result(
        cls,
        errors: Optional[Dict[str, List[str]]] = None,
        message: Optional[str] = None
    ) -> 'ServiceResult':
        """Create a failure result"""
        return cls(success=False, errors=errors or {}, message=message)

    def __repr__(self) -> str:
        status = "Success" if self.success else "Failure"
        return f"<ServiceResult({status}, errors={len(self.errors)})>"
