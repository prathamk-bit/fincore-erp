"""
Accounting models implementing double-entry bookkeeping.

Models:
    - Account: Chart of Accounts node (self-referential hierarchy).
    - JournalEntry: Header for a set of balanced debit/credit lines.
    - JournalEntryLine: Individual debit or credit posting against an Account.

Design notes:
    Every JournalEntry must have lines whose total debits equal total credits
    (enforced at the application / service layer).
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
# Account (Chart of Accounts)
# ---------------------------------------------------------------------------

class Account(Base):
    """
    A node in the Chart of Accounts.

    Supports an arbitrary-depth parent-child hierarchy via
    ``parent_account_id`` (self-referential foreign key).

    Attributes:
        code: Unique human-readable code (e.g. '1000', '2100').
        name: Descriptive account name.
        account_type: One of 'asset', 'liability', 'equity', 'revenue', 'expense'.
        parent_account_id: FK to parent Account (nullable for root accounts).
        balance: Current account balance.
        is_active: Soft-delete / deactivation flag.
    """

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    account_type = Column(
        String(20),
        nullable=False,
        comment="asset | liability | equity | revenue | expense",
    )
    balance = Column(Numeric(15, 2), nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)

    # Self-referential hierarchy
    parent_account_id = Column(
        Integer, ForeignKey("accounts.id"), nullable=True
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
    parent = relationship(
        "Account", remote_side="Account.id", back_populates="children"
    )
    children = relationship(
        "Account", back_populates="parent"
    )
    journal_lines = relationship("JournalEntryLine", back_populates="account")

    def __repr__(self) -> str:
        return (
            f"<Account(id={self.id}, code='{self.code}', "
            f"name='{self.name}', type='{self.account_type}')>"
        )


# ---------------------------------------------------------------------------
# JournalEntry (Header)
# ---------------------------------------------------------------------------

class JournalEntry(Base):
    """
    Header record for a double-entry journal posting.

    Attributes:
        entry_number: Unique sequential reference (e.g. 'JE-000001').
        date: Accounting date of the entry.
        description: Memo / narration.
        reference_type: Source document type (e.g. 'payroll', 'purchase_order').
        reference_id: PK in the referenced source table.
        status: Entry status - 'draft' (editable, no ledger impact) or 'posted' (immutable, affects balances).
        total_debit: Sum of all debit amounts on the lines.
        total_credit: Sum of all credit amounts on the lines.
    """

    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    entry_number = Column(
        String(30), unique=True, nullable=False, index=True
    )
    date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True, index=True)
    status = Column(
        String(20),
        nullable=False,
        default="draft",
        comment="draft | posted",
    )
    total_debit = Column(Numeric(15, 2), nullable=False, default=0)
    total_credit = Column(Numeric(15, 2), nullable=False, default=0)

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
    lines = relationship(
        "JournalEntryLine",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
    )
    payrolls = relationship("Payroll", back_populates="journal_entry")
    financial_transactions = relationship(
        "FinancialTransaction", back_populates="journal_entry"
    )
    purchase_orders = relationship(
        "PurchaseOrder", back_populates="journal_entry"
    )

    def __repr__(self) -> str:
        return (
            f"<JournalEntry(id={self.id}, number='{self.entry_number}', "
            f"date={self.date}, status='{self.status}')>"
        )


# ---------------------------------------------------------------------------
# JournalEntryLine (Line Items)
# ---------------------------------------------------------------------------

class JournalEntryLine(Base):
    """
    A single debit or credit line within a JournalEntry.

    Exactly one of ``debit`` or ``credit`` should be non-zero for each line.

    Attributes:
        journal_entry_id: FK to JournalEntry header.
        account_id: FK to Account being posted to.
        debit: Debit amount (0 if this is a credit line).
        credit: Credit amount (0 if this is a debit line).
        description: Optional line-level narration.
    """

    __tablename__ = "journal_entry_lines"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(
        Integer, ForeignKey("journal_entries.id"), nullable=False, index=True
    )
    account_id = Column(
        Integer, ForeignKey("accounts.id"), nullable=False, index=True
    )
    debit = Column(Numeric(15, 2), nullable=False, default=0)
    credit = Column(Numeric(15, 2), nullable=False, default=0)
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
    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account", back_populates="journal_lines")

    def __repr__(self) -> str:
        return (
            f"<JournalEntryLine(id={self.id}, account_id={self.account_id}, "
            f"debit={self.debit}, credit={self.credit})>"
        )
