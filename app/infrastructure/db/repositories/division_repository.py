"""Division repository — backs the project-owner picker.

Reads + the upsert-on-others-label write path. The seed of the three
built-in rows (``tmd1`` / ``tmd2`` / ``others``) lives in ``init_db``;
this repo is purely runtime CRUD.
"""
import re
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.division import DivisionModel


def slugify(label: str) -> str:
    """Lowercase + strip + replace whitespace runs and non-alnum chars
    with a single underscore. Used to mint a wire code from a human label.

        slugify('  Engineering R&D  ') == 'engineering_r_d'

    Two labels that differ only in casing or punctuation collapse to the
    same code (so the next user picking 'Engineering' from the dropdown
    doesn't accidentally create a third row).
    """
    s = (label or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s


class DivisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_active(self) -> List[DivisionModel]:
        """All active divisions in stable display order: built-ins first
        (in code order), then user-added rows in created_at order."""
        return (
            self.db.query(DivisionModel)
            .filter(DivisionModel.active.is_(True))
            .order_by(
                DivisionModel.is_builtin.desc(),
                DivisionModel.id.asc(),
            )
            .all()
        )

    def get_by_code(self, code: str) -> Optional[DivisionModel]:
        """Lookup by lowercase wire code. Returns None on miss / inactive."""
        if not code:
            return None
        return (
            self.db.query(DivisionModel)
            .filter(DivisionModel.code == code.strip().lower())
            .filter(DivisionModel.active.is_(True))
            .first()
        )

    def is_known_code(self, code: str) -> bool:
        return self.get_by_code(code) is not None

    def upsert_user_division(self, label: str) -> Optional[DivisionModel]:
        """Insert a new user-added division, or no-op if the slugified
        code already exists. Returns the row (existing or new), or None
        if the label slugifies to an empty string (caller-side guard).
        Caller owns the transaction — does NOT commit.
        """
        code = slugify(label)
        if not code:
            return None
        existing = (
            self.db.query(DivisionModel)
            .filter(DivisionModel.code == code)
            .first()
        )
        if existing is not None:
            # Re-activate if it was soft-disabled. Don't touch the label —
            # preserves whatever the original creator typed.
            if not existing.active:
                existing.active = True
                self.db.flush()
            return existing
        row = DivisionModel(
            code=code,
            label=(label or "").strip(),
            is_builtin=False,
            requires_other=False,
            active=True,
        )
        self.db.add(row)
        self.db.flush()
        return row
