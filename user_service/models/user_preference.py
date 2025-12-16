from datetime import datetime, timezone as dt_timezone
from typing import Optional, Dict, Any


class UserPreference:
    """
    Stores individual user preferences and settings.

    Based on OpenProject's UserPreference model.
    """

    def __init__(
        self,
        id: Optional[int] = None,
        user_id: Optional[int] = None,
        timezone: str = 'UTC',
        hide_mail: bool = True,
        time_zone: Optional[str] = None,
        comments_sorting: str = 'asc',
        warn_on_leaving_unsaved: bool = True,
        theme: str = 'default',
        notification_settings: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.timezone = timezone or time_zone or 'UTC'
        self.hide_mail = hide_mail
        self.comments_sorting = comments_sorting
        self.warn_on_leaving_unsaved = warn_on_leaving_unsaved
        self.theme = theme
        self.notification_settings = notification_settings or {}
        self.created_at = datetime.now(dt_timezone.utc)
        self.updated_at = datetime.now(dt_timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert preferences to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'timezone': self.timezone,
            'hide_mail': self.hide_mail,
            'comments_sorting': self.comments_sorting,
            'warn_on_leaving_unsaved': self.warn_on_leaving_unsaved,
            'theme': self.theme,
            'notification_settings': self.notification_settings,
        }

    def __repr__(self) -> str:
        return f"<UserPreference(id={self.id}, user_id={self.user_id}, timezone='{self.timezone}')>"
