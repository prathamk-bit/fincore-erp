"""
User model with Role-Based Access Control (RBAC).

Roles (stored as plain string):
    - admin: Full system access
    - accountant: Accounting and finance modules
    - hr_manager: HR and payroll modules
    - inventory_manager: Inventory and procurement modules
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    func,
)

from .database import Base


class User(Base):
    """
    Application user with role-based access control.

    Attributes:
        id: Primary key.
        username: Unique login name.
        email: Unique email address.
        hashed_password: Bcrypt (or similar) hashed password.
        role: One of 'admin', 'accountant', 'hr_manager', 'inventory_manager'.
        is_active: Soft-delete / deactivation flag.
        created_at: Row creation timestamp (server default).
        updated_at: Row last-update timestamp (auto-updated).
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        String(20),
        nullable=False,
        default="accountant",
        comment="admin | accountant | hr_manager | inventory_manager",
    )
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
