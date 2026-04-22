"""
API routes for the Finance module.

Endpoints:
    POST /api/finance/transactions             - Create a financial transaction.
    GET  /api/finance/transactions             - List all financial transactions.
    GET  /api/finance/transactions/by-category - Get transactions filtered by category.
    GET  /api/finance/transactions/{id}        - Get a single financial transaction.
    GET  /api/finance/summary                  - Get financial summary with totals.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.auth.auth import role_required
from backend.models.database import get_db
from backend.models.user import User
from backend.schemas.finance import (
    FinancialSummary,
    FinancialTransactionCreate,
    FinancialTransactionResponse,
)
from backend.services.finance_service import (
    create_transaction,
    get_financial_summary,
    get_transaction,
    get_transactions,
    get_transactions_by_category,
)

router = APIRouter(prefix="/api/finance", tags=["Finance"])

ALLOWED_ROLES = ["admin", "accountant"]


# ---------------------------------------------------------------------------
# Financial Transactions
# ---------------------------------------------------------------------------

@router.post("/transactions", response_model=FinancialTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction_route(
    data: FinancialTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """Create a new financial transaction."""
    return create_transaction(db, data)


@router.get("/transactions", response_model=List[FinancialTransactionResponse])
def list_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """List all financial transactions."""
    return get_transactions(db)


@router.get("/transactions/by-category", response_model=List[FinancialTransactionResponse])
def list_transactions_by_category(
    category: Optional[str] = Query(None, description="Filter by category"),
    transaction_type: Optional[str] = Query(None, description="Filter by type (income/expense)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """Get transactions filtered by category and/or type."""
    return get_transactions_by_category(db, category=category, transaction_type=transaction_type)


@router.get("/transactions/{id}", response_model=FinancialTransactionResponse)
def get_transaction_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """Get a single financial transaction by ID."""
    return get_transaction(db, id)


# ---------------------------------------------------------------------------
# Financial Summaries
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=FinancialSummary)
def get_summary_route(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Get financial summary with totals.

    Returns total income, total expenses, net balance, and breakdowns by category.
    Optionally filter by date range.
    """
    return get_financial_summary(db, start_date=start_date, end_date=end_date)
