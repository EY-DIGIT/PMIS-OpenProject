"""
Work Package Type domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class WorkPackageType:
    id: int
    name: str
    internal_name: str
    is_builtin: bool
    is_active: bool
    position: int
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "internal_name": self.internal_name,
            "is_builtin": self.is_builtin,
            "is_active": self.is_active,
            "position": self.position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
