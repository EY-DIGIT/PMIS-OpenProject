"""Request schemas for the consolidated /api/v3/master/* endpoints (doc 20).

Each catalog has its own create + update body. Responses reuse the
existing per-catalog projection helpers in routes.py to keep the wire
format identical to the legacy endpoints.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Divisions
# ---------------------------------------------------------------------------

class DivisionCreateRequest(BaseModel):
    """POST /api/v3/master/divisions/create body.

    ``code`` is optional — when omitted, the service slugifies ``label``
    to derive one ('Engineering R&D' -> 'engineering_r_d'). Supply a
    code explicitly when you want a stable wire identifier independent
    of the human label.

    ``email`` / ``phoneNumber`` are optional contact details for the
    division — typically a shared mailbox alias and a hotline. Mirrors
    the same fields on vendors (doc 18). Both default to None and the
    seeded built-in rows (``tmd1`` / ``tmd2`` / ``others``) leave them
    NULL on first boot.

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
    email: Optional[EmailStr] = Field(
        None,
        description=(
            "Optional contact email for the division (e.g. a shared "
            "mailbox alias). RFC-5322-validated. Empty / null leaves the "
            "column NULL."
        ),
    )
    phoneNumber: Optional[str] = Field(
        None,
        alias="phone_number",
        max_length=50,
        description=(
            "Optional contact phone for the division. Free-form (no "
            "regex) — same convention as vendors.phone_number."
        ),
    )


class DivisionUpdateRequest(BaseModel):
    """PATCH /api/v3/master/divisions/{code} body.

    ``code`` itself is NOT patchable — it's the wire identifier that
    every project's ``owner`` column points at. Renaming would break
    every existing reference. Only ``label`` / ``requiresOther`` /
    ``email`` / ``phoneNumber`` are editable. Built-in rows accept patches
    only on ``email`` + ``phoneNumber`` (admins can still add contact
    details to the seeded rows); the route layer rejects label /
    requiresOther changes on built-ins with 403.

    Pass an empty string for ``email`` or ``phoneNumber`` to explicitly
    clear a stored contact (the repo normalizes empty → NULL). Omit the
    field entirely to leave the existing value alone — standard PATCH
    semantics.
    """
    model_config = ConfigDict(populate_by_name=True)

    label: Optional[str] = Field(None, min_length=1, max_length=255)
    requires_other: Optional[bool] = Field(None, alias="requiresOther")
    email: Optional[str] = Field(
        None,
        description=(
            "Optional contact email. RFC-5322-validated when non-empty; "
            "empty string clears the stored value."
        ),
    )
    phoneNumber: Optional[str] = Field(
        None,
        alias="phone_number",
        max_length=50,
        description=(
            "Optional contact phone. Empty string clears the stored value."
        ),
    )

    @field_validator("email")
    @classmethod
    def _email_loose(cls, v: Optional[str]) -> Optional[str]:
        # On PATCH we accept empty string (sentinel for "clear"). When
        # non-empty we still want RFC-5322-ish validation, but we can't
        # apply EmailStr directly because it rejects empty. Apply the
        # check manually here.
        if v is None or v == "":
            return v
        # Defer to email-validator via Pydantic's EmailStr internals.
        from pydantic import TypeAdapter
        return TypeAdapter(EmailStr).validate_python(v)


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
    description: Optional[str] = Field(None, max_length=500)


class ProjectStatusTransitionUpdateRequest(BaseModel):
    """PATCH /api/v3/master/project_status_transitions/{id} body.

    Only the policy fields (requiresAdmin, description) are editable.
    The (from_status, to_status) tuple is the row's identity — patching
    it would amount to deleting one edge and creating another. Use
    DELETE + POST for that.
    """
    model_config = ConfigDict(populate_by_name=True)

    requires_admin: Optional[bool] = Field(None, alias="requiresAdmin")
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
