"""
Accounting service layer.

Provides business-logic functions for the Chart of Accounts, journal entries
(double-entry bookkeeping), and general-ledger views.

Every journal entry is validated so that total debits equal total credits
before it is persisted. Account balances are ONLY updated when a journal
entry is POSTED (status='posted'). Draft entries do not affect account balances.

This module serves as the CENTRAL ACCOUNTING HUB for the entire ERP system.
All other modules (HR, Procurement, Finance, Inventory) should use the
`create_journal_entry_from_module()` function to create journal entries,
ensuring consistent double-entry bookkeeping across the system.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.accounting import Account, JournalEntry, JournalEntryLine
from backend.schemas.accounting import (
    AccountCreate,
    JournalEntryCreate,
    JournalEntryUpdate,
    LedgerEntry,
    TrialBalanceEntry,
    TrialBalanceSummary,
)


# ---------------------------------------------------------------------------
# Account (Chart of Accounts)
# ---------------------------------------------------------------------------

def create_account(db: Session, data: AccountCreate) -> Account:
    """Create a new account in the Chart of Accounts."""
    existing = db.query(Account).filter(Account.code == data.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account with code '{data.code}' already exists",
        )

    if data.parent_account_id is not None:
        parent = db.query(Account).filter(
            Account.id == data.parent_account_id
        ).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent account with id {data.parent_account_id} not found",
            )

    account = Account(
        code=data.code,
        name=data.name,
        account_type=data.account_type,
        parent_account_id=data.parent_account_id,
        balance=Decimal("0"),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_accounts(db: Session) -> List[Account]:
    """Return all accounts in the Chart of Accounts."""
    return db.query(Account).order_by(Account.code).all()


def get_account(db: Session, account_id: int) -> Account:
    """Return a single account by ID or raise 404."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found",
        )
    return account


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_journal_entry_number(db: Session) -> str:
    """Generate the next sequential journal-entry number (JE-<id>)."""
    last = (
        db.query(JournalEntry)
        .order_by(JournalEntry.id.desc())
        .first()
    )
    next_id = (last.id + 1) if last else 1
    return f"JE-{next_id}"


# ---------------------------------------------------------------------------
# Centralized Helpers for Cross-Module Integration
# ---------------------------------------------------------------------------

def get_or_create_account(
    db: Session,
    code: str,
    name: str,
    account_type: str,
) -> Account:
    """
    Return the Account with the given code, creating it if necessary.

    This is the centralized helper for all modules to ensure consistent
    account creation.

    Args:
        db: Database session
        code: Account code (e.g., '5001')
        name: Account name (e.g., 'Salary Expense')
        account_type: One of 'asset', 'liability', 'equity', 'revenue', 'expense'

    Returns:
        The existing or newly created Account
    """
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        account = Account(
            code=code,
            name=name,
            account_type=account_type,
            balance=Decimal("0"),
        )
        db.add(account)
        db.flush()  # so account.id is available
    return account


@dataclass
class JournalLine:
    """
    Simplified line item for module-initiated journal entries.

    Used by create_journal_entry_from_module() to accept line items
    with account codes instead of account IDs, allowing automatic
    account creation if needed.
    """

    account_code: str
    account_name: str
    account_type: str  # asset, liability, equity, revenue, expense
    debit: Decimal
    credit: Decimal
    description: Optional[str] = None


def create_journal_entry_from_module(
    db: Session,
    entry_date: date,
    description: str,
    reference_type: str,
    reference_id: int,
    lines: List[JournalLine],
    auto_post: bool = True,
) -> JournalEntry:
    """
    Create a journal entry initiated by another module (HR, Procurement, etc.).

    This centralizes all journal entry creation to ensure:
    - Proper debit/credit validation
    - Consistent entry numbering
    - Automatic account creation when needed
    - Correct balance updates per account type (only when posted)

    Args:
        db: Database session
        entry_date: Accounting date for the entry
        description: Journal entry description/narration
        reference_type: Source module (e.g., 'payroll', 'purchase_order', 'inventory_adjustment')
        reference_id: Primary key of the source document
        lines: List of JournalLine objects with account info and amounts
        auto_post: If True (default), entry is immediately posted and balances updated.
                   If False, entry is created as draft.

    Returns:
        The created JournalEntry

    Raises:
        HTTPException: If debits != credits or no lines provided
    """
    if not lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry must have at least one line",
        )

    # Filter out lines where both debit and credit are zero (no-op lines)
    lines = [line for line in lines if line.debit != Decimal("0") or line.credit != Decimal("0")]

    if not lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry must have at least one non-zero line",
        )

    total_debit = sum(line.debit for line in lines)
    total_credit = sum(line.credit for line in lines)

    if total_debit == Decimal("0") and total_credit == Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a journal entry with zero total amount",
        )

    if total_debit != total_credit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Total debits ({total_debit}) must equal total credits "
                f"({total_credit})"
            ),
        )

    # Create header
    entry_number = _next_journal_entry_number(db)
    journal_entry = JournalEntry(
        entry_number=entry_number,
        date=entry_date,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        status="posted" if auto_post else "draft",
        total_debit=total_debit,
        total_credit=total_credit,
    )

    accounts_to_update: List[Tuple[Account, Decimal, Decimal]] = []

    for line in lines:
        account = get_or_create_account(
            db, line.account_code, line.account_name, line.account_type
        )

        journal_line = JournalEntryLine(
            account_id=account.id,
            debit=line.debit,
            credit=line.credit,
            description=line.description,
        )
        journal_entry.lines.append(journal_line)
        accounts_to_update.append((account, line.debit, line.credit))

    db.add(journal_entry)
    db.flush()

    # Only update account balances if auto_post is True
    if auto_post:
        _update_account_balances(accounts_to_update)

    return journal_entry


def _update_account_balances(
    accounts_to_update: List[Tuple[Account, Decimal, Decimal]]
) -> None:
    """
    Update account balances based on debits and credits.

    Asset and Expense accounts: balance += debit - credit
    Liability, Equity, and Revenue accounts: balance += credit - debit
    
    All values are safely converted to Decimal to prevent None or type errors.
    """
    for account, debit, credit in accounts_to_update:
        # Safe conversion of all values to Decimal
        current_balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
        safe_debit = Decimal(str(debit)) if debit is not None else Decimal("0")
        safe_credit = Decimal(str(credit)) if credit is not None else Decimal("0")
        
        account_type = (account.account_type or "").lower()
        
        if account_type in ("asset", "expense"):
            # Normal debit balance: increases with debits
            account.balance = current_balance + safe_debit - safe_credit
        else:
            # Normal credit balance (liability, equity, revenue): increases with credits
            account.balance = current_balance + safe_credit - safe_debit


# ---------------------------------------------------------------------------
# Journal Entry
# ---------------------------------------------------------------------------

def create_journal_entry(db: Session, data: JournalEntryCreate) -> JournalEntry:
    """
    Create a journal entry with its lines as DRAFT.

    Draft entries do NOT affect account balances. Use post_journal_entry()
    to post the entry and update balances.

    Validates that:
        - At least one line is provided.
        - Total debits equal total credits.
        - All referenced accounts exist.
    """
    if not data.lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry must have at least one line",
        )

    total_debit = sum(line.debit for line in data.lines)
    total_credit = sum(line.credit for line in data.lines)

    if total_debit != total_credit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Total debits ({total_debit}) must equal total credits "
                f"({total_credit})"
            ),
        )

    # Validate all account IDs exist
    account_ids = {line.account_id for line in data.lines}
    accounts = (
        db.query(Account)
        .filter(Account.id.in_(account_ids))
        .all()
    )
    found_ids = {a.id for a in accounts}
    missing = account_ids - found_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account(s) not found: {sorted(missing)}",
        )

    # Create header - always as draft
    entry_number = _next_journal_entry_number(db)
    journal_entry = JournalEntry(
        entry_number=entry_number,
        date=data.date,
        description=data.description,
        reference_type=data.reference_type,
        reference_id=data.reference_id,
        status="draft",  # Always start as draft
        total_debit=total_debit,
        total_credit=total_credit,
    )

    # Create lines
    for line_data in data.lines:
        line = JournalEntryLine(
            account_id=line_data.account_id,
            debit=line_data.debit,
            credit=line_data.credit,
            description=line_data.description,
        )
        journal_entry.lines.append(line)

    db.add(journal_entry)
    # Note: NO balance updates - this is a draft entry
    db.commit()
    db.refresh(journal_entry)
    return journal_entry


def get_journal_entry(db: Session, entry_id: int) -> JournalEntry:
    """Return a single journal entry by ID or raise 404."""
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal entry with id {entry_id} not found",
        )
    return entry


def update_journal_entry(
    db: Session, entry_id: int, data: JournalEntryUpdate
) -> JournalEntry:
    """
    Update a DRAFT journal entry.

    Posted entries are immutable and cannot be updated.

    Validates that:
        - Entry exists and is in draft status.
        - If lines are provided, total debits equal total credits.
        - All referenced accounts exist.
    """
    entry = get_journal_entry(db, entry_id)

    if entry.status == "posted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit a posted journal entry. Posted entries are immutable.",
        )

    # Update header fields if provided
    if data.date is not None:
        entry.date = data.date
    if data.description is not None:
        entry.description = data.description
    if data.reference_type is not None:
        entry.reference_type = data.reference_type
    if data.reference_id is not None:
        entry.reference_id = data.reference_id

    # Update lines if provided
    if data.lines is not None:
        if not data.lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Journal entry must have at least one line",
            )

        total_debit = sum(line.debit for line in data.lines)
        total_credit = sum(line.credit for line in data.lines)

        if total_debit != total_credit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Total debits ({total_debit}) must equal total credits "
                    f"({total_credit})"
                ),
            )

        # Validate all account IDs exist
        account_ids = {line.account_id for line in data.lines}
        accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
        found_ids = {a.id for a in accounts}
        missing = account_ids - found_ids
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Account(s) not found: {sorted(missing)}",
            )

        # Delete existing lines and create new ones
        for line in entry.lines:
            db.delete(line)

        entry.lines = []
        for line_data in data.lines:
            line = JournalEntryLine(
                account_id=line_data.account_id,
                debit=line_data.debit,
                credit=line_data.credit,
                description=line_data.description,
            )
            entry.lines.append(line)

        entry.total_debit = total_debit
        entry.total_credit = total_credit

    db.commit()
    db.refresh(entry)
    return entry


def post_journal_entry(db: Session, entry_id: int) -> JournalEntry:
    """
    Post a draft journal entry to the ledger.

    This transitions the entry from 'draft' to 'posted' status and
    updates all affected account balances.

    Posted entries are IMMUTABLE and cannot be edited or unposted.

    Validates that:
        - Entry exists and is in draft status.
        - Total debits equal total credits.

    Raises:
        HTTPException: If entry not found, already posted, or unbalanced.
    """
    entry = get_journal_entry(db, entry_id)

    if entry.status == "posted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Journal entry {entry.entry_number} is already posted.",
        )

    # Re-validate balance before posting
    if entry.total_debit != entry.total_credit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot post unbalanced entry. Total debits ({entry.total_debit}) "
                f"must equal total credits ({entry.total_credit})"
            ),
        )

    # Update status to posted
    entry.status = "posted"

    # Update account balances
    accounts_to_update: List[Tuple[Account, Decimal, Decimal]] = []
    for line in entry.lines:
        account = db.query(Account).filter(Account.id == line.account_id).first()
        if account:
            accounts_to_update.append((account, line.debit, line.credit))

    _update_account_balances(accounts_to_update)

    db.commit()
    db.refresh(entry)
    return entry


def get_journal_entries(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status_filter: Optional[str] = None,
) -> List[JournalEntry]:
    """
    Return journal entries with optional filters.

    Args:
        db: Database session
        start_date: Optional filter for entries on or after this date
        end_date: Optional filter for entries on or before this date
        status_filter: Optional filter by status ('draft' or 'posted')

    Returns:
        List of journal entries ordered by date descending
    """
    query = db.query(JournalEntry)

    if start_date:
        query = query.filter(JournalEntry.date >= start_date)
    if end_date:
        query = query.filter(JournalEntry.date <= end_date)
    if status_filter:
        query = query.filter(JournalEntry.status == status_filter)

    return query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).all()


def get_ledger(
    db: Session,
    account_id: int,
    include_drafts: bool = False,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[LedgerEntry]:
    """
    Return a ledger view for a specific account.

    Each row contains the journal entry header information merged with
    the individual debit/credit posting for the requested account.
    A running balance is computed across POSTED entries only (by default).

    Args:
        db: Database session
        account_id: The account ID to get ledger for
        include_drafts: If True, include draft entries (not counted in running balance)
        start_date: Optional filter for entries on or after this date
        end_date: Optional filter for entries on or before this date
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found",
        )

    query = (
        db.query(JournalEntryLine)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .filter(JournalEntryLine.account_id == account_id)
    )

    if not include_drafts:
        query = query.filter(JournalEntry.status == "posted")

    if start_date:
        query = query.filter(JournalEntry.date >= start_date)
    if end_date:
        query = query.filter(JournalEntry.date <= end_date)

    lines = query.order_by(JournalEntry.date, JournalEntry.id, JournalEntryLine.id).all()

    running_balance = Decimal("0")
    ledger_entries: List[LedgerEntry] = []
    
    account_type = (account.account_type or "").lower()

    for line in lines:
        je = line.journal_entry
        # Safely convert debit/credit to Decimal
        safe_debit = Decimal(str(line.debit)) if line.debit is not None else Decimal("0")
        safe_credit = Decimal(str(line.credit)) if line.credit is not None else Decimal("0")
        
        # Only posted entries affect running balance
        if je.status == "posted":
            if account_type in ("asset", "expense"):
                running_balance += safe_debit - safe_credit
            else:
                running_balance += safe_credit - safe_debit

        ledger_entries.append(
            LedgerEntry(
                journal_entry_id=je.id,
                entry_number=je.entry_number,
                date=je.date,
                description=je.description,
                status=je.status,
                account_id=account.id,
                account_code=account.code,
                account_name=account.name,
                debit=safe_debit,
                credit=safe_credit,
                balance=running_balance,
            )
        )

    return ledger_entries


# ---------------------------------------------------------------------------
# Trial Balance
# ---------------------------------------------------------------------------

def get_trial_balance(
    db: Session, as_of_date: Optional[date] = None
) -> TrialBalanceSummary:
    """
    Generate a trial balance report.

    The trial balance lists all accounts with their debit or credit balances.
    Asset and Expense accounts normally have debit balances.
    Liability, Equity, and Revenue accounts normally have credit balances.

    Args:
        db: Database session
        as_of_date: Optional date filter (defaults to today)

    Returns:
        TrialBalanceSummary with all accounts and totals
    """
    from datetime import date as date_module

    if as_of_date is None:
        as_of_date = date_module.today()

    accounts = (
        db.query(Account)
        .filter(Account.is_active == True)
        .order_by(Account.code)
        .all()
    )

    entries: List[TrialBalanceEntry] = []
    total_debits = Decimal("0")
    total_credits = Decimal("0")

    for account in accounts:
        # Safe Decimal conversion for balance
        balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
        account_type = (account.account_type or "").lower()

        # Determine if balance is debit or credit based on account type
        if account_type in ("asset", "expense"):
            # Normal debit balance accounts
            if balance >= 0:
                debit_balance = balance
                credit_balance = Decimal("0")
            else:
                # Negative balance means credit balance (unusual)
                debit_balance = Decimal("0")
                credit_balance = abs(balance)
        else:
            # Normal credit balance accounts (liability, equity, revenue)
            if balance >= 0:
                debit_balance = Decimal("0")
                credit_balance = balance
            else:
                # Negative balance means debit balance (unusual)
                debit_balance = abs(balance)
                credit_balance = Decimal("0")

        total_debits += debit_balance
        total_credits += credit_balance

        entries.append(
            TrialBalanceEntry(
                account_id=account.id,
                account_code=account.code,
                account_name=account.name,
                account_type=account.account_type,
                debit_balance=debit_balance,
                credit_balance=credit_balance,
            )
        )

    return TrialBalanceSummary(
        as_of_date=as_of_date,
        entries=entries,
        total_debits=total_debits,
        total_credits=total_credits,
        is_balanced=(total_debits == total_credits),
    )


# ---------------------------------------------------------------------------
# Financial Reports
# ---------------------------------------------------------------------------

def get_income_statement(
    db: Session,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Generate an Income Statement (Profit & Loss) for a period.

    The Income Statement shows:
    - Revenue: All revenue accounts (account_type = 'revenue')
    - Expenses: All expense accounts (account_type = 'expense')
    - Net Income: Total Revenue - Total Expenses

    Args:
        db: Database session
        start_date: Period start date
        end_date: Period end date

    Returns:
        Dictionary with revenue section, expense section, and net income
    """
    from backend.schemas.accounting import (
        IncomeStatement,
        IncomeStatementSection,
        IncomeStatementLineItem,
    )

    # Get all revenue and expense accounts
    revenue_accounts = (
        db.query(Account)
        .filter(Account.account_type == "revenue", Account.is_active == True)
        .order_by(Account.code)
        .all()
    )

    expense_accounts = (
        db.query(Account)
        .filter(Account.account_type == "expense", Account.is_active == True)
        .order_by(Account.code)
        .all()
    )

    # Calculate revenue from journal entries in the period
    revenue_items = []
    total_revenue = Decimal("0")
    for account in revenue_accounts:
        # Get credits minus debits for revenue accounts in the period
        period_amount = _get_account_period_balance(db, account.id, start_date, end_date)
        if period_amount != Decimal("0"):
            revenue_items.append(
                IncomeStatementLineItem(
                    account_id=account.id,
                    account_code=account.code,
                    account_name=account.name,
                    amount=period_amount,
                )
            )
            total_revenue += period_amount

    # Calculate expenses from journal entries in the period
    expense_items = []
    total_expenses = Decimal("0")
    for account in expense_accounts:
        # Get debits minus credits for expense accounts in the period
        period_amount = _get_account_period_balance(db, account.id, start_date, end_date)
        if period_amount != Decimal("0"):
            expense_items.append(
                IncomeStatementLineItem(
                    account_id=account.id,
                    account_code=account.code,
                    account_name=account.name,
                    amount=period_amount,
                )
            )
            total_expenses += period_amount

    net_income = total_revenue - total_expenses

    return IncomeStatement(
        report_title="Income Statement",
        period_start=start_date,
        period_end=end_date,
        revenue_section=IncomeStatementSection(
            section_name="Revenue",
            line_items=revenue_items,
            section_total=total_revenue,
        ),
        expense_section=IncomeStatementSection(
            section_name="Expenses",
            line_items=expense_items,
            section_total=total_expenses,
        ),
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_income=net_income,
    )


def _get_account_period_balance(
    db: Session,
    account_id: int,
    start_date: date,
    end_date: date,
) -> Decimal:
    """
    Calculate the net change in an account for a specific period.

    For revenue accounts: returns credits - debits (positive is good)
    For expense accounts: returns debits - credits (positive is expense)
    For asset accounts: returns debits - credits
    For liability/equity accounts: returns credits - debits
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return Decimal("0")

    # Get all posted journal entry lines for this account in the period
    lines = (
        db.query(JournalEntryLine)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .filter(
            JournalEntryLine.account_id == account_id,
            JournalEntry.status == "posted",
            JournalEntry.date >= start_date,
            JournalEntry.date <= end_date,
        )
        .all()
    )

    # Safely sum debits and credits with explicit Decimal conversion
    total_debit = sum(
        (Decimal(str(line.debit)) if line.debit is not None else Decimal("0"))
        for line in lines
    )
    total_credit = sum(
        (Decimal(str(line.credit)) if line.credit is not None else Decimal("0"))
        for line in lines
    )

    account_type = (account.account_type or "").lower()
    
    if account_type in ("asset", "expense"):
        # Debit balance accounts: debits increase, credits decrease
        return total_debit - total_credit
    else:
        # Credit balance accounts (liability, equity, revenue): credits increase, debits decrease
        return total_credit - total_debit


def get_balance_sheet(db: Session, as_of_date: date) -> dict:
    """
    Generate a Balance Sheet as of a specific date.

    The Balance Sheet shows:
    - Assets: All asset accounts
    - Liabilities: All liability accounts
    - Equity: All equity accounts (including retained earnings)

    The accounting equation: Assets = Liabilities + Equity

    Args:
        db: Database session
        as_of_date: Date for the balance sheet

    Returns:
        Dictionary with assets, liabilities, equity sections and totals
    """
    from backend.schemas.accounting import (
        BalanceSheet,
        BalanceSheetSection,
        BalanceSheetLineItem,
    )

    # Get all active accounts by type
    asset_accounts = (
        db.query(Account)
        .filter(Account.account_type == "asset", Account.is_active == True)
        .order_by(Account.code)
        .all()
    )

    liability_accounts = (
        db.query(Account)
        .filter(Account.account_type == "liability", Account.is_active == True)
        .order_by(Account.code)
        .all()
    )

    equity_accounts = (
        db.query(Account)
        .filter(Account.account_type == "equity", Account.is_active == True)
        .order_by(Account.code)
        .all()
    )

    # Build asset section
    asset_items = []
    total_assets = Decimal("0")
    for account in asset_accounts:
        balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
        if balance != Decimal("0"):
            asset_items.append(
                BalanceSheetLineItem(
                    account_id=account.id,
                    account_code=account.code,
                    account_name=account.name,
                    balance=balance,
                )
            )
            total_assets += balance

    # Build liability section
    liability_items = []
    total_liabilities = Decimal("0")
    for account in liability_accounts:
        balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
        if balance != Decimal("0"):
            liability_items.append(
                BalanceSheetLineItem(
                    account_id=account.id,
                    account_code=account.code,
                    account_name=account.name,
                    balance=balance,
                )
            )
            total_liabilities += balance

    # Build equity section (including retained earnings from P&L)
    equity_items = []
    total_equity = Decimal("0")
    for account in equity_accounts:
        balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
        if balance != Decimal("0"):
            equity_items.append(
                BalanceSheetLineItem(
                    account_id=account.id,
                    account_code=account.code,
                    account_name=account.name,
                    balance=balance,
                )
            )
            total_equity += balance

    # Calculate retained earnings (net income = revenue - expenses)
    revenue_accounts = db.query(Account).filter(
        Account.account_type == "revenue", Account.is_active == True
    ).all()
    expense_accounts = db.query(Account).filter(
        Account.account_type == "expense", Account.is_active == True
    ).all()

    total_revenue = sum(
        (Decimal(str(a.balance)) if a.balance is not None else Decimal("0"))
        for a in revenue_accounts
    )
    total_expenses = sum(
        (Decimal(str(a.balance)) if a.balance is not None else Decimal("0"))
        for a in expense_accounts
    )
    retained_earnings = total_revenue - total_expenses

    if retained_earnings != Decimal("0"):
        equity_items.append(
            BalanceSheetLineItem(
                account_id=0,  # Virtual account for retained earnings
                account_code="RE",
                account_name="Retained Earnings (Current Period)",
                balance=retained_earnings,
            )
        )
        total_equity += retained_earnings

    liabilities_and_equity = total_liabilities + total_equity
    is_balanced = (total_assets == liabilities_and_equity)

    return BalanceSheet(
        report_title="Balance Sheet",
        as_of_date=as_of_date,
        assets_section=BalanceSheetSection(
            section_name="Assets",
            line_items=asset_items,
            section_total=total_assets,
        ),
        liabilities_section=BalanceSheetSection(
            section_name="Liabilities",
            line_items=liability_items,
            section_total=total_liabilities,
        ),
        equity_section=BalanceSheetSection(
            section_name="Equity",
            line_items=equity_items,
            section_total=total_equity,
        ),
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity,
        liabilities_and_equity=liabilities_and_equity,
        is_balanced=is_balanced,
    )


def get_cash_flow_statement(
    db: Session,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Generate a Cash Flow Statement for a period.

    The Cash Flow Statement shows cash inflows and outflows divided into:
    - Operating activities: Day-to-day business operations
    - Investing activities: Purchase/sale of long-term assets
    - Financing activities: Debt and equity transactions

    This is a simplified direct method cash flow statement.

    Args:
        db: Database session
        start_date: Period start date
        end_date: Period end date

    Returns:
        Dictionary with operating, investing, financing sections and net cash flow
    """
    from backend.schemas.accounting import (
        CashFlowStatement,
        CashFlowSection,
        CashFlowLineItem,
    )

    # Get cash/bank account (code 1001 or similar)
    # Also include "1000" which is used in the seed data
    cash_account = db.query(Account).filter(
        Account.code.in_(["1000", "1001", "1100", "1110", "1120"])
    ).first()

    beginning_cash = Decimal("0")
    ending_cash = Decimal("0")

    if cash_account:
        # Calculate beginning cash balance
        beginning_lines = (
            db.query(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntryLine.account_id == cash_account.id,
                JournalEntry.status == "posted",
                JournalEntry.date < start_date,
            )
            .all()
        )
        for line in beginning_lines:
            safe_debit = Decimal(str(line.debit)) if line.debit is not None else Decimal("0")
            safe_credit = Decimal(str(line.credit)) if line.credit is not None else Decimal("0")
            beginning_cash += safe_debit - safe_credit

        # Calculate ending cash balance
        ending_lines = (
            db.query(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntryLine.account_id == cash_account.id,
                JournalEntry.status == "posted",
                JournalEntry.date <= end_date,
            )
            .all()
        )
        for line in ending_lines:
            safe_debit = Decimal(str(line.debit)) if line.debit is not None else Decimal("0")
            safe_credit = Decimal(str(line.credit)) if line.credit is not None else Decimal("0")
            ending_cash += safe_debit - safe_credit

    # Operating Activities - from revenue and expense accounts
    operating_items = []
    operating_total = Decimal("0")

    # Cash from revenue
    revenue_accounts = db.query(Account).filter(
        Account.account_type == "revenue", Account.is_active == True
    ).all()
    for account in revenue_accounts:
        period_amount = _get_account_period_balance(db, account.id, start_date, end_date)
        if period_amount != Decimal("0"):
            operating_items.append(
                CashFlowLineItem(
                    description=f"Cash from {account.name}",
                    amount=period_amount,
                )
            )
            operating_total += period_amount

    # Cash used for expenses
    expense_accounts = db.query(Account).filter(
        Account.account_type == "expense", Account.is_active == True
    ).all()
    for account in expense_accounts:
        period_amount = _get_account_period_balance(db, account.id, start_date, end_date)
        if period_amount != Decimal("0"):
            operating_items.append(
                CashFlowLineItem(
                    description=f"Cash paid for {account.name}",
                    amount=-period_amount,  # Negative because it's cash outflow
                )
            )
            operating_total -= period_amount

    # Investing Activities - fixed assets, long-term investments
    investing_items = []
    investing_total = Decimal("0")
    # Note: In a more complete implementation, this would identify
    # transactions related to fixed asset accounts

    # Financing Activities - equity and debt transactions
    financing_items = []
    financing_total = Decimal("0")
    # Note: In a more complete implementation, this would identify
    # transactions related to equity and loan accounts

    net_cash_flow = operating_total + investing_total + financing_total

    return CashFlowStatement(
        report_title="Cash Flow Statement",
        period_start=start_date,
        period_end=end_date,
        operating_activities=CashFlowSection(
            section_name="Operating Activities",
            line_items=operating_items,
            section_total=operating_total,
        ),
        investing_activities=CashFlowSection(
            section_name="Investing Activities",
            line_items=investing_items,
            section_total=investing_total,
        ),
        financing_activities=CashFlowSection(
            section_name="Financing Activities",
            line_items=financing_items,
            section_total=financing_total,
        ),
        net_cash_flow=net_cash_flow,
        beginning_cash=beginning_cash,
        ending_cash=ending_cash,
    )
