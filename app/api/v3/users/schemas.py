"""
User API schemas (request/response models).
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _split_full_name(full_name: Optional[str]):
    """Split ``"first last…"`` into ``(first, last_or_None)`` on the first
    space. Returns ``(None, None)`` for falsy input. Used by both create
    and update schemas so the FE can send a single ``fullName`` field
    and the BE backfills first_name / last_name from it. Mirrors the
    join rule used by the response formatter (`format_user_response`).
    """
    if not full_name:
        return None, None
    parts = full_name.strip().split(" ", 1)
    first = parts[0] or None
    last = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return first, last

from ....domain.resource_types.resource_type import (
    DIVISION_CHOICES,
    DIVISION_OTHERS,
)
from ....shared.phone import validate_phone_number


# Allowed values for the user's status field. "inactive" is what soft-deleted
# users carry; admins can also set it manually via the Edit User flow.
_USER_STATUS_CHOICES = ("active", "inactive", "locked", "registered")


class UserCreateRequest(BaseModel):
    """Request schema for creating a user.

    Per product spec, every new user must have:
      - a vendor (single, FK to vendors)
      - a division (one of DIVISION_CHOICES; 'others' requires divisionOther)
      - at least one project mapping (project_ids)

    The bootstrap admin path (init_db seed) bypasses this validation.
    """
    model_config = ConfigDict(populate_by_name=True)

    login: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    # Canonical name input. Split on the first space server-side into
    # first_name / last_name for DB storage; the response formatter
    # joins them back to fullName on the way out. firstName / lastName
    # are exposed as read-only @property below so existing service
    # code that reads ``data.firstName`` / ``data.lastName`` keeps
    # working unchanged.
    fullName: Optional[str] = Field(
        None, alias="full_name", max_length=510,
        description=(
            "User's full name. Split on the first space into "
            "first_name / last_name for storage — e.g. 'Saikat Aich "
            "gupta' becomes first='Saikat', last='Aich gupta'. May be "
            "omitted; in that case the DB rows are stored with NULL "
            "first/last and the response falls back to ``login`` for "
            "the fullName key."
        ),
    )
    admin: bool = False

    vendorId: str = Field(
        ..., alias="vendor_id",
        description=(
            "Vendor identifier. Accepts EITHER the vendor's UUID OR its "
            "human-readable ``vendorCode`` (e.g. ``VN-ACME-260502143015`` "
            "— see doc 25). The dispatcher auto-detects via the ``VN-`` "
            "prefix; the persisted FK is always the canonical UUID."
        ),
    )
    division: str = Field(
        ...,
        description=f"One of: {', '.join(DIVISION_CHOICES)}.",
    )
    divisionOther: Optional[str] = Field(
        None, alias="division_other", max_length=255,
        description=(
            f"Required (non-empty) when division == '{DIVISION_OTHERS}'. "
            "Must be omitted / null for any other division."
        ),
    )
    projectIds: List[str] = Field(
        ...,
        alias="project_ids",
        min_length=1,
        description=(
            "List of project UUIDs to map this user to. At least one is "
            "required. Each id must reference a non-deleted project."
        ),
    )
    phoneNumber: str = Field(
        ...,
        alias="phone_number",
        min_length=1,
        max_length=50,
        description=(
            "User's phone / mobile number. Required on create. Accepts "
            "an optional leading ``+`` country-code prefix; ``[7..15]`` "
            "digits total after stripping spaces / hyphens / parens / "
            "dots. Mirrors the vendor schema's ``phoneNumber`` field."
        ),
    )

    @field_validator("phoneNumber", mode="before")
    @classmethod
    def _validate_phone(cls, v):
        return validate_phone_number(v)

    @property
    def firstName(self) -> Optional[str]:
        first, _ = _split_full_name(self.fullName)
        return first

    @property
    def lastName(self) -> Optional[str]:
        _, last = _split_full_name(self.fullName)
        return last


class UserUpdateRequest(BaseModel):
    """Request schema for updating a user."""
    model_config = ConfigDict(populate_by_name=True)

    email: Optional[EmailStr] = None
    # Canonical name input on PATCH. None / omitted leaves the existing
    # first / last unchanged; a value is split on the first space and
    # replaces BOTH fields atomically. firstName / lastName are exposed
    # as read-only @property below for the service layer.
    fullName: Optional[str] = Field(
        None, alias="full_name", max_length=510,
        description=(
            "User's full name. Omit to leave the name unchanged. "
            "When supplied, the value is split on the first space — "
            "first token becomes first_name, the remainder becomes "
            "last_name. Both columns are written; sending a single "
            "token clears last_name."
        ),
    )
    admin: Optional[bool] = None
    status: Optional[str] = None
    vendorId: Optional[str] = Field(
        None, alias="vendor_id",
        description=(
            "Vendor identifier. Accepts UUID or ``VN-...`` code (doc 25)."
        ),
    )
    division: Optional[str] = None
    divisionOther: Optional[str] = Field(
        None, alias="division_other", max_length=255,
    )
    phoneNumber: Optional[str] = Field(
        None,
        alias="phone_number",
        max_length=50,
        description=(
            "Optional on PATCH. When supplied, replaces the user's stored "
            "phone number; omit / null to leave unchanged. Mirrors the "
            "vendor PATCH schema."
        ),
    )

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v is not None and v not in _USER_STATUS_CHOICES:
            raise ValueError(
                f"Status must be one of: {', '.join(_USER_STATUS_CHOICES)}."
            )
        return v

    @field_validator("phoneNumber", mode="before")
    @classmethod
    def _validate_phone(cls, v):
        # Optional on PATCH — None / unset means "no change".
        if v is None:
            return v
        return validate_phone_number(v)

    @property
    def firstName(self) -> Optional[str]:
        # When fullName is omitted, return None so the update service
        # treats the name as "no change". Don't fall back to login on
        # update — that's only the response-side fallback.
        if self.fullName is None:
            return None
        first, _ = _split_full_name(self.fullName)
        return first

    @property
    def lastName(self) -> Optional[str]:
        if self.fullName is None:
            return None
        _, last = _split_full_name(self.fullName)
        return last


class UserPasswordUpdateRequest(BaseModel):
    """Request schema for updating user password."""
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    """Request schema for user login."""
    login: str
    password: str


class LoginResponse(BaseModel):
    """Response schema for user login."""
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


class UserListQuery(BaseModel):
    """Query parameters for listing users."""
    offset: int = Field(1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(20, ge=1, le=200, description="Number of items per page (max 200).")
    status: Optional[str] = Field(None, description="Filter by status")
    includeDeleted: bool = Field(
        False, alias="include_deleted",
        description="Admin-only: also surface soft-deleted users.",
    )


class IntrospectRequest(BaseModel):
    """Request schema for token introspection.

    RFC 7662-style: pure read-only metadata lookup, never rotates tokens.
    Provide either or both fields. Both → response shape becomes
    ``{access: {...}, refresh: {...}}``.
    """

    access_token: Optional[str] = None
    refresh_token: Optional[str] = None


class RefreshRequest(BaseModel):
    """Request schema for POST /users/refresh.

    Takes only a refresh token. Successful rotation returns a new
    access + refresh pair plus expiry metadata so the FE can schedule
    the next preemptive refresh without decoding the JWT.
    """

    refresh_token: str


# ---------------------------------------------------------------------------
# Doc 33 change 3 — 2FA + forgot-password schemas
# ---------------------------------------------------------------------------

class OtpSendRequest(BaseModel):
    """POST /users/login/send-otp body."""

    ephemeral_token: str = Field(..., min_length=10)
    channel: str = Field(..., description="email or sms")


class OtpVerifyRequest(BaseModel):
    """POST /users/login/verify-otp body."""

    ephemeral_token: str = Field(..., min_length=10)
    code: str = Field(..., min_length=4, max_length=12)


class ForgotPasswordRequest(BaseModel):
    """POST /users/forgot-password body. Anti-enumeration: this endpoint
    always returns 200, whether the user exists or not."""

    login_or_email: str = Field(..., min_length=1, max_length=255)
    channel: str = Field(..., description="email or sms")


class ResetPasswordRequest(BaseModel):
    """POST /users/reset-password body. Accepts either a URL-safe token
    (email channel) or a numeric OTP (sms channel) — the server hashes
    and matches whichever form was sent."""

    token_or_code: str = Field(..., min_length=4, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=255)
