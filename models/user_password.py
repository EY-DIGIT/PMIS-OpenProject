from datetime import datetime, timezone
from typing import Optional


class UserPassword:
    """
    Represents a historical password record for password reuse prevention.

    Based on OpenProject's UserPassword model.
    """

    def __init__(
        self,
        id: Optional[int] = None,
        user_id: Optional[int] = None,
        hashed_password: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.user_id = user_id
        self.hashed_password = hashed_password
        self.created_at = created_at or datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<UserPassword(id={self.id}, user_id={self.user_id}, created_at={self.created_at})>"
