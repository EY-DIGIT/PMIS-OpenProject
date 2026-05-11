"""
Work Package Type domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ...shared.datetime import iso_ist


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
            "created_at": iso_ist(self.created_at),
            "updated_at": iso_ist(self.updated_at),
        }
