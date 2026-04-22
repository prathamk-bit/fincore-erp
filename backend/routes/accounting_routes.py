"""
API routes for the Accounting module.

Endpoints:
    POST /api/accounting/accounts                    - Create an account.
    GET  /api/accounting/accounts                    - List all accounts.
    GET  /api/accounting/accounts/{id}               - Get a single account.
    POST /api/accounting/journal-entries             - Create a journal entry (draft).
    GET  /api/accounting/journal-entries             - List all journal entries.
    GET  /api/accounting/journal-entries/{id}        - Get a single journal entry.
    PUT  /api/accounting/journal-entries/{id}        - Update a draft journal entry.
    POST /api/accounting/journal-entries/{id}/post   - Post a draft journal entry.
    GET  /api/accounting/ledger                      - Get full general ledger (all accounts).
    GET  /api/accounting/ledger/{account_id}         - Get ledger for a specific account.
    GET  /api/accounting/trial-balance               - Get trial balance report.
    GET  /api/accounting/reports/income-statement    - Get income statement (P&L).
    GET  /api/accounting/reports/balance-sheet       - Get balance sheet.
    GET  /api/accounting/reports/cash-flow           - Get cash flow statement.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.auth.auth import role_required
from backend.models.database import get_db
from backend.models.user import User
from backend.schemas.accounting import (
    AccountCreate,
    AccountResponse,
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntryResponse,
    LedgerEntry,
    TrialBalanceSummary,
    IncomeStatement,
    BalanceSheet,
    CashFlowStatement,
)
from backend.services.accounting_service import (
    create_account,
    create_journal_entry,
    get_account,
    get_accounts,
    get_journal_entry,
    get_journal_entries,
    get_ledger,
    get_trial_balance,
    post_journal_entry,
    update_journal_entry,
    get_income_statement,
    get_balance_sheet,
    get_cash_flow_statement,
)

router = APIRouter(prefix="/api/accounting", tags=["Accounting"])

ALLOWED_ROLES = ["admin", "accountant"]


# ---------------------------------------------------------------------------
# Accounts (Chart of Accounts)
# ---------------------------------------------------------------------------

@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account_route(
    data: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """Create a new account in the Chart of Accounts."""
    return create_account(db, data)


@router.get("/accounts", response_model=List[AccountResponse])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """List all accounts in the Chart of Accounts."""
    return get_accounts(db)


@router.get("/accounts/{id}", response_model=AccountResponse)
def get_account_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """Get a single account by ID."""
    return get_account(db, id)


# ---------------------------------------------------------------------------
# Journal Entries
# ---------------------------------------------------------------------------

@router.post("/journal-entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
def create_journal_entry_route(
    data: JournalEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Create a new journal entry with its lines as DRAFT.

    Draft entries do not affect account balances until posted.
    Use POST /journal-entries/{id}/post to post the entry.
    """
    return create_journal_entry(db, data)


@router.get("/journal-entries", response_model=List[JournalEntryResponse])
def list_journal_entries(
    start_date: Optional[date] = Query(None, description="Filter entries from this date"),
    end_date: Optional[date] = Query(None, description="Filter entries up to this date"),
    status: Optional[str] = Query(None, description="Filter by status: draft or posted"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """List journal entries with optional filters."""
    return get_journal_entries(db, start_date, end_date, status)


@router.get("/journal-entries/{id}", response_model=JournalEntryResponse)
def get_journal_entry_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """Get a single journal entry by ID."""
    return get_journal_entry(db, id)


@router.put("/journal-entries/{id}", response_model=JournalEntryResponse)
def update_journal_entry_route(
    id: int,
    data: JournalEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Update a DRAFT journal entry.

    Only draft entries can be updated. Posted entries are immutable.
    """
    return update_journal_entry(db, id, data)


@router.post("/journal-entries/{id}/post", response_model=JournalEntryResponse)
def post_journal_entry_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Post a draft journal entry to the ledger.

    This transitions the entry from 'draft' to 'posted' status and
    updates all affected account balances.

    Posted entries are IMMUTABLE and cannot be edited or unposted.
    """
    return post_journal_entry(db, id)


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

@router.get("/ledger", response_model=List[LedgerEntry])
def get_full_ledger(
    include_drafts: bool = Query(False, description="Include draft entries (not counted in running balance)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Get the full general ledger across all accounts.

    Returns ledger entries for every account that has journal entry postings.
    By default, only posted entries are included.
    """
    accounts = get_accounts(db)
    all_entries: List[LedgerEntry] = []
    for account in accounts:
        all_entries.extend(get_ledger(db, account.id, include_drafts=include_drafts))
    return all_entries


@router.get("/ledger/{account_id}", response_model=List[LedgerEntry])
def get_account_ledger(
    account_id: int,
    include_drafts: bool = Query(False, description="Include draft entries (not counted in running balance)"),
    start_date: Optional[date] = Query(None, description="Filter entries from this date"),
    end_date: Optional[date] = Query(None, description="Filter entries up to this date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """Get the ledger for a specific account with optional date filtering."""
    return get_ledger(db, account_id, include_drafts, start_date, end_date)


# ---------------------------------------------------------------------------
# Trial Balance
# ---------------------------------------------------------------------------

@router.get("/trial-balance", response_model=TrialBalanceSummary)
def get_trial_balance_route(
    as_of_date: Optional[date] = Query(None, description="As of date (defaults to today)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Get the trial balance report.

    Lists all active accounts with their debit or credit balances.
    Total debits should equal total credits if the books are balanced.

    The is_balanced field indicates whether the books are in balance.
    """
    return get_trial_balance(db, as_of_date)


# ---------------------------------------------------------------------------
# Financial Reports
# ---------------------------------------------------------------------------

@router.get("/reports/income-statement", response_model=IncomeStatement)
def get_income_statement_route(
    start_date: date = Query(..., description="Period start date"),
    end_date: date = Query(..., description="Period end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Get the Income Statement (Profit & Loss) for a period.

    Shows all revenue and expenses for the specified period, with net income calculated.
    Net Income = Total Revenue - Total Expenses

    A positive net income indicates profit; negative indicates loss.
    """
    return get_income_statement(db, start_date, end_date)


@router.get("/reports/balance-sheet", response_model=BalanceSheet)
def get_balance_sheet_route(
    as_of_date: Optional[date] = Query(None, description="As of date (defaults to today)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Get the Balance Sheet as of a specific date.

    Shows Assets, Liabilities, and Equity (including current period retained earnings).
    The accounting equation: Assets = Liabilities + Equity

    The is_balanced field indicates whether the balance sheet is in balance.
    """
    if as_of_date is None:
        as_of_date = date.today()
    return get_balance_sheet(db, as_of_date)


@router.get("/reports/cash-flow", response_model=CashFlowStatement)
def get_cash_flow_route(
    start_date: date = Query(..., description="Period start date"),
    end_date: date = Query(..., description="Period end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "accountant"])),
):
    """
    Get the Cash Flow Statement for a period.

    Shows cash inflows and outflows divided into:
    - Operating activities: Revenue and expense related cash flows
    - Investing activities: Long-term asset transactions
    - Financing activities: Debt and equity transactions

    Includes beginning and ending cash balances.
    """
    return get_cash_flow_statement(db, start_date, end_date)
