"""
Inventory management models.

Models:
    - ItemCategory: Grouping / classification for inventory items.
    - Warehouse: Physical storage location.
    - Item: Individual SKU / product.
    - StockLedger: Log of every stock movement providing a full audit trail.
"""

from sqlalchemy import (
    Boolean,
    Column,
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
# ItemCategory
# ---------------------------------------------------------------------------

class ItemCategory(Base):
    """
    Grouping for inventory items (e.g. Raw Materials, Finished Goods).

    Attributes:
        name: Unique category name.
        description: Optional notes.
    """

    __tablename__ = "item_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
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
    items = relationship("Item", back_populates="category")

    def __repr__(self) -> str:
        return f"<ItemCategory(id={self.id}, name='{self.name}')>"


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------

class Warehouse(Base):
    """
    Physical storage location.

    Attributes:
        name: Unique warehouse name.
        location: Free-text address or location descriptor.
        is_active: Soft-delete flag.
    """

    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    location = Column(Text, nullable=True)
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
    stock_entries = relationship("StockLedger", back_populates="warehouse")

    def __repr__(self) -> str:
        return f"<Warehouse(id={self.id}, name='{self.name}')>"


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class Item(Base):
    """
    Individual inventory item / SKU.

    Attributes:
        code: Unique human-readable code (e.g. 'ITM-001').
        name: Short descriptive name.
        description: Long description.
        category_id: FK to ItemCategory.
        unit_of_measure: e.g. 'pcs', 'kg', 'litre'.
        reorder_level: Minimum stock level before reorder is triggered.
        current_stock: Current on-hand quantity.
        unit_price: Standard purchase / cost price.
    """

    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    unit_of_measure = Column(String(20), nullable=False, default="pcs")
    reorder_level = Column(Numeric(15, 2), nullable=False, default=0)
    current_stock = Column(Numeric(15, 2), nullable=False, default=0)
    unit_price = Column(Numeric(15, 2), nullable=False, default=0)

    category_id = Column(
        Integer, ForeignKey("item_categories.id"), nullable=True
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
    category = relationship("ItemCategory", back_populates="items")
    stock_entries = relationship("StockLedger", back_populates="item")
    purchase_order_items = relationship(
        "PurchaseOrderItem", back_populates="item"
    )

    def __repr__(self) -> str:
        return (
            f"<Item(id={self.id}, code='{self.code}', "
            f"name='{self.name}')>"
        )


# ---------------------------------------------------------------------------
# StockLedger
# ---------------------------------------------------------------------------

class StockLedger(Base):
    """
    Record of a stock movement event.

    Attributes:
        item_id: FK to the Item that moved.
        warehouse_id: FK to the Warehouse where the movement occurred.
        transaction_type: 'IN', 'OUT', or 'TRANSFER'.
        quantity: Quantity moved (always positive; type determines direction).
        reference_type: Source document type (e.g. 'purchase_order', 'transfer').
        reference_id: PK of the source document.
        balance_after: Stock balance after this transaction (total across all warehouses).
        transaction_date: Date/time of the movement.
    """

    __tablename__ = "stock_ledger"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(
        Integer, ForeignKey("items.id"), nullable=False, index=True
    )
    warehouse_id = Column(
        Integer, ForeignKey("warehouses.id"), nullable=False, index=True
    )
    transaction_type = Column(
        String(10),
        nullable=False,
        comment="IN | OUT | TRANSFER",
    )
    quantity = Column(Numeric(15, 2), nullable=False)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True, index=True)
    balance_after = Column(Numeric(15, 2), nullable=False, default=0)
    transaction_date = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
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
    item = relationship("Item", back_populates="stock_entries")
    warehouse = relationship("Warehouse", back_populates="stock_entries")

    def __repr__(self) -> str:
        return (
            f"<StockLedger(id={self.id}, item_id={self.item_id}, "
            f"wh={self.warehouse_id}, type='{self.transaction_type}', "
            f"qty={self.quantity})>"
        )


# ---------------------------------------------------------------------------
# WarehouseStock (Per-warehouse stock tracking)
# ---------------------------------------------------------------------------

class WarehouseStock(Base):
    """
    Tracks quantity of each item per warehouse.

    Attributes:
        item_id: FK to Item.
        warehouse_id: FK to Warehouse.
        quantity: Current quantity in this warehouse.
    """

    __tablename__ = "warehouse_stock"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(
        Integer, ForeignKey("items.id"), nullable=False, index=True
    )
    warehouse_id = Column(
        Integer, ForeignKey("warehouses.id"), nullable=False, index=True
    )
    quantity = Column(Numeric(15, 2), nullable=False, default=0)

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
    item = relationship("Item", backref="warehouse_stocks")
    warehouse = relationship("Warehouse", backref="warehouse_stocks")

    def __repr__(self) -> str:
        return (
            f"<WarehouseStock(id={self.id}, item_id={self.item_id}, "
            f"warehouse_id={self.warehouse_id}, qty={self.quantity})>"
        )
