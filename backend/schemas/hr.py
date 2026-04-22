"""
Pydantic schemas for HR module: departments, designations, employees, and payroll.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------

class DepartmentCreate(BaseModel):
    """Schema for creating a new department."""
    name: str
    description: Optional[str] = None


class DepartmentResponse(BaseModel):
    """Schema returned when reading a department."""
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Designation
# ---------------------------------------------------------------------------

class DesignationCreate(BaseModel):
    """Schema for creating a new designation."""
    title: str
    description: Optional[str] = None


class DesignationResponse(BaseModel):
    """Schema returned when reading a designation."""
    id: int
    title: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

class EmployeeCreate(BaseModel):
    """Schema for creating a new employee."""
    employee_code: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    department_id: int
    designation_id: int
    date_of_joining: date
    salary: Decimal


class EmployeeResponse(BaseModel):
    """Schema returned when reading an employee record."""
    id: int
    employee_code: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    department_id: int
    designation_id: int
    date_of_joining: date
    salary: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Payroll Component (sub-schema used inside PayrollProcess)
# ---------------------------------------------------------------------------

class PayrollComponentSchema(BaseModel):
    """A single earning or deduction line item."""
    component_name: str
    component_type: str  # "earnings" or "deductions"
    amount: Decimal


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------

class PayrollProcess(BaseModel):
    """Schema for processing (creating) a payroll run for an employee."""
    employee_id: int
    pay_period_start: date
    pay_period_end: date
    components: List[PayrollComponentSchema]


class PayrollComponentResponse(BaseModel):
    """Schema returned for individual payroll component lines."""
    id: int
    payroll_id: int
    component_name: str
    component_type: str
    amount: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollResponse(BaseModel):
    """Schema returned when reading a payroll record."""
    id: int
    employee_id: int
    pay_period_start: date
    pay_period_end: date
    basic_salary: Decimal
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    status: str
    journal_entry_id: Optional[int] = None
    components: List[PayrollComponentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
