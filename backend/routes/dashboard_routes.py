"""
API routes for the Dashboard module.

Endpoints:
    GET /api/dashboard/stats                  - Finance-centric summary statistics.
    GET /api/dashboard/recent-journal-entries - Recent journal entries for dashboard.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user, role_required
from backend.models.database import get_db
from backend.models.hr import Employee
from backend.models.accounting import Account, JournalEntry
from backend.models.inventory import Item
from backend.models.procurement import PurchaseOrder
from backend.models.finance import FinancialTransaction
from backend.models.user import User


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.post("/reset-demo")
def reset_demo_data(current_user: User = Depends(get_current_user)):
    """Reset demo data to initial state (Dev/Demo Only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can reset demo data")
    from backend.main import seed_demo_data
    seed_demo_data(force=True)
    return {"message": "Demo data reset successfully"}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RecentJournalEntry(BaseModel):
    """Simplified journal entry for dashboard display."""
    id: int
    entry_number: str
    date: date
    description: Optional[str] = None
    reference_type: Optional[str] = None
    total_debit: Decimal
    total_credit: Decimal

    model_config = ConfigDict(from_attributes=True)


class DashboardStats(BaseModel):
    """
    Finance-centric dashboard statistics.

    Primary focus on financial KPIs:
    - Net Position (Assets - Liabilities)
    - Net Income (Revenue - Expenses)
    - Revenue and Expense totals

    Secondary:
    - Asset and Liability totals
    - Account and journal entry counts
    - Operational metrics

    Note: Financial metrics are Optional - they return null for non-financial roles
    (hr_manager, inventory_manager) to enforce RBAC.
    """
    # Primary financial metrics (shown prominently) - Optional for RBAC
    net_position: Optional[Decimal] = None  # Assets - Liabilities (Net Worth)
    net_income: Optional[Decimal] = None  # Revenue - Expenses
    total_revenue: Optional[Decimal] = None
    total_expenses: Optional[Decimal] = None

    # Secondary metrics - Optional for RBAC
    total_assets: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None

    # Operational counts (shown smaller) - visible to all roles
    total_accounts: Optional[int] = None
    total_journal_entries: Optional[int] = None
    total_employees: int
    total_items: int
    total_purchase_orders: int

    # Trial balance status - Optional for RBAC
    is_balanced: Optional[bool] = None


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return finance-centric summary for the dashboard.

    Role-based access:
    - admin, accountant: Full financial metrics
    - hr_manager, inventory_manager: Operational counts only (financial data hidden)

    Primary focus on:
    - Net Position (Assets - Liabilities) - The company's net worth
    - Net Income (Revenue - Expenses) - Profitability
    - Revenue and Expense totals

    Secondary:
    - Account and journal entry counts
    - Operational metrics (employees, items, POs)
    - Trial balance status (is_balanced)
    """
    try:
        # Check if user has access to financial data
        has_financial_access = current_user.role in ["admin", "accountant"]

        # Count operational metrics (visible to all roles)
        try:
            total_employees = db.query(Employee).filter(Employee.is_active == True).count()
        except Exception:
            total_employees = 0

        try:
            total_items = db.query(Item).count()
        except Exception:
            total_items = 0

        try:
            total_purchase_orders = db.query(PurchaseOrder).count()
        except Exception:
            total_purchase_orders = 0

        # For non-financial roles, return only operational counts
        if not has_financial_access:
            return DashboardStats(
                # Financial metrics hidden (null)
                net_position=None,
                net_income=None,
                total_revenue=None,
                total_expenses=None,
                total_assets=None,
                total_liabilities=None,
                total_accounts=None,
                total_journal_entries=None,
                is_balanced=None,
                # Operational counts visible
                total_employees=total_employees,
                total_items=total_items,
                total_purchase_orders=total_purchase_orders,
            )

        # Calculate account balances by type from the Chart of Accounts
        accounts = db.query(Account).filter(Account.is_active == True).all()

        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        total_equity = Decimal("0")
        total_revenue = Decimal("0")
        total_expenses = Decimal("0")

        total_debits = Decimal("0")
        total_credits = Decimal("0")

        for account in accounts:
            # Safe Decimal conversion for balance (handles None, float, and other types)
            balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
            # Safe null check for account_type
            account_type = (account.account_type or "").lower()

            if account_type == "asset":
                total_assets += balance
                # Assets have normal debit balance
                if balance >= 0:
                    total_debits += balance
                else:
                    total_credits += abs(balance)
            elif account_type == "liability":
                total_liabilities += balance
                # Liabilities have normal credit balance
                if balance >= 0:
                    total_credits += balance
                else:
                    total_debits += abs(balance)
            elif account_type == "equity":
                total_equity += balance
                # Equity has normal credit balance
                if balance >= 0:
                    total_credits += balance
                else:
                    total_debits += abs(balance)
            elif account_type == "revenue":
                total_revenue += balance
                # Revenue has normal credit balance
                if balance >= 0:
                    total_credits += balance
                else:
                    total_debits += abs(balance)
            elif account_type == "expense":
                total_expenses += balance
                # Expenses have normal debit balance
                if balance >= 0:
                    total_debits += balance
                else:
                    total_credits += abs(balance)

        # Calculate key financial metrics
        net_position = total_assets - total_liabilities  # Net Worth
        net_income = total_revenue - total_expenses  # Profitability

        # Check if books are balanced
        is_balanced = total_debits == total_credits

        # Count additional metrics
        try:
            total_journal_entries = db.query(JournalEntry).count()
        except Exception:
            total_journal_entries = 0

        total_accounts = len(accounts)

        return DashboardStats(
            # Primary financial metrics
            net_position=net_position,
            net_income=net_income,
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            # Secondary metrics
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            # Operational counts
            total_accounts=total_accounts,
            total_journal_entries=total_journal_entries,
            total_employees=total_employees,
            total_items=total_items,
            total_purchase_orders=total_purchase_orders,
            # Trial balance status
            is_balanced=is_balanced,
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dashboard statistics: {str(e)}"
        )


# ---------------------------------------------------------------------------
# GET /recent-journal-entries
# ---------------------------------------------------------------------------

@router.get("/recent-journal-entries", response_model=List[RecentJournalEntry])
def get_recent_journal_entries(
    limit: int = Query(10, ge=1, le=50, description="Number of entries to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Return the most recent journal entries for dashboard display.

    Shows the latest transactions across all modules for quick overview.

    Access restricted to:
    - admin: Full access
    - accountant: Full access

    Other roles will receive 403 Forbidden.
    """
    try:
        entries = (
            db.query(JournalEntry)
            .order_by(JournalEntry.date.desc(), JournalEntry.id.desc())
            .limit(limit)
            .all()
        )

        return [
            RecentJournalEntry(
                id=entry.id,
                entry_number=entry.entry_number or f"JE-{entry.id}",
                date=entry.date,
                description=entry.description,
                reference_type=entry.reference_type,
                total_debit=entry.total_debit if entry.total_debit is not None else Decimal("0"),
                total_credit=entry.total_credit if entry.total_credit is not None else Decimal("0"),
            )
            for entry in entries
        ]

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load recent journal entries: {str(e)}"
        )
