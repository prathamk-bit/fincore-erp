"""
HR service layer.

Provides business-logic functions for departments, designations, employees,
and payroll processing with proper workflow state transitions.

Payroll Workflow:
    Draft -> Processed -> Paid

    - Draft: Initial state, can be edited
    - Processed: Journal entry created (Debit: Salary Expense, Credit: Salary Payable)
    - Paid: Payment entry created (Debit: Salary Payable, Credit: Cash)

This module integrates with the central accounting service to ensure all
payroll transactions are properly recorded in the general ledger.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.models.hr import (
    Department,
    Designation,
    Employee,
    Payroll,
    PayrollComponent,
)
from backend.schemas.hr import (
    DepartmentCreate,
    DesignationCreate,
    EmployeeCreate,
    PayrollProcess,
)
from backend.services.accounting_service import (
    create_journal_entry_from_module,
    JournalLine,
)


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------

def create_department(db: Session, data: DepartmentCreate) -> Department:
    """Create a new department."""
    department = Department(
        name=data.name,
        description=data.description,
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def get_departments(db: Session) -> List[Department]:
    """Return all departments."""
    return db.query(Department).all()


# ---------------------------------------------------------------------------
# Designation
# ---------------------------------------------------------------------------

def create_designation(db: Session, data: DesignationCreate) -> Designation:
    """Create a new designation."""
    designation = Designation(
        title=data.title,
        description=data.description,
    )
    db.add(designation)
    db.commit()
    db.refresh(designation)
    return designation


def get_designations(db: Session) -> List[Designation]:
    """Return all designations."""
    return db.query(Designation).all()


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

def create_employee(db: Session, data: EmployeeCreate) -> Employee:
    """Create a new employee record."""
    employee = Employee(
        employee_code=data.employee_code,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        department_id=data.department_id,
        designation_id=data.designation_id,
        date_of_joining=data.date_of_joining,
        salary=data.salary,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def get_employees(db: Session) -> List[Employee]:
    """Return all employees."""
    return db.query(Employee).all()


def get_employee(db: Session, id: int) -> Employee:
    """Return a single employee by ID or raise 404."""
    employee = db.query(Employee).filter(Employee.id == id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {id} not found",
        )
    return employee


def update_employee(db: Session, id: int, data: EmployeeCreate) -> Employee:
    """Update an existing employee record."""
    employee = db.query(Employee).filter(Employee.id == id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {id} not found",
        )
    employee.employee_code = data.employee_code
    employee.first_name = data.first_name
    employee.last_name = data.last_name
    employee.email = data.email
    employee.phone = data.phone
    employee.department_id = data.department_id
    employee.designation_id = data.designation_id
    employee.date_of_joining = data.date_of_joining
    employee.salary = data.salary
    db.commit()
    db.refresh(employee)
    return employee


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------

# Valid payroll status transitions
PAYROLL_TRANSITIONS = {
    "draft": ["processed", "cancelled"],
    "processed": ["paid", "cancelled"],
    "paid": [],  # Terminal state
    "cancelled": [],  # Terminal state
}


def _check_duplicate_payroll(
    db: Session,
    employee_id: int,
    pay_period_start: date,
    pay_period_end: date,
    exclude_payroll_id: Optional[int] = None,
) -> None:
    """
    Check for existing payroll records that overlap with the given period.

    Raises HTTPException if duplicate found.
    """
    query = db.query(Payroll).filter(
        Payroll.employee_id == employee_id,
        Payroll.status != "cancelled",
        # Check for overlap
        or_(
            and_(
                Payroll.pay_period_start <= pay_period_start,
                Payroll.pay_period_end >= pay_period_start,
            ),
            and_(
                Payroll.pay_period_start <= pay_period_end,
                Payroll.pay_period_end >= pay_period_end,
            ),
            and_(
                Payroll.pay_period_start >= pay_period_start,
                Payroll.pay_period_end <= pay_period_end,
            ),
        ),
    )

    if exclude_payroll_id is not None:
        query = query.filter(Payroll.id != exclude_payroll_id)

    existing = query.first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Duplicate payroll detected. Employee {employee_id} already has "
                f"payroll for period {existing.pay_period_start} to {existing.pay_period_end} "
                f"(Payroll ID: {existing.id}, Status: {existing.status})"
            ),
        )


def create_payroll(db: Session, data: PayrollProcess) -> Payroll:
    """
    Create a new payroll record as DRAFT.

    Draft payrolls do NOT create journal entries. Use process_payroll()
    to transition to 'processed' status and create the journal entry.

    Steps:
        1. Validate the employee exists.
        2. Check for duplicate payroll (same employee, overlapping period).
        3. Create PayrollComponent rows for each earning / deduction.
        4. Compute gross_salary, total_deductions, and net_salary.
        5. Create payroll record with status='draft'.

    Raises:
        HTTPException: If employee not found or duplicate payroll exists.
    """
    # --- 1. Validate employee ---
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {data.employee_id} not found",
        )

    # --- 2. Check for duplicate payroll ---
    _check_duplicate_payroll(
        db, data.employee_id, data.pay_period_start, data.pay_period_end
    )

    # --- 3. Build components and compute totals ---
    gross_salary = Decimal("0")
    total_deductions = Decimal("0")
    components: List[PayrollComponent] = []

    for comp in data.components:
        pc = PayrollComponent(
            component_name=comp.component_name,
            component_type=comp.component_type,
            amount=comp.amount,
        )
        components.append(pc)
        if comp.component_type == "earnings":
            gross_salary += comp.amount
        elif comp.component_type == "deductions":
            total_deductions += comp.amount

    # If no earnings components provided, use basic salary as gross
    if gross_salary == Decimal("0"):
        gross_salary = employee.salary

    net_salary = gross_salary - total_deductions

    # --- 4. Create payroll record as DRAFT ---
    payroll = Payroll(
        employee_id=data.employee_id,
        pay_period_start=data.pay_period_start,
        pay_period_end=data.pay_period_end,
        basic_salary=employee.salary,
        gross_salary=gross_salary,
        total_deductions=total_deductions,
        net_salary=net_salary,
        status="draft",
        # No journal entry yet - will be created when processed
    )
    for pc in components:
        payroll.components.append(pc)

    db.add(payroll)
    db.commit()
    db.refresh(payroll)
    return payroll


def get_payroll(db: Session, payroll_id: int) -> Payroll:
    """Return a single payroll record by ID or raise 404."""
    payroll = db.query(Payroll).filter(Payroll.id == payroll_id).first()
    if not payroll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payroll with id {payroll_id} not found",
        )
    return payroll


def process_payroll(db: Session, payroll_id: int) -> Payroll:
    """
    Transition payroll from 'draft' to 'processed'.

    This creates the salary expense journal entry:
        - Debit: Salary Expense (5001)
        - Credit: Salary Payable (2001)

    Raises:
        HTTPException: If payroll not found or invalid state transition.
    """
    payroll = get_payroll(db, payroll_id)

    if payroll.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot process payroll. Current status is '{payroll.status}'. "
                f"Only 'draft' payrolls can be processed."
            ),
        )

    # Get employee info
    employee = db.query(Employee).filter(Employee.id == payroll.employee_id).first()
    employee_code = employee.employee_code if employee else f"EMP-{payroll.employee_id}"

    # Create salary expense journal entry
    journal_entry = create_journal_entry_from_module(
        db=db,
        entry_date=date.today(),
        description=(
            f"Payroll for employee {employee_code} "
            f"({payroll.pay_period_start} to {payroll.pay_period_end})"
        ),
        reference_type="payroll",
        reference_id=payroll.id,
        lines=[
            JournalLine(
                account_code="5001",
                account_name="Salary Expense",
                account_type="expense",
                debit=payroll.gross_salary,
                credit=Decimal("0"),
                description="Salary expense",
            ),
            JournalLine(
                account_code="2001",
                account_name="Salary Payable",
                account_type="liability",
                debit=Decimal("0"),
                credit=payroll.gross_salary,
                description="Salary payable",
            ),
        ],
        auto_post=True,
    )

    # Update payroll status and link journal entry
    payroll.status = "processed"
    payroll.journal_entry_id = journal_entry.id

    db.commit()
    db.refresh(payroll)
    return payroll


def pay_payroll(db: Session, payroll_id: int) -> Payroll:
    """
    Transition payroll from 'processed' to 'paid'.

    This creates the payment journal entry:
        - Debit: Salary Payable (2001)
        - Credit: Cash/Bank (1001)

    Note: This debits the net_salary (after deductions), not gross_salary.

    Raises:
        HTTPException: If payroll not found or invalid state transition.
    """
    payroll = get_payroll(db, payroll_id)

    if payroll.status != "processed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot pay payroll. Current status is '{payroll.status}'. "
                f"Only 'processed' payrolls can be paid."
            ),
        )

    # Get employee info
    employee = db.query(Employee).filter(Employee.id == payroll.employee_id).first()
    employee_code = employee.employee_code if employee else f"EMP-{payroll.employee_id}"

    # Validate amounts before creating journal entry
    if payroll.gross_salary <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot pay payroll with zero or negative gross salary",
        )

    # Create payment journal entry (for net salary)
    create_journal_entry_from_module(
        db=db,
        entry_date=date.today(),
        description=(
            f"Salary payment for employee {employee_code} "
            f"({payroll.pay_period_start} to {payroll.pay_period_end})"
        ),
        reference_type="payroll_payment",
        reference_id=payroll.id,
        lines=[
            JournalLine(
                account_code="2001",
                account_name="Salary Payable",
                account_type="liability",
                debit=payroll.gross_salary,
                credit=Decimal("0"),
                description="Clear salary payable",
            ),
            JournalLine(
                account_code="1001",
                account_name="Cash/Bank",
                account_type="asset",
                debit=Decimal("0"),
                credit=payroll.net_salary,
                description="Salary payment",
            ),
            JournalLine(
                account_code="2101",
                account_name="Tax Payable",
                account_type="liability",
                debit=Decimal("0"),
                credit=payroll.total_deductions,
                description="Withholding taxes",
            ),
        ],
        auto_post=True,
    )

    # Update payroll status
    payroll.status = "paid"

    db.commit()
    db.refresh(payroll)
    return payroll


def cancel_payroll(db: Session, payroll_id: int) -> Payroll:
    """
    Cancel a payroll record.

    Only 'draft' and 'processed' payrolls can be cancelled.
    Paid payrolls cannot be cancelled.

    Raises:
        HTTPException: If payroll not found or invalid state transition.
    """
    payroll = get_payroll(db, payroll_id)

    if payroll.status not in ["draft", "processed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot cancel payroll. Current status is '{payroll.status}'. "
                f"Only 'draft' or 'processed' payrolls can be cancelled."
            ),
        )

    payroll.status = "cancelled"

    db.commit()
    db.refresh(payroll)
    return payroll


def get_payrolls(
    db: Session,
    employee_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> List[Payroll]:
    """
    Return payroll records with optional filters.

    Args:
        db: Database session
        employee_id: Optional filter by employee ID
        status_filter: Optional filter by status ('draft', 'processed', 'paid', 'cancelled')
        period_start: Optional filter for pay periods starting on or after this date
        period_end: Optional filter for pay periods ending on or before this date

    Returns:
        List of payroll records ordered by ID descending
    """
    query = db.query(Payroll)

    if employee_id:
        query = query.filter(Payroll.employee_id == employee_id)
    if status_filter:
        query = query.filter(Payroll.status == status_filter)
    if period_start:
        query = query.filter(Payroll.pay_period_start >= period_start)
    if period_end:
        query = query.filter(Payroll.pay_period_end <= period_end)

    return query.order_by(Payroll.id.desc()).all()
