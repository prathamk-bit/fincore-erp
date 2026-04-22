"""
Procurement models.

Models:
    - Supplier: Vendor / supplier master record.
    - PurchaseOrder: Header for a purchase order.
    - PurchaseOrderItem: Individual line item on a purchase order.
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
# Supplier
# ---------------------------------------------------------------------------

class Supplier(Base):
    """
    Vendor / supplier master.

    Attributes:
        name: Legal or trading name.
        contact_person: Primary contact name.
        email: Contact email.
        phone: Contact phone number.
        address: Postal address.
        is_active: Soft-delete flag.
    """

    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    contact_person = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

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
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")

    def __repr__(self) -> str:
        return (
            f"<Supplier(id={self.id}, name='{self.name}')>"
        )


# ---------------------------------------------------------------------------
# PurchaseOrder (Header)
# ---------------------------------------------------------------------------

class PurchaseOrder(Base):
    """
    Purchase order header.

    Attributes:
        po_number: Unique sequential reference (e.g. 'PO-000001').
        supplier_id: FK to Supplier.
        order_date: Date the order was placed.
        expected_delivery_date: Planned delivery date.
        status: Lifecycle state ('draft', 'approved', 'received', 'cancelled').
        total_amount: Computed or cached sum of line totals.
        journal_entry_id: Optional FK to accounting journal entry.
    """

    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(
        String(30), unique=True, nullable=False, index=True
    )
    supplier_id = Column(
        Integer, ForeignKey("suppliers.id"), nullable=False, index=True
    )
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default="draft",
        comment="draft | approved | received | cancelled",
    )
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)

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
    supplier = relationship("Supplier", back_populates="purchase_orders")
    items = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )
    journal_entry = relationship(
        "JournalEntry", back_populates="purchase_orders"
    )

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrder(id={self.id}, po='{self.po_number}', "
            f"status='{self.status}', total={self.total_amount})>"
        )


# ---------------------------------------------------------------------------
# PurchaseOrderItem (Line Items)
# ---------------------------------------------------------------------------

class PurchaseOrderItem(Base):
    """
    Individual line item on a purchase order.

    Attributes:
        purchase_order_id: FK to PurchaseOrder header.
        item_id: FK to the inventory Item being purchased.
        quantity: Ordered quantity.
        received_quantity: Quantity received so far (for partial receipts).
        unit_price: Agreed purchase price per unit.
        total_price: quantity * unit_price.
    """

    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(
        Integer,
        ForeignKey("purchase_orders.id"),
        nullable=False,
        index=True,
    )
    item_id = Column(
        Integer, ForeignKey("items.id"), nullable=False, index=True
    )
    quantity = Column(Numeric(15, 3), nullable=False, default=0)
    received_quantity = Column(Numeric(15, 3), nullable=False, default=0)
    unit_price = Column(Numeric(15, 2), nullable=False, default=0)
    total_price = Column(Numeric(15, 2), nullable=False, default=0)

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
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    item = relationship("Item", back_populates="purchase_order_items")

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrderItem(id={self.id}, po_id={self.purchase_order_id}, "
            f"item_id={self.item_id}, qty={self.quantity}, "
            f"price={self.unit_price})>"
        )
