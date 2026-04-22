"""
Human Resources models.

Models:
    - Department: Organizational unit.
    - Designation: Job title / position.
    - Employee: Individual employee record linked to department and designation.
    - Payroll: Pay-period payroll header per employee.
    - PayrollComponent: Individual earning/deduction line items on a payroll.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------

class Department(Base):
    """
    Organizational department (e.g. Engineering, Sales).

    Attributes:
        id: Primary key.
        name: Unique department name.
        description: Optional long description.
    """

    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    employees = relationship("Employee", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department(id={self.id}, name='{self.name}')>"


# ---------------------------------------------------------------------------
# Designation
# ---------------------------------------------------------------------------

class Designation(Base):
    """
    Job title / position (e.g. Senior Engineer, Sales Manager).

    Attributes:
        id: Primary key.
        title: Unique designation title.
        description: Optional long description.
    """

    __tablename__ = "designations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    employees = relationship("Employee", back_populates="designation")

    def __repr__(self) -> str:
        return f"<Designation(id={self.id}, title='{self.title}')>"


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

class Employee(Base):
    """
    Individual employee record.

    Linked to:
        - Department (many-to-one)
        - Designation (many-to-one)

    Attributes:
        employee_code: Human-readable unique code (e.g. 'EMP-001').
        first_name / last_name: Legal name.
        email: Unique email address.
        phone: Contact number.
        date_of_joining: Date the employee joined.
        salary: Monthly salary (Numeric for precision).
        is_active: Soft-delete flag.
    """

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(20), unique=True, nullable=False, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)
    date_of_joining = Column(Date, nullable=False)
    salary = Column(Numeric(15, 2), nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)

    # Foreign keys
    department_id = Column(
        Integer, ForeignKey("departments.id"), nullable=False
    )
    designation_id = Column(
        Integer, ForeignKey("designations.id"), nullable=False
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    department = relationship("Department", back_populates="employees")
    designation = relationship("Designation", back_populates="employees")
    payrolls = relationship("Payroll", back_populates="employee")

    def __repr__(self) -> str:
        return (
            f"<Employee(id={self.id}, code='{self.employee_code}', "
            f"name='{self.first_name} {self.last_name}')>"
        )


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------

class Payroll(Base):
    """
    Pay-period payroll header for a single employee.

    Attributes:
        employee_id: FK to the employee.
        pay_period_start: Start date of the pay period.
        pay_period_end: End date of the pay period.
        basic_salary: Base salary for this period.
        gross_salary: Total of all earning components.
        total_deductions: Total of all deduction components.
        net_salary: gross_salary - total_deductions.
        status: Payroll lifecycle state (e.g. draft, approved, paid).
        journal_entry_id: Optional FK to the accounting journal entry.
    """

    __tablename__ = "payrolls"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )
    pay_period_start = Column(Date, nullable=False)
    pay_period_end = Column(Date, nullable=False)

    basic_salary = Column(Numeric(15, 2), nullable=False, default=0)
    gross_salary = Column(Numeric(15, 2), nullable=False, default=0)
    total_deductions = Column(Numeric(15, 2), nullable=False, default=0)
    net_salary = Column(Numeric(15, 2), nullable=False, default=0)

    status = Column(
        String(20),
        nullable=False,
        default="draft",
        comment="draft | approved | paid | cancelled",
    )

    journal_entry_id = Column(
        Integer, ForeignKey("journal_entries.id"), nullable=True
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    employee = relationship("Employee", back_populates="payrolls")
    journal_entry = relationship("JournalEntry", back_populates="payrolls")
    components = relationship(
        "PayrollComponent", back_populates="payroll", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Payroll(id={self.id}, employee_id={self.employee_id}, "
            f"period={self.pay_period_start} to {self.pay_period_end}, "
            f"net={self.net_salary})>"
        )


# ---------------------------------------------------------------------------
# PayrollComponent
# ---------------------------------------------------------------------------

class PayrollComponent(Base):
    """
    Individual earning or deduction line on a payroll.

    Examples:
        - Basic Pay (earnings)
        - HRA (earnings)
        - Income Tax (deductions)
        - Provident Fund (deductions)

    Attributes:
        payroll_id: FK to the parent Payroll.
        component_name: Label for the component.
        component_type: 'earnings' or 'deductions'.
        amount: Monetary value (always positive; type determines sign).
    """

    __tablename__ = "payroll_components"

    id = Column(Integer, primary_key=True, index=True)
    payroll_id = Column(
        Integer, ForeignKey("payrolls.id"), nullable=False, index=True
    )
    component_name = Column(String(100), nullable=False)
    component_type = Column(
        String(20),
        nullable=False,
        comment="earnings | deductions",
    )
    amount = Column(Numeric(15, 2), nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    payroll = relationship("Payroll", back_populates="components")

    def __repr__(self) -> str:
        return (
            f"<PayrollComponent(id={self.id}, name='{self.component_name}', "
            f"type='{self.component_type}', amount={self.amount})>"
        )
