"""Vendor request/response schemas."""
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class VendorCreateRequest(BaseModel):
    """Body for POST /vendors/create.

    Contact fields (`email`, `contactPerson`, `phoneNumber`) are
    optional. Email goes through Pydantic's loose RFC 5322 check; phone
    is a free-form string (international formats vary too much for a
    one-size regex).
    """
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: bool = Field(True)
    email: Optional[EmailStr] = Field(
        None, description="Vendor primary contact email.",
    )
    contactPerson: Optional[str] = Field(
        None, alias="contact_person", max_length=255,
        description="Person at the vendor org to reach out to.",
    )
    phoneNumber: Optional[str] = Field(
        None, alias="phone_number", max_length=50,
        description=(
            "Free-form phone number. No regex check — international "
            "formats vary; FE may apply its own client-side mask."
        ),
    )


class VendorUpdateRequest(BaseModel):
    """Body for PATCH /vendors/{id}. Same fields as create, all optional."""
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: Optional[bool] = None
    email: Optional[EmailStr] = None
    contactPerson: Optional[str] = Field(
        None, alias="contact_person", max_length=255,
    )
    phoneNumber: Optional[str] = Field(
        None, alias="phone_number", max_length=50,
    )
