"""
Finance models for cross-module financial transaction tracking.

Models:
    - FinancialTransaction: A ledger entry that can reference any source
      document across modules (payroll, purchase order, journal entry, etc.)
      via ``reference_type`` + ``reference_id``.

This table acts as a unified financial audit trail, allowing reports to
be generated across all modules without module-specific joins.
"""

from sqlalchemy import (
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
# FinancialTransaction
# ---------------------------------------------------------------------------

class FinancialTransaction(Base):
    """
    Unified financial transaction record for cross-module linking.

    Attributes:
        transaction_date: Effective date of the transaction.
        transaction_type: 'income' or 'expense'.
        category: Free-text category label (e.g. 'salary', 'office supplies').
        amount: Monetary value.
        description: Free-text narration.
        reference_type: Source document type (e.g. 'payroll', 'purchase_order').
        reference_id: PK in the referenced source table.
        journal_entry_id: Optional FK to the accounting journal entry.
    """

    __tablename__ = "financial_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_date = Column(Date, nullable=False)
    transaction_type = Column(
        String(20),
        nullable=False,
        comment="income | expense",
    )
    category = Column(String(100), nullable=True)
    amount = Column(Numeric(15, 2), nullable=False, default=0)
    description = Column(Text, nullable=True)

    # Cross-module polymorphic reference
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True, index=True)

    # Link to accounting journal entry
    journal_entry_id = Column(
        Integer, ForeignKey("journal_entries.id"), nullable=True
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
    journal_entry = relationship(
        "JournalEntry", back_populates="financial_transactions"
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialTransaction(id={self.id}, "
            f"type='{self.transaction_type}', amount={self.amount}, "
            f"ref={self.reference_type}:{self.reference_id})>"
        )
