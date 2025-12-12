"""
Pydantic schemas for API request/response models.

Following OpenProject API v3 HAL+JSON format.
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserStatusEnum(str, Enum):
    """User status values"""
    active = "active"
    registered = "registered"
    invited = "invited"
    locked = "locked"
    deleted = "deleted"


# Base schemas
class HALLink(BaseModel):
    """HAL link object"""
    href: str
    title: Optional[str] = None


class HALLinks(BaseModel):
    """HAL _links collection"""
    self: HALLink
    model_config = ConfigDict(extra='allow')


# User schemas
class UserPreferenceSchema(BaseModel):
    """User preference schema"""
    timezone: str = "UTC"
    hide_mail: bool = True
    comments_sorting: str = "asc"
    warn_on_leaving_unsaved: bool = True
    theme: str = "default"
    notification_settings: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    """Base user schema"""
    login: str = Field(..., min_length=1, max_length=256)
    firstName: Optional[str] = Field(None, max_length=256)
    lastName: Optional[str] = Field(None, max_length=256)
    email: EmailStr
    language: str = "en"
    admin: bool = False
    status: UserStatusEnum = UserStatusEnum.active


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8)
    preferences: Optional[UserPreferenceSchema] = None


class UserUpdate(BaseModel):
    """
    User update schema (all fields optional).

    Note: The 'name' field is read-only and automatically computed from
    'firstName' and 'lastName'. Update those fields to change the name.
    """
    login: Optional[str] = Field(None, min_length=1, max_length=256)
    firstName: Optional[str] = Field(None, max_length=256, description="First name (updates the 'name' field)")
    lastName: Optional[str] = Field(None, max_length=256, description="Last name (updates the 'name' field)")
    email: Optional[EmailStr] = None
    language: Optional[str] = None
    admin: Optional[bool] = None
    status: Optional[UserStatusEnum] = None
    preferences: Optional[UserPreferenceSchema] = None


class UserResponse(BaseModel):
    """User response schema (HAL+JSON format)"""
    _type: str = "User"
    id: int
    login: str
    firstName: Optional[str]
    lastName: Optional[str]
    name: str
    email: str
    admin: bool
    status: UserStatusEnum
    language: str
    identityUrl: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    _links: HALLinks

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserCollectionResponse(BaseModel):
    """User collection response (HAL+JSON format)"""
    type_: str = Field(default="Collection", serialization_alias="_type")
    total: int
    count: int
    pageSize: int = Field(alias="pageSize")
    offset: int
    embedded: Dict[str, List[UserResponse]] = Field(serialization_alias="_embedded")
    links: HALLinks = Field(serialization_alias="_links")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        # Allow serialization with aliases
        by_alias=True
    )


# Authentication schemas
class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with JWT tokens"""
    user: UserResponse
    token: Optional[str] = None  # Deprecated, use accessToken
    sessionId: Optional[str] = None
    accessToken: Optional[str] = None  # JWT access token
    refreshToken: Optional[str] = None  # JWT refresh token
    tokenType: Optional[str] = "bearer"  # Token type
    expiresIn: Optional[int] = None  # Token expiration in seconds


class PasswordChangeRequest(BaseModel):
    """Password change request"""
    currentPassword: str
    newPassword: str = Field(..., min_length=8)
    newPasswordConfirmation: str


class RegistrationRequest(UserCreate):
    """User registration request"""
    pass


# Schema for validation
class UserSchemaResponse(BaseModel):
    """User schema definition response"""
    _type: str = "Schema"
    _dependencies: List[Dict[str, Any]] = []
    login: Dict[str, Any]
    firstName: Dict[str, Any]
    lastName: Dict[str, Any]
    email: Dict[str, Any]
    admin: Dict[str, Any]
    status: Dict[str, Any]
    language: Dict[str, Any]
    password: Dict[str, Any]
    _links: HALLinks


# Error response
class ErrorResponse(BaseModel):
    """Error response schema"""
    _type: str = "Error"
    errorIdentifier: str
    message: str
    details: Optional[Dict[str, List[str]]] = None


# Lock/Unlock schemas
class LockResponse(BaseModel):
    """Lock user response"""
    _type: str = "User"
    message: str = "User locked successfully"


class UnlockResponse(BaseModel):
    """Unlock user response"""
    _type: str = "User"
    message: str = "User unlocked successfully"
