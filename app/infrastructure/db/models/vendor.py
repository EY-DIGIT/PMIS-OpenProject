"""Vendor SQLAlchemy model.

Simple catalog table that backs the project + milestone vendor-picker. Full
"vendor management" (contracts, onboarding flows, etc.) is a future feature;
for now this is just a named reference rows can point at.

Soft-delete columns (`deleted_at`, `deleted_by`) were added so DELETE /vendors/{id}
can hide a vendor from the catalog without losing the historical
project/milestone mappings. Restore by clearing `deleted_at` and flipping
`active` back on.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class VendorModel(Base):
    __tablename__ = "vendors"

    id = Column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid4()),
    )
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Soft-delete. A non-NULL deleted_at hides the vendor from the catalog
    # endpoint and from picker validation, but the project_vendors /
    # milestone_vendors mapping rows are intentionally NOT touched.
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("idx_vendors_active_name", "active", "name"),
        Index("idx_vendors_created_at", "created_at"),
        Index("idx_vendors_deleted_at", "deleted_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<VendorModel(id='{self.id}', name='{self.name}', "
            f"active={self.active}, deleted_at={self.deleted_at})>"
        )
