"""Vendor + project/milestone-vendor association queries.

Keep this repository simple — no soft-delete, just an ``active`` flag. If a
vendor is deactivated, the existing project/milestone associations are NOT
deleted (they stay as history); new attachments simply won't be allowed to
reference an inactive vendor (enforced at the service layer).
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models.milestone_vendor import MilestoneVendorModel
from ..models.project_vendor import ProjectVendorModel
from ..models.vendor import VendorModel
from ....domain.vendors.vendor import Vendor


def _to_domain(m: VendorModel) -> Vendor:
    return Vendor(
        id=m.id,
        name=m.name,
        description=m.description,
        active=bool(m.active),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class VendorRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- Vendor CRUD (lightweight) ------------------------------------

    def create(self, *, name: str, description: Optional[str] = None, active: bool = True) -> Vendor:
        m = VendorModel(name=name.strip(), description=description, active=active)
        self.db.add(m)
        self.db.flush()
        return _to_domain(m)

    def get_by_id(self, vendor_id: str) -> Optional[Vendor]:
        m = self.db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
        return _to_domain(m) if m else None

    def get_by_name(self, name: str) -> Optional[Vendor]:
        m = self.db.query(VendorModel).filter(VendorModel.name == name).first()
        return _to_domain(m) if m else None

    def list_active(self) -> List[Vendor]:
        rows = (
            self.db.query(VendorModel)
            .filter(VendorModel.active == True)  # noqa: E712
            .order_by(VendorModel.name.asc())
            .all()
        )
        return [_to_domain(r) for r in rows]

    def list_all(self) -> List[Vendor]:
        rows = self.db.query(VendorModel).order_by(VendorModel.name.asc()).all()
        return [_to_domain(r) for r in rows]

    def existing_active_ids(self, ids: List[str]) -> List[str]:
        """Filter the supplied ids down to the subset that exists and is active."""
        if not ids:
            return []
        rows = (
            self.db.query(VendorModel.id)
            .filter(VendorModel.id.in_(ids))
            .filter(VendorModel.active == True)  # noqa: E712
            .all()
        )
        return [r[0] for r in rows]

    # ---- Project-Vendor associations ----------------------------------

    def set_project_vendors(self, project_id: str, vendor_ids: List[str]) -> None:
        """Replace the full vendor set for a project. Does NOT commit."""
        self.db.query(ProjectVendorModel).filter(
            ProjectVendorModel.project_id == project_id
        ).delete(synchronize_session=False)
        for vid in vendor_ids:
            self.db.add(ProjectVendorModel(project_id=project_id, vendor_id=vid))
        self.db.flush()

    def list_project_vendors(self, project_id: str) -> List[Tuple[str, str]]:
        """Return [(vendor_id, vendor_name), ...] for the project."""
        rows = (
            self.db.query(VendorModel.id, VendorModel.name)
            .join(ProjectVendorModel, ProjectVendorModel.vendor_id == VendorModel.id)
            .filter(ProjectVendorModel.project_id == project_id)
            .order_by(VendorModel.name.asc())
            .all()
        )
        return [(r[0], r[1]) for r in rows]

    def project_vendor_ids(self, project_id: str) -> List[str]:
        rows = (
            self.db.query(ProjectVendorModel.vendor_id)
            .filter(ProjectVendorModel.project_id == project_id)
            .all()
        )
        return [r[0] for r in rows]

    # ---- Milestone-Vendor associations --------------------------------

    def set_milestone_vendors(self, milestone_id: str, vendor_ids: List[str]) -> None:
        """Replace the full vendor set for a milestone. Does NOT commit."""
        self.db.query(MilestoneVendorModel).filter(
            MilestoneVendorModel.milestone_id == milestone_id
        ).delete(synchronize_session=False)
        for vid in vendor_ids:
            self.db.add(MilestoneVendorModel(milestone_id=milestone_id, vendor_id=vid))
        self.db.flush()

    def list_milestone_vendors(self, milestone_id: str) -> List[Tuple[str, str]]:
        rows = (
            self.db.query(VendorModel.id, VendorModel.name)
            .join(MilestoneVendorModel, MilestoneVendorModel.vendor_id == VendorModel.id)
            .filter(MilestoneVendorModel.milestone_id == milestone_id)
            .order_by(VendorModel.name.asc())
            .all()
        )
        return [(r[0], r[1]) for r in rows]
