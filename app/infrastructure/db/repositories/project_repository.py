"""
Project repository for database operations.

Writes (create/update/soft_delete/hard_delete) do NOT commit. Callers own the
transaction boundary and must call ``db.commit()`` after the full operation
succeeds — this lets multi-step flows (version create + subtree clone, project
delete + subtree cascade) run atomically.
"""
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from ..models.project import ProjectModel
from ....domain.projects.project import Project


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dialect_insert(db: Session):
    """Return the dialect-specific insert() construct that supports
    on_conflict_do_update() (PostgreSQL or SQLite)."""
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _insert
        return _insert
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _insert
        return _insert
    raise NotImplementedError(
        f"Upsert is not supported for dialect '{dialect}'. "
        "Only PostgreSQL and SQLite are supported."
    )


class ProjectRepository:
    """Repository for Project database operations."""

    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            identifier=model.identifier,
            name=model.name,
            description=model.description,
            active=model.active,
            public=model.public,
            status_explanation=model.status_explanation,
            created_at=model.created_at,
            updated_at=model.updated_at,
            parent_id=model.parent_id,
            status=model.status,
            owner=model.owner,
            category=model.category,
            start_date=model.start_date,
            end_date=model.end_date,
            actual_end_date=model.actual_end_date,
            is_version=bool(model.is_version),
            version_of=model.version_of,
            baseline_id=model.baseline_id,
            version_no=model.version_no,
            created_by=model.created_by,
            updated_by=model.updated_by,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
        )

    # ------------------------------------------------------------------
    # writes — no commit; caller owns transaction boundary
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        identifier: str,
        name: str,
        description: Optional[str] = None,
        active: bool = True,
        public: bool = False,
        status_explanation: Optional[str] = None,
        parent_id: Optional[int] = None,
        status: str = "new",
        owner: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        actual_end_date: Optional[datetime] = None,
        is_version: bool = False,
        version_of: Optional[int] = None,
        baseline_id: Optional[int] = None,
        version_no: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> Project:
        model = ProjectModel(
            identifier=identifier,
            name=name,
            description=description,
            active=active,
            public=public,
            status_explanation=status_explanation,
            parent_id=parent_id,
            status=status,
            owner=owner,
            category=category,
            start_date=start_date,
            end_date=end_date,
            actual_end_date=actual_end_date,
            is_version=is_version,
            version_of=version_of,
            baseline_id=baseline_id,
            version_no=version_no,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(model)
        self.db.flush()
        return self._to_domain(model)

    def upsert_by_identifier(
        self,
        identifier: str,
        name: str,
        description: Optional[str] = None,
        active: bool = True,
        public: bool = False,
        status_explanation: Optional[str] = None,
        parent_id: Optional[int] = None,
        status: str = "new",
        owner: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[Project, bool]:
        """
        Insert a project if no row with this identifier exists, otherwise
        update the existing row. Atomic via INSERT ... ON CONFLICT (identifier)
        DO UPDATE (SQLite 3.24+ / Postgres 9.5+).

        identifier and created_at are never overwritten; updated_at is bumped.

        Returns:
            (project, created) — created=True on fresh insert, False on update.

        Unlike the other writes, this method commits on success to preserve
        the atomicity of the ON CONFLICT semantics that the wizard flow relies
        on. Callers should not wrap it in their own transaction.
        """
        insert_fn = _dialect_insert(self.db)
        now = _utcnow()

        values = dict(
            identifier=identifier,
            name=name,
            description=description,
            active=active,
            public=public,
            status_explanation=status_explanation,
            parent_id=parent_id,
            status=status,
            owner=owner,
            category=category,
            start_date=start_date,
            end_date=end_date,
            created_at=now,
            updated_at=now,
        )
        stmt = insert_fn(ProjectModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["identifier"],
            set_={
                "name": stmt.excluded.name,
                "description": stmt.excluded.description,
                "active": stmt.excluded.active,
                "public": stmt.excluded.public,
                "status_explanation": stmt.excluded.status_explanation,
                "parent_id": stmt.excluded.parent_id,
                "status": stmt.excluded.status,
                "owner": stmt.excluded.owner,
                "category": stmt.excluded.category,
                "start_date": stmt.excluded.start_date,
                "end_date": stmt.excluded.end_date,
                "updated_at": now,
                # identifier and created_at intentionally preserved.
            },
        )

        # Detect insert vs. update portably by probing before the statement.
        existed_before = (
            self.db.query(ProjectModel.id)
            .filter(ProjectModel.identifier == identifier)
            .first()
            is not None
        )

        self.db.execute(stmt)
        self.db.commit()

        model = (
            self.db.query(ProjectModel)
            .filter(ProjectModel.identifier == identifier)
            .first()
        )
        return self._to_domain(model), (not existed_before)

    def update(
        self,
        project_id: int,
        *,
        updated_by: Optional[int] = None,
        include_deleted: bool = False,
        **fields,
    ) -> Optional[Project]:
        """Apply a field patch. Only known model attributes are applied."""
        q = self.db.query(ProjectModel).filter(ProjectModel.id == project_id)
        if not include_deleted:
            q = q.filter(ProjectModel.deleted_at.is_(None))
        model = q.first()
        if not model:
            return None

        for attr, value in fields.items():
            if value is None:
                continue
            if hasattr(model, attr):
                setattr(model, attr, value)

        if updated_by is not None:
            model.updated_by = updated_by

        self.db.flush()
        return self._to_domain(model)

    def soft_delete(
        self,
        project_id: int,
        actor_id: Optional[int],
        when: Optional[datetime] = None,
    ) -> Optional[Project]:
        """Mark a project deleted. Idempotent on already-deleted rows."""
        model = (
            self.db.query(ProjectModel)
            .filter(ProjectModel.id == project_id)
            .first()
        )
        if not model:
            return None
        if model.deleted_at is None:
            model.deleted_at = when or _utcnow()
            model.deleted_by = actor_id
            self.db.flush()
        return self._to_domain(model)

    def hard_delete(self, project_id: int) -> bool:
        """Remove a row. Reserved for tests or admin cleanup — prefer soft_delete."""
        model = (
            self.db.query(ProjectModel)
            .filter(ProjectModel.id == project_id)
            .first()
        )
        if not model:
            return False
        self.db.delete(model)
        self.db.flush()
        return True

    # ------------------------------------------------------------------
    # reads — filter soft-deleted by default
    # ------------------------------------------------------------------

    def _base_query(self, include_deleted: bool = False):
        q = self.db.query(ProjectModel)
        if not include_deleted:
            q = q.filter(ProjectModel.deleted_at.is_(None))
        return q

    def get_by_id(self, project_id: int, include_deleted: bool = False) -> Optional[Project]:
        model = self._base_query(include_deleted).filter(ProjectModel.id == project_id).first()
        return self._to_domain(model) if model else None

    def get_by_identifier(self, identifier: str, include_deleted: bool = False) -> Optional[Project]:
        model = (
            self._base_query(include_deleted)
            .filter(ProjectModel.identifier == identifier)
            .first()
        )
        return self._to_domain(model) if model else None

    def list_all(self, offset: int = 0, limit: int = 20) -> Tuple[List[Project], int]:
        q = self._base_query()
        total = q.with_entities(func.count(ProjectModel.id)).scalar()
        models = q.offset(offset).limit(limit).all()
        return [self._to_domain(m) for m in models], total

    def list_active(self, offset: int = 0, limit: int = 20) -> Tuple[List[Project], int]:
        q = self._base_query().filter(ProjectModel.active == True)  # noqa: E712
        total = q.with_entities(func.count(ProjectModel.id)).scalar()
        models = q.offset(offset).limit(limit).all()
        return [self._to_domain(m) for m in models], total

    def list_public(self, offset: int = 0, limit: int = 20) -> Tuple[List[Project], int]:
        q = self._base_query().filter(ProjectModel.public == True)  # noqa: E712
        total = q.with_entities(func.count(ProjectModel.id)).scalar()
        models = q.offset(offset).limit(limit).all()
        return [self._to_domain(m) for m in models], total

    # Existence checks deliberately ignore soft-delete: identifiers should not
    # be reusable while a deleted row still occupies them.
    def exists_by_identifier(self, identifier: str) -> bool:
        return (
            self.db.query(ProjectModel.id)
            .filter(ProjectModel.identifier == identifier)
            .first()
            is not None
        )

    def exists_by_id(self, project_id: int) -> bool:
        return (
            self.db.query(ProjectModel.id)
            .filter(ProjectModel.id == project_id)
            .first()
            is not None
        )

    # ------------------------------------------------------------------
    # version helpers
    # ------------------------------------------------------------------

    def active_version_exists(self, baseline_id: int) -> bool:
        """Any version of ``baseline_id`` that is not suspended or deleted."""
        return (
            self.db.query(ProjectModel.id)
            .filter(
                and_(
                    ProjectModel.version_of == baseline_id,
                    ProjectModel.is_version == True,  # noqa: E712
                    ProjectModel.status != "suspended",
                    ProjectModel.deleted_at.is_(None),
                )
            )
            .first()
            is not None
        )

    def next_version_no(self, baseline_id: int) -> int:
        """Next sequential version number for a baseline (1-indexed)."""
        max_no = (
            self.db.query(func.max(ProjectModel.version_no))
            .filter(ProjectModel.version_of == baseline_id)
            .scalar()
        )
        return (max_no or 0) + 1

    # ------------------------------------------------------------------
    # identifier generation
    # ------------------------------------------------------------------

    _DEFAULT_IDENTIFIER_PREFIX = "prj"

    def generate_next_identifier(self, prefix: str = _DEFAULT_IDENTIFIER_PREFIX) -> str:
        """
        Allocate the next sequential identifier ``{prefix}{n:03d}`` for a new
        non-version project. Scans existing identifiers to find the highest
        integer suffix for the prefix and returns prefix + (max + 1).
        """
        rows = (
            self.db.query(ProjectModel.identifier)
            .filter(ProjectModel.identifier.like(f"{prefix}%"))
            .all()
        )
        max_n = 0
        prefix_len = len(prefix)
        for (ident,) in rows:
            tail = ident[prefix_len:]
            if tail.isdigit():
                n = int(tail)
                if n > max_n:
                    max_n = n
        return f"{prefix}{max_n + 1:03d}"
