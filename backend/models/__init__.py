"""
ERP System database models package.

Imports all models so that ``from backend.models import *`` (or simply
importing this package) registers every table with SQLAlchemy's Base
metadata.  This is required for ``Base.metadata.create_all()`` to
discover all tables.
"""

from .database import Base, SessionLocal, engine, get_db

# User / Auth
from .user import User

# Human Resources
from .hr import (
    Department,
    Designation,
    Employee,
    Payroll,
    PayrollComponent,
)

# Accounting
from .accounting import (
    Account,
    JournalEntry,
    JournalEntryLine,
)

# Finance
from .finance import FinancialTransaction

# Inventory
from .inventory import (
    ItemCategory,
    Item,
    StockLedger,
    Warehouse,
)

# Procurement
from .procurement import (
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)

__all__ = [
    # Database
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
    # User
    "User",
    # HR
    "Department",
    "Designation",
    "Employee",
    "Payroll",
    "PayrollComponent",
    # Accounting
    "Account",
    "JournalEntry",
    "JournalEntryLine",
    # Finance
    "FinancialTransaction",
    # Inventory
    "ItemCategory",
    "Item",
    "StockLedger",
    "Warehouse",
    # Procurement
    "PurchaseOrder",
    "PurchaseOrderItem",
    "Supplier",
]
