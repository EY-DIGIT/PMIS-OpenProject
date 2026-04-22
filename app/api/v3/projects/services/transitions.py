"""
Project status lifecycle + editable-field whitelist.

Single source of truth for:
  - the allowed status vocabulary
  - which fields are editable in each project state
  - which (from, to) status transitions are legal, and by whom
"""
from typing import Optional, Set, Tuple
from sqlalchemy.orm import Session

from .....core.errors import ValidationError
from .....domain.projects.project import Project
from .....infrastructure.db.repositories.project_repository import ProjectRepository


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

STATUS_NEW = "new"
STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_CLOSED = "closed"
STATUS_SUSPENDED = "suspended"

PROJECT_STATUS_CHOICES: Tuple[str, ...] = (
    STATUS_NEW,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    STATUS_CLOSED,
    STATUS_SUSPENDED,
)

CATEGORY_MSAP = "MSAP"
CATEGORY_MSIP = "MSIP"
CATEGORY_BSP = "BSP"
# Free-text category. When used, ``category_other`` on the project row MUST
# be a non-empty string (max 255 chars) — the create/upsert services enforce.
CATEGORY_OTHERS = "others"
PROJECT_CATEGORY_CHOICES: Tuple[str, ...] = (
    CATEGORY_MSAP,
    CATEGORY_MSIP,
    CATEGORY_BSP,
    CATEGORY_OTHERS,
)

# "Active" version = not suspended and not soft-deleted. Used for the
# one-active-version-per-baseline invariant.
ACTIVE_VERSION_STATUSES: Set[str] = {
    STATUS_NEW,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    STATUS_CLOSED,
}


# ---------------------------------------------------------------------------
# Editable field whitelist
# ---------------------------------------------------------------------------

# Snake_case names matching ProjectModel columns / ProjectUpdateRequest fields.
EDITABLE_FIELDS_BASELINE_UNPUBLISHED: Set[str] = {
    "name",
    "description",
    "owner",
    "start_date",
    "end_date",
    "public",
    "active",
    "status_explanation",
}

# A published baseline is immutable by edit. Transitions (close, delete)
# happen through dedicated endpoints, not through PATCH.
EDITABLE_FIELDS_BASELINE_PUBLISHED: Set[str] = set()

# Versions allow editing a small subset; published versions remain editable
# on these fields (owner / public / actual_end_date) per the mockup.
EDITABLE_FIELDS_VERSION: Set[str] = {
    "owner",
    "public",
    "actual_end_date",
    "status_explanation",
}


def editable_fields_for(project: Project) -> Set[str]:
    """Return the set of field names a PATCH may modify for this project."""
    if project.is_version:
        return EDITABLE_FIELDS_VERSION
    if (project.status or "").lower() == STATUS_PUBLISHED:
        return EDITABLE_FIELDS_BASELINE_PUBLISHED
    return EDITABLE_FIELDS_BASELINE_UNPUBLISHED


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
#
# Legal (from_status, to_status) edges. Admin-only edges are tagged in
# ``ADMIN_ONLY_TRANSITIONS``. Version-only or baseline-only guards are applied
# separately, because the edge set is the same for both.

_LEGAL_TRANSITIONS: Set[Tuple[str, str]] = {
    (STATUS_NEW, STATUS_DRAFT),
    (STATUS_DRAFT, STATUS_NEW),          # revert if milestones removed (allowed)
    (STATUS_NEW, STATUS_PUBLISHED),      # admin
    (STATUS_DRAFT, STATUS_PUBLISHED),    # admin
    (STATUS_NEW, STATUS_CLOSED),         # admin
    (STATUS_DRAFT, STATUS_CLOSED),       # admin
    (STATUS_PUBLISHED, STATUS_CLOSED),   # admin
    # Suspend is available for versions only (enforced by guard below).
    (STATUS_NEW, STATUS_SUSPENDED),
    (STATUS_DRAFT, STATUS_SUSPENDED),
    (STATUS_PUBLISHED, STATUS_SUSPENDED),
}

ADMIN_ONLY_TRANSITIONS: Set[Tuple[str, str]] = {
    (STATUS_NEW, STATUS_PUBLISHED),
    (STATUS_DRAFT, STATUS_PUBLISHED),
    (STATUS_NEW, STATUS_CLOSED),
    (STATUS_DRAFT, STATUS_CLOSED),
    (STATUS_PUBLISHED, STATUS_CLOSED),
}

VERSION_ONLY_TRANSITIONS: Set[Tuple[str, str]] = {
    (STATUS_NEW, STATUS_SUSPENDED),
    (STATUS_DRAFT, STATUS_SUSPENDED),
    (STATUS_PUBLISHED, STATUS_SUSPENDED),
}


def assert_transition_allowed(
    *,
    from_status: str,
    to_status: str,
    actor_is_admin: bool,
    project_is_version: bool,
) -> None:
    """Raise ValidationError if the requested status transition is illegal."""
    from_status = (from_status or "").lower()
    to_status = (to_status or "").lower()

    if from_status == to_status:
        # No-op transitions are silently accepted by callers that pre-check;
        # if this helper is reached, treat as invalid to surface the mistake.
        raise ValidationError(
            "Status is already set to that value",
            details={
                "errorIdentifier": "invalid_transition",
                "from": from_status,
                "to": to_status,
            },
        )

    edge = (from_status, to_status)
    if edge not in _LEGAL_TRANSITIONS:
        raise ValidationError(
            f"Illegal status transition: {from_status} -> {to_status}",
            details={
                "errorIdentifier": "invalid_transition",
                "from": from_status,
                "to": to_status,
            },
        )

    if edge in ADMIN_ONLY_TRANSITIONS and not actor_is_admin:
        raise ValidationError(
            f"Transition {from_status} -> {to_status} requires admin privileges",
            details={
                "errorIdentifier": "invalid_transition",
                "from": from_status,
                "to": to_status,
                "reason": "admin_required",
            },
        )

    if edge in VERSION_ONLY_TRANSITIONS and not project_is_version:
        raise ValidationError(
            f"Transition {from_status} -> {to_status} is only allowed on version projects",
            details={
                "errorIdentifier": "invalid_transition",
                "from": from_status,
                "to": to_status,
                "reason": "version_only",
            },
        )


# ---------------------------------------------------------------------------
# Cross-module helper: new -> draft on first-milestone save
# ---------------------------------------------------------------------------

def transition_to_draft_if_new(
    db: Session,
    project_id: str,
    actor_id: Optional[int],
) -> Optional[Project]:
    """
    Flip status from 'new' to 'draft' when the M/A/T/S contributor's save
    finalizes (i.e., at least one milestone has been added and the user
    clicks Save Project). No-op if project is not in 'new'.

    Does NOT commit — caller (the M/A/T/S save endpoint) owns the transaction.
    Returns the updated Project when a transition happened, else None.
    """
    repo = ProjectRepository(db)
    project = repo.get_by_id(project_id)
    if project is None:
        return None
    if (project.status or "").lower() != STATUS_NEW:
        return None

    updated = repo.update(
        project_id=project_id,
        status=STATUS_DRAFT,
        updated_by=actor_id,
    )
    # Audit is recorded by the caller (they know the triggering action).
    return updated
