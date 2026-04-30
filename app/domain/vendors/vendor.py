"""Vendor domain entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Vendor:
    id: str
    name: str
    description: Optional[str]
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    # Contact details (doc 18). All three nullable; the FE renders an
    # empty cell when missing. None of them participate in soft-delete
    # / restore semantics — they're plain attributes.
    email: Optional[str] = None
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "active": self.active,
            "email": self.email,
            "contact_person": self.contact_person,
            "phone_number": self.phone_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "deleted_by": self.deleted_by,
        }
