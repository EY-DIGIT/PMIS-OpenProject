"""Request schemas for the consolidated /api/v3/master/* endpoints (doc 20).

Each catalog has its own create + update body. Responses reuse the
existing per-catalog projection helpers in routes.py to keep the wire
format identical to the legacy endpoints.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Divisions
# ---------------------------------------------------------------------------

class DivisionCreateRequest(BaseModel):
    """POST /api/v3/master/divisions/create body.

    ``code`` is optional — when omitted, the service slugifies ``label``
    to derive one ('Engineering R&D' -> 'engineering_r_d'). Supply a
    code explicitly when you want a stable wire identifier independent
    of the human label.

    Built-in rows (``tmd1`` / ``tmd2`` / ``others``) cannot be created
    via this endpoint; the unique constraint on ``code`` rejects the
    insert with 409 if you try.
    """
    model_config = ConfigDict(populate_by_name=True)

    label: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(
        None, max_length=64,
        description=(
            "Optional. Lowercase alphanumeric + underscore. Derived from "
            "label via slugify when omitted."
        ),
    )
    requires_other: bool = Field(
        False, alias="requiresOther",
        description=(
            "True only on rows that prompt the FE to show a free-text "
            "follow-up input (the 'others' row uses this)."
        ),
    )


class DivisionUpdateRequest(BaseModel):
    """PATCH /api/v3/master/divisions/{code} body.

    ``code`` itself is NOT patchable — it's the wire identifier that
    every project's ``owner`` column points at. Renaming would break
    every existing reference. Only ``label`` and ``requiresOther`` are
    editable. Built-in rows reject any patch attempt with 403.
    """
    model_config = ConfigDict(populate_by_name=True)

    label: Optional[str] = Field(None, min_length=1, max_length=255)
    requires_other: Optional[bool] = Field(None, alias="requiresOther")


# ---------------------------------------------------------------------------
# Project status transitions
# ---------------------------------------------------------------------------

class ProjectStatusTransitionCreateRequest(BaseModel):
    """POST /api/v3/master/project_status_transitions/create body.

    Adds a new ``(from_status, to_status)`` edge to the project lifecycle.
    ``from_status=None`` represents the initial-status seed (state the
    system accepts on a fresh create).
    """
    model_config = ConfigDict(populate_by_name=True)

    from_status: Optional[str] = Field(
        None, alias="fromStatus", max_length=50,
        description="Source status; null marks an initial-status seed row.",
    )
    to_status: str = Field(..., alias="toStatus", min_length=1, max_length=50)
    requires_admin: bool = Field(False, alias="requiresAdmin")
    version_only: bool = Field(False, alias="versionOnly")
    description: Optional[str] = Field(None, max_length=500)


class ProjectStatusTransitionUpdateRequest(BaseModel):
    """PATCH /api/v3/master/project_status_transitions/{id} body.

    Only the policy fields (requiresAdmin, versionOnly, description) are
    editable. The (from_status, to_status) tuple is the row's identity —
    patching it would amount to deleting one edge and creating another.
    Use DELETE + POST for that.
    """
    model_config = ConfigDict(populate_by_name=True)

    requires_admin: Optional[bool] = Field(None, alias="requiresAdmin")
    version_only: Optional[bool] = Field(None, alias="versionOnly")
    description: Optional[str] = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# Resource types
# ---------------------------------------------------------------------------

class ResourceTypeCreateRequest(BaseModel):
    """POST /api/v3/master/resource_types/create body."""
    model_config = ConfigDict(populate_by_name=True)
    code: str = Field(
        ..., min_length=1, max_length=50,
        description="Canonical lowercase code; unique across the catalog.",
    )
    name: str = Field(..., min_length=1, max_length=255)
    active: bool = Field(True)


class ResourceTypeUpdateRequest(BaseModel):
    """PATCH /api/v3/master/resource_types/{id} body.

    Only ``name`` is patchable. ``code`` is NOT updatable — every
    activity_resource row in the system points at the row's id, but the
    picker dropdown is keyed by code; renaming a code mid-flight would
    break consistency for resource activities created with the old
    code. Renames go through deactivate-and-create-new.
    """
    model_config = ConfigDict(populate_by_name=True)
    name: Optional[str] = Field(None, min_length=1, max_length=255)


# ---------------------------------------------------------------------------
# Vendors — schemas reuse the existing vendor-create/update bodies via
# delegation. Nothing new lives here for vendors. See routes.py.
# ---------------------------------------------------------------------------
