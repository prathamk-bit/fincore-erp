"""
Pydantic schemas for User authentication and registration.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Valid roles for the ERP system
# ---------------------------------------------------------------------------

VALID_ROLES = ("admin", "accountant", "hr_manager", "inventory_manager")
RoleType = Literal["admin", "accountant", "hr_manager", "inventory_manager"]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """Schema for creating a new user account."""
    username: str
    email: str
    password: str
    role: RoleType = "accountant"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")
        return v


class UserUpdate(BaseModel):
    """Schema for updating an existing user account."""
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[RoleType] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")
        return v


class LoginRequest(BaseModel):
    """Schema for the login form payload."""
    username: str
    password: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """Schema returned when reading a user record."""
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Schema for the JWT access-token response."""
    access_token: str
    token_type: str = "bearer"
