"""
Pydantic schemas for the Inventory module: item categories, warehouses,
items, stock ledger entries, warehouse stock, and stock valuation.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, computed_field


# ---------------------------------------------------------------------------
# Item Category
# ---------------------------------------------------------------------------

class ItemCategoryCreate(BaseModel):
    """Schema for creating an item category."""
    name: str
    description: Optional[str] = None


class ItemCategoryResponse(BaseModel):
    """Schema returned when reading an item category."""
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------

class WarehouseCreate(BaseModel):
    """Schema for creating a warehouse."""
    name: str
    location: Optional[str] = None


class WarehouseResponse(BaseModel):
    """Schema returned when reading a warehouse."""
    id: int
    name: str
    location: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class ItemCreate(BaseModel):
    """Schema for creating an inventory item."""
    code: str
    name: str
    description: Optional[str] = None
    unit_of_measure: str = "pcs"
    reorder_level: Decimal = Decimal("0")
    current_stock: Decimal = Decimal("0")
    unit_price: Decimal = Decimal("0")
    category_id: Optional[int] = None


class ItemResponse(BaseModel):
    """Schema returned when reading an inventory item."""
    id: int
    code: str
    name: str
    description: Optional[str] = None
    unit_of_measure: str
    reorder_level: Decimal
    current_stock: Decimal
    unit_price: Decimal
    category_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def stock_value(self) -> Decimal:
        """Calculated stock value = current_stock * unit_price"""
        return self.current_stock * self.unit_price

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Stock Ledger
# ---------------------------------------------------------------------------

class StockLedgerResponse(BaseModel):
    """Schema returned when reading a stock ledger entry."""
    id: int
    item_id: int
    warehouse_id: int
    transaction_type: str  # IN | OUT
    quantity: Decimal
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    balance_after: Decimal
    transaction_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Inventory Adjustment
# ---------------------------------------------------------------------------

class InventoryAdjustmentCreate(BaseModel):
    """
    Schema for creating an inventory adjustment.

    Adjustments automatically create journal entries:
    - Increase: Debit Inventory, Credit Inventory Adjustment Gain
    - Decrease: Debit Inventory Adjustment Loss, Credit Inventory
    """
    item_id: int
    warehouse_id: int
    adjustment_type: str  # "increase" or "decrease"
    quantity: Decimal
    reason: str
    unit_cost: Optional[Decimal] = None  # Uses item.unit_price if not provided


# ---------------------------------------------------------------------------
# Stock Transfer
# ---------------------------------------------------------------------------

class StockTransferCreate(BaseModel):
    """Schema for creating a stock transfer between warehouses."""
    item_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: Decimal
    reason: Optional[str] = None


class StockTransferResponse(BaseModel):
    """Response schema for stock transfer operation."""
    item_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: Decimal
    new_source_balance: Decimal
    new_dest_balance: Decimal
    message: str


# ---------------------------------------------------------------------------
# Warehouse Stock
# ---------------------------------------------------------------------------

class WarehouseStockResponse(BaseModel):
    """Schema for per-warehouse stock levels."""
    item_id: int
    item_code: str
    item_name: str
    warehouse_id: int
    warehouse_name: str
    quantity: Decimal
    unit_price: Decimal
    stock_value: Decimal

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Stock Valuation
# ---------------------------------------------------------------------------

class StockValuationItem(BaseModel):
    """Single item in stock valuation report."""
    item_id: int
    item_code: str
    item_name: str
    current_stock: Decimal
    unit_price: Decimal
    stock_value: Decimal


class StockValuationReport(BaseModel):
    """Complete stock valuation report."""
    items: List[StockValuationItem]
    total_value: Decimal
    total_items: int
