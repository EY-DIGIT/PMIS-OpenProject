"""Repository for the project_status_transitions catalog.

Reads only — the seed runs once at init_db time. Writes (admin-managed
catalog edits) are not surfaced through the API yet; callers can still
modify rows via the DB if a release ever needs to.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.project_status_transition import ProjectStatusTransitionModel


class ProjectStatusTransitionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_active(self) -> List[ProjectStatusTransitionModel]:
        return (
            self.db.query(ProjectStatusTransitionModel)
            .filter(ProjectStatusTransitionModel.active.is_(True))
            .order_by(
                ProjectStatusTransitionModel.from_status.asc(),
                ProjectStatusTransitionModel.to_status.asc(),
            )
            .all()
        )

    def find_edge(
        self, from_status: Optional[str], to_status: str,
    ) -> Optional[ProjectStatusTransitionModel]:
        """Return the active row matching this edge, or None if missing."""
        q = (
            self.db.query(ProjectStatusTransitionModel)
            .filter(ProjectStatusTransitionModel.to_status == to_status)
            .filter(ProjectStatusTransitionModel.active.is_(True))
        )
        if from_status is None:
            q = q.filter(ProjectStatusTransitionModel.from_status.is_(None))
        else:
            q = q.filter(ProjectStatusTransitionModel.from_status == from_status)
        return q.first()

    def known_to_statuses(self) -> List[str]:
        """Distinct ``to_status`` values across active rows.

        The set of statuses the API recognises is exactly this list — used
        by the create-project validator to reject typos like 'inprogress'
        with ``invalid_status`` rather than letting them through.
        """
        rows = (
            self.db.query(ProjectStatusTransitionModel.to_status)
            .filter(ProjectStatusTransitionModel.active.is_(True))
            .distinct()
            .all()
        )
        return sorted({r[0] for r in rows})
