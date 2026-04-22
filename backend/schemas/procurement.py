"""
Pydantic schemas for the Procurement module: suppliers, purchase orders,
and purchase order line items.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

class SupplierCreate(BaseModel):
    """Schema for creating a supplier."""
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SupplierResponse(BaseModel):
    """Schema returned when reading a supplier record."""
    id: int
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Purchase Order Item (line-level)
# ---------------------------------------------------------------------------

class PurchaseOrderItemCreate(BaseModel):
    """Schema for a single line item on a purchase order."""
    item_id: int
    quantity: Decimal
    unit_price: Decimal
    total_price: Optional[Decimal] = None


class PurchaseOrderItemResponse(BaseModel):
    """Schema returned when reading a purchase order line item."""
    id: int
    purchase_order_id: int
    item_id: int
    quantity: Decimal
    received_quantity: Decimal
    unit_price: Decimal
    total_price: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Receive Purchase Order (partial receipts)
# ---------------------------------------------------------------------------

class ReceiveItemQuantity(BaseModel):
    """Schema for specifying quantity to receive per PO line item."""
    po_item_id: int  # ID of the PurchaseOrderItem
    quantity: Decimal  # Quantity being received


class ReceivePurchaseOrder(BaseModel):
    """Schema for receiving a purchase order with specific quantities."""
    warehouse_id: int
    items: List[ReceiveItemQuantity]


# ---------------------------------------------------------------------------
# Purchase Order (header)
# ---------------------------------------------------------------------------

class PurchaseOrderCreate(BaseModel):
    """Schema for creating a purchase order with its line items."""
    supplier_id: int
    order_date: date
    expected_delivery_date: Optional[date] = None
    items: List[PurchaseOrderItemCreate]


class PurchaseOrderResponse(BaseModel):
    """Schema returned when reading a purchase order."""
    id: int
    po_number: str
    supplier_id: int
    order_date: date
    expected_delivery_date: Optional[date] = None
    status: str
    total_amount: Decimal
    journal_entry_id: Optional[int] = None
    items: List[PurchaseOrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
