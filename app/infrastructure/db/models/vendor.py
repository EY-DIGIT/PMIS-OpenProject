"""Vendor SQLAlchemy model.

Simple catalog table that backs the project + milestone vendor-picker. Full
"vendor management" (contracts, onboarding flows, etc.) is a future feature;
for now this is just a named reference rows can point at.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text
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

    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_vendors_active_name", "active", "name"),
    )

    def __repr__(self) -> str:
        return f"<VendorModel(id='{self.id}', name='{self.name}', active={self.active})>"
