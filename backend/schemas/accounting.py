"""
Pydantic schemas for the Accounting module: chart of accounts, journal entries,
journal entry lines, and ledger views.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Account (Chart of Accounts)
# ---------------------------------------------------------------------------

class AccountCreate(BaseModel):
    """Schema for creating a new account in the Chart of Accounts."""
    code: str
    name: str
    account_type: str  # asset | liability | equity | revenue | expense
    parent_account_id: Optional[int] = None


class AccountResponse(BaseModel):
    """Schema returned when reading an account."""
    id: int
    code: str
    name: str
    account_type: str
    balance: Decimal
    is_active: bool
    parent_account_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Journal Entry Line
# ---------------------------------------------------------------------------

class JournalEntryLineCreate(BaseModel):
    """Schema for a single debit/credit line within a journal entry."""
    account_id: int
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: Optional[str] = None


class JournalEntryLineResponse(BaseModel):
    """Schema returned for a journal entry line."""
    id: int
    journal_entry_id: int
    account_id: int
    debit: Decimal
    credit: Decimal
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Journal Entry (Header)
# ---------------------------------------------------------------------------

class JournalEntryCreate(BaseModel):
    """Schema for creating a journal entry with its lines."""
    date: date
    description: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    lines: List[JournalEntryLineCreate]


class JournalEntryUpdate(BaseModel):
    """Schema for updating a draft journal entry."""
    date: Optional[date] = None
    description: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    lines: Optional[List[JournalEntryLineCreate]] = None


class JournalEntryResponse(BaseModel):
    """Schema returned when reading a journal entry."""
    id: int
    entry_number: str
    date: date
    description: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    status: str  # draft | posted
    total_debit: Decimal
    total_credit: Decimal
    lines: List[JournalEntryLineResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Ledger Entry (read-only view)
# ---------------------------------------------------------------------------

class LedgerEntry(BaseModel):
    """
    Flattened ledger-view schema combining journal entry header data
    with individual line-item postings for a given account.
    """
    journal_entry_id: int
    entry_number: str
    date: date
    description: Optional[str] = None
    status: str  # draft | posted
    account_id: int
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    balance: Decimal

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Trial Balance
# ---------------------------------------------------------------------------

class TrialBalanceEntry(BaseModel):
    """Single row in the trial balance report."""
    account_id: int
    account_code: str
    account_name: str
    account_type: str
    debit_balance: Decimal
    credit_balance: Decimal

    model_config = ConfigDict(from_attributes=True)


class TrialBalanceSummary(BaseModel):
    """Complete trial balance report."""
    as_of_date: date
    entries: List[TrialBalanceEntry]
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool


# ---------------------------------------------------------------------------
# Income Statement (Profit & Loss)
# ---------------------------------------------------------------------------

class IncomeStatementLineItem(BaseModel):
    """Single account line in the income statement."""
    account_id: int
    account_code: str
    account_name: str
    amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class IncomeStatementSection(BaseModel):
    """A section (Revenue or Expenses) in the income statement."""
    section_name: str
    line_items: List[IncomeStatementLineItem]
    section_total: Decimal

    model_config = ConfigDict(from_attributes=True)


class IncomeStatement(BaseModel):
    """
    Complete Income Statement (Profit & Loss) report.

    Shows revenues and expenses for a period, resulting in net income.
    """
    report_title: str = "Income Statement"
    period_start: date
    period_end: date
    revenue_section: IncomeStatementSection
    expense_section: IncomeStatementSection
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal  # Revenue - Expenses (positive = profit, negative = loss)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Balance Sheet
# ---------------------------------------------------------------------------

class BalanceSheetLineItem(BaseModel):
    """Single account line in the balance sheet."""
    account_id: int
    account_code: str
    account_name: str
    balance: Decimal

    model_config = ConfigDict(from_attributes=True)


class BalanceSheetSection(BaseModel):
    """A section (Assets, Liabilities, or Equity) in the balance sheet."""
    section_name: str
    line_items: List[BalanceSheetLineItem]
    section_total: Decimal

    model_config = ConfigDict(from_attributes=True)


class BalanceSheet(BaseModel):
    """
    Complete Balance Sheet report.

    Shows Assets, Liabilities, and Equity as of a specific date.
    Assets = Liabilities + Equity (the accounting equation).
    """
    report_title: str = "Balance Sheet"
    as_of_date: date
    assets_section: BalanceSheetSection
    liabilities_section: BalanceSheetSection
    equity_section: BalanceSheetSection
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    liabilities_and_equity: Decimal  # total_liabilities + total_equity
    is_balanced: bool  # True if total_assets == liabilities_and_equity

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Cash Flow Statement
# ---------------------------------------------------------------------------

class CashFlowLineItem(BaseModel):
    """Single line item in a cash flow section."""
    description: str
    amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class CashFlowSection(BaseModel):
    """A section in the cash flow statement."""
    section_name: str
    line_items: List[CashFlowLineItem]
    section_total: Decimal

    model_config = ConfigDict(from_attributes=True)


class CashFlowStatement(BaseModel):
    """
    Complete Cash Flow Statement report.

    Shows cash inflows and outflows divided into:
    - Operating activities
    - Investing activities
    - Financing activities
    """
    report_title: str = "Cash Flow Statement"
    period_start: date
    period_end: date
    operating_activities: CashFlowSection
    investing_activities: CashFlowSection
    financing_activities: CashFlowSection
    net_cash_flow: Decimal
    beginning_cash: Decimal
    ending_cash: Decimal

    model_config = ConfigDict(from_attributes=True)
