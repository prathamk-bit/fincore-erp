"""
Finance service layer.

Provides business-logic functions for creating and querying unified
financial transactions that span across all ERP modules.

This module automatically creates journal entries for all financial
transactions (income and expense), ensuring proper double-entry
bookkeeping throughout the system.

Income transactions:
    - Debit: Cash/Bank (1001)
    - Credit: Revenue account based on category

Expense transactions:
    - Debit: Expense account based on category
    - Credit: Cash/Bank (1001)
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.finance import FinancialTransaction
from backend.schemas.finance import FinancialTransactionCreate
from backend.services.accounting_service import (
    create_journal_entry_from_module,
    JournalLine,
)


# ---------------------------------------------------------------------------
# Account Mappings for Financial Transactions
# ---------------------------------------------------------------------------

# Standard account mappings for income transactions
INCOME_ACCOUNTS = {
    "default": ("4001", "Revenue", "revenue"),
    "sales": ("4001", "Sales Revenue", "revenue"),
    "service": ("4002", "Service Revenue", "revenue"),
    "interest": ("4003", "Interest Income", "revenue"),
    "other": ("4099", "Other Income", "revenue"),
}

# Standard account mappings for expense transactions
EXPENSE_ACCOUNTS = {
    "default": ("5099", "General Expense", "expense"),
    "office_supplies": ("5010", "Office Supplies", "expense"),
    "utilities": ("5020", "Utilities Expense", "expense"),
    "rent": ("5030", "Rent Expense", "expense"),
    "maintenance": ("5040", "Maintenance Expense", "expense"),
    "travel": ("5050", "Travel Expense", "expense"),
    "marketing": ("5060", "Marketing Expense", "expense"),
    "other": ("5099", "General Expense", "expense"),
}


# ---------------------------------------------------------------------------
# Financial Transaction
# ---------------------------------------------------------------------------

def create_transaction(
    db: Session, data: FinancialTransactionCreate
) -> FinancialTransaction:
    """
    Create a new financial transaction with automatic journal entry.

    Income transactions:
        - Debit: Cash/Bank (1001)
        - Credit: Revenue account based on category

    Expense transactions:
        - Debit: Expense account based on category
        - Credit: Cash/Bank (1001)

    Args:
        db: Database session
        data: Transaction data including type, amount, and category

    Returns:
        The created FinancialTransaction with linked journal entry

    Raises:
        HTTPException: If transaction_type is invalid
    """
    if data.transaction_type not in ("income", "expense"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid transaction_type '{data.transaction_type}'. "
                "Must be 'income' or 'expense'."
            ),
        )

    # Create the financial transaction record first
    transaction = FinancialTransaction(
        transaction_date=data.transaction_date,
        transaction_type=data.transaction_type,
        category=data.category,
        amount=data.amount,
        description=data.description,
        reference_type=data.reference_type,
        reference_id=data.reference_id,
    )
    db.add(transaction)
    db.flush()  # Get transaction.id

    # Build journal entry lines based on transaction type
    category_key = (data.category or "").lower().replace(" ", "_")

    if data.transaction_type == "income":
        # Get appropriate revenue account
        account_info = INCOME_ACCOUNTS.get(category_key, INCOME_ACCOUNTS["default"])

        lines = [
            JournalLine(
                account_code="1001",
                account_name="Cash/Bank",
                account_type="asset",
                debit=data.amount,
                credit=Decimal("0"),
                description=f"Cash received - {data.description or data.category or 'Income'}",
            ),
            JournalLine(
                account_code=account_info[0],
                account_name=account_info[1],
                account_type=account_info[2],
                debit=Decimal("0"),
                credit=data.amount,
                description=f"Revenue - {data.description or data.category or 'Income'}",
            ),
        ]
    else:  # expense
        # Get appropriate expense account
        account_info = EXPENSE_ACCOUNTS.get(category_key, EXPENSE_ACCOUNTS["default"])

        lines = [
            JournalLine(
                account_code=account_info[0],
                account_name=account_info[1],
                account_type=account_info[2],
                debit=data.amount,
                credit=Decimal("0"),
                description=f"Expense - {data.description or data.category or 'Expense'}",
            ),
            JournalLine(
                account_code="1001",
                account_name="Cash/Bank",
                account_type="asset",
                debit=Decimal("0"),
                credit=data.amount,
                description=f"Cash paid - {data.description or data.category or 'Expense'}",
            ),
        ]

    # Create journal entry via centralized service
    journal_entry = create_journal_entry_from_module(
        db=db,
        entry_date=data.transaction_date,
        description=data.description or f"{data.transaction_type.title()} - {data.category or 'General'}",
        reference_type="financial_transaction",
        reference_id=transaction.id,
        lines=lines,
    )

    # Link journal entry to transaction
    transaction.journal_entry_id = journal_entry.id

    db.commit()
    db.refresh(transaction)
    return transaction


def get_transactions(db: Session) -> List[FinancialTransaction]:
    """Return all financial transactions ordered by date descending."""
    return (
        db.query(FinancialTransaction)
        .order_by(
            FinancialTransaction.transaction_date.desc(),
            FinancialTransaction.id.desc(),
        )
        .all()
    )


def get_transaction(db: Session, transaction_id: int) -> FinancialTransaction:
    """Return a single financial transaction by ID or raise 404."""
    transaction = (
        db.query(FinancialTransaction)
        .filter(FinancialTransaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Financial transaction with id {transaction_id} not found",
        )
    return transaction


# ---------------------------------------------------------------------------
# Financial Summaries
# ---------------------------------------------------------------------------

def get_financial_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict:
    """
    Get financial summary with totals by category.

    Args:
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        Dict with total_income, total_expenses, net_balance, and category breakdowns
    """
    query = db.query(FinancialTransaction)

    if start_date:
        query = query.filter(FinancialTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(FinancialTransaction.transaction_date <= end_date)

    transactions = query.all()

    total_income = Decimal("0")
    total_expenses = Decimal("0")
    income_by_category: Dict[str, Dict] = defaultdict(
        lambda: {"total_amount": Decimal("0"), "transaction_count": 0}
    )
    expense_by_category: Dict[str, Dict] = defaultdict(
        lambda: {"total_amount": Decimal("0"), "transaction_count": 0}
    )

    for trans in transactions:
        category = trans.category or "Uncategorized"
        # Safe Decimal conversion for amount
        amount = Decimal(str(trans.amount)) if trans.amount is not None else Decimal("0")
        transaction_type_lower = (trans.transaction_type or "").lower()

        if transaction_type_lower == "income":
            total_income += amount
            income_by_category[category]["total_amount"] += amount
            income_by_category[category]["transaction_count"] += 1
        elif transaction_type_lower == "expense":
            total_expenses += amount
            expense_by_category[category]["total_amount"] += amount
            expense_by_category[category]["transaction_count"] += 1

    net_balance = total_income - total_expenses

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
        "income_by_category": [
            {"category": cat, "total_amount": data["total_amount"], "transaction_count": data["transaction_count"]}
            for cat, data in sorted(income_by_category.items())
        ],
        "expense_by_category": [
            {"category": cat, "total_amount": data["total_amount"], "transaction_count": data["transaction_count"]}
            for cat, data in sorted(expense_by_category.items())
        ],
        "transaction_count": len(transactions),
    }


def get_transactions_by_category(
    db: Session,
    category: Optional[str] = None,
    transaction_type: Optional[str] = None,
) -> List[FinancialTransaction]:
    """
    Get transactions filtered by category and/or type.

    Args:
        db: Database session
        category: Optional category filter
        transaction_type: Optional type filter ("income" or "expense")

    Returns:
        List of matching transactions
    """
    query = db.query(FinancialTransaction)

    if category:
        query = query.filter(FinancialTransaction.category == category)
    if transaction_type:
        query = query.filter(FinancialTransaction.transaction_type == transaction_type)

    return query.order_by(
        FinancialTransaction.transaction_date.desc(),
        FinancialTransaction.id.desc(),
    ).all()
