"""
API routes for the HR module.

Endpoints:
    POST /api/hr/departments                - Create a department.
    GET  /api/hr/departments                - List all departments.
    POST /api/hr/designations               - Create a designation.
    GET  /api/hr/designations               - List all designations.
    POST /api/hr/employees                  - Create an employee.
    GET  /api/hr/employees                  - List all employees.
    GET  /api/hr/employees/{id}             - Get a single employee.
    PUT  /api/hr/employees/{id}             - Update an employee.
    POST /api/hr/payrolls                   - Create a payroll (draft).
    GET  /api/hr/payrolls                   - List all payroll records.
    GET  /api/hr/payrolls/{id}              - Get a single payroll.
    POST /api/hr/payrolls/{id}/process      - Process a draft payroll (creates expense JE).
    POST /api/hr/payrolls/{id}/pay          - Pay a processed payroll (creates payment JE).
    POST /api/hr/payrolls/{id}/cancel       - Cancel a payroll.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.auth.auth import role_required
from backend.models.database import get_db
from backend.models.user import User
from backend.schemas.hr import (
    DepartmentCreate,
    DepartmentResponse,
    DesignationCreate,
    DesignationResponse,
    EmployeeCreate,
    EmployeeResponse,
    PayrollProcess,
    PayrollResponse,
)
from backend.services.hr_service import (
    cancel_payroll,
    create_department,
    create_designation,
    create_employee,
    create_payroll,
    get_departments,
    get_designations,
    get_employee,
    get_employees,
    get_payroll,
    get_payrolls,
    pay_payroll,
    process_payroll,
    update_employee,
)

router = APIRouter(prefix="/api/hr", tags=["HR"])

ALLOWED_ROLES = ["admin", "hr_manager"]


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department_route(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """Create a new department."""
    return create_department(db, data)


@router.get("/departments", response_model=List[DepartmentResponse])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """List all departments."""
    return get_departments(db)


# ---------------------------------------------------------------------------
# Designations
# ---------------------------------------------------------------------------

@router.post("/designations", response_model=DesignationResponse, status_code=status.HTTP_201_CREATED)
def create_designation_route(
    data: DesignationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """Create a new designation."""
    return create_designation(db, data)


@router.get("/designations", response_model=List[DesignationResponse])
def list_designations(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """List all designations."""
    return get_designations(db)


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee_route(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """Create a new employee record."""
    return create_employee(db, data)


@router.get("/employees", response_model=List[EmployeeResponse])
def list_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """List all employees."""
    return get_employees(db)


@router.get("/employees/{id}", response_model=EmployeeResponse)
def get_employee_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """Get a single employee by ID."""
    return get_employee(db, id)


@router.put("/employees/{id}", response_model=EmployeeResponse)
def update_employee_route(
    id: int,
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """Update an existing employee record."""
    return update_employee(db, id, data)


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------

@router.post("/payrolls", response_model=PayrollResponse, status_code=status.HTTP_201_CREATED)
def create_payroll_route(
    data: PayrollProcess,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """
    Create a new payroll record as DRAFT.

    Draft payrolls do not create journal entries.
    Use POST /payrolls/{id}/process to process the payroll.
    """
    return create_payroll(db, data)


# Keep legacy endpoint for backwards compatibility
@router.post("/payroll/process", response_model=PayrollResponse, status_code=status.HTTP_201_CREATED)
def process_payroll_legacy_route(
    data: PayrollProcess,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """
    [DEPRECATED] Create a payroll as draft.

    Use POST /payrolls to create, then POST /payrolls/{id}/process to process.
    """
    return create_payroll(db, data)


@router.get("/payrolls", response_model=List[PayrollResponse])
def list_payrolls(
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    status: Optional[str] = Query(None, description="Filter by status: draft, processed, paid, cancelled"),
    period_start: Optional[date] = Query(None, description="Filter pay periods starting from this date"),
    period_end: Optional[date] = Query(None, description="Filter pay periods ending by this date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """List payroll records with optional filters."""
    return get_payrolls(db, employee_id, status, period_start, period_end)


@router.get("/payrolls/{id}", response_model=PayrollResponse)
def get_payroll_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """Get a single payroll record by ID."""
    return get_payroll(db, id)


@router.post("/payrolls/{id}/process", response_model=PayrollResponse)
def process_payroll_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """
    Process a draft payroll.

    Transitions the payroll from 'draft' to 'processed' status and
    creates a journal entry:
        - Debit: Salary Expense
        - Credit: Salary Payable
    """
    return process_payroll(db, id)


@router.post("/payrolls/{id}/pay", response_model=PayrollResponse)
def pay_payroll_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """
    Pay a processed payroll.

    Transitions the payroll from 'processed' to 'paid' status and
    creates a payment journal entry:
        - Debit: Salary Payable
        - Credit: Cash/Bank
    """
    return pay_payroll(db, id)


@router.post("/payrolls/{id}/cancel", response_model=PayrollResponse)
def cancel_payroll_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "hr_manager"])),
):
    """
    Cancel a payroll.

    Only 'draft' or 'processed' payrolls can be cancelled.
    """
    return cancel_payroll(db, id)
