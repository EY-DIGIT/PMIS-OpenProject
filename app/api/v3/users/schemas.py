"""
User API schemas (request/response models).
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserCreateRequest(BaseModel):
    """Request schema for creating a user."""

    login: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    firstName: Optional[str] = Field(None, max_length=255)
    lastName: Optional[str] = Field(None, max_length=255)
    admin: bool = False


class UserUpdateRequest(BaseModel):
    """Request schema for updating a user."""

    email: Optional[EmailStr] = None
    firstName: Optional[str] = Field(None, max_length=255)
    lastName: Optional[str] = Field(None, max_length=255)
    admin: Optional[bool] = None
    status: Optional[str] = None


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
    # Backwards-compatible addition: include refresh token when present
    refresh_token: Optional[str] = None


class UserListQuery(BaseModel):
    """Query parameters for listing users."""

    offset: int = Field(1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(20, ge=1, le=100, description="Number of items per page")
    status: Optional[str] = Field(None, description="Filter by status")


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
