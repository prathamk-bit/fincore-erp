"""
API routes for the Procurement module.

Endpoints:
    POST /api/procurement/suppliers                    - Create a supplier.
    GET  /api/procurement/suppliers                    - List all suppliers.
    POST /api/procurement/purchase-orders              - Create a purchase order (draft).
    GET  /api/procurement/purchase-orders              - List all purchase orders.
    GET  /api/procurement/purchase-orders/{id}         - Get a single purchase order.
    POST /api/procurement/purchase-orders/{id}/approve - Approve a draft purchase order.
    POST /api/procurement/purchase-orders/{id}/cancel  - Cancel a purchase order.
    POST /api/procurement/purchase-orders/{id}/receive - Receive goods (full or partial).
"""

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from backend.auth.auth import role_required
from backend.models.database import get_db
from backend.models.user import User
from backend.schemas.procurement import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    ReceivePurchaseOrder,
    SupplierCreate,
    SupplierResponse,
)
from backend.services.procurement_service import (
    approve_purchase_order,
    cancel_purchase_order,
    create_purchase_order,
    create_supplier,
    get_purchase_order,
    get_purchase_orders,
    get_suppliers,
    receive_purchase_order,
)

router = APIRouter(prefix="/api/procurement", tags=["Procurement"])

ALLOWED_ROLES = ["admin", "inventory_manager"]


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_route(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """Create a new supplier."""
    return create_supplier(db, data)


@router.get("/suppliers", response_model=List[SupplierResponse])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """List all suppliers."""
    return get_suppliers(db)


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------

@router.post("/purchase-orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order_route(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """Create a new purchase order with its line items."""
    return create_purchase_order(db, data)


@router.get("/purchase-orders", response_model=List[PurchaseOrderResponse])
def list_purchase_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """List all purchase orders."""
    return get_purchase_orders(db)


@router.get("/purchase-orders/{id}", response_model=PurchaseOrderResponse)
def get_purchase_order_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """Get a single purchase order by ID."""
    return get_purchase_order(db, id)


# ---------------------------------------------------------------------------
# Purchase Order Workflow
# ---------------------------------------------------------------------------

@router.post("/purchase-orders/{id}/approve", response_model=PurchaseOrderResponse)
def approve_purchase_order_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """
    Approve a draft purchase order.

    Only 'draft' POs can be approved. Once approved, a PO is ready
    for receiving goods.
    """
    return approve_purchase_order(db, id)


@router.post("/purchase-orders/{id}/cancel", response_model=PurchaseOrderResponse)
def cancel_purchase_order_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """
    Cancel a purchase order.

    Only 'draft' or 'approved' POs (with no received items) can be cancelled.
    """
    return cancel_purchase_order(db, id)


# ---------------------------------------------------------------------------
# Receive Purchase Order
# ---------------------------------------------------------------------------

@router.post("/purchase-orders/{id}/receive", response_model=PurchaseOrderResponse)
def receive_purchase_order_route(
    id: int,
    warehouse_id: int = Query(..., description="The warehouse ID to receive goods into"),
    data: Optional[ReceivePurchaseOrder] = Body(None, description="Optional partial receipt data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """
    Receive goods for a purchase order (supports partial receipts).

    This requires the PO to be in 'approved' status.

    If no body is provided, all remaining items are received.
    For partial receipts, provide a list of items with quantities to receive.

    Updates item stock, creates stock ledger entries, and records
    the corresponding accounting journal entry.
    """
    items = None
    if data and data.items:
        items = [{"po_item_id": item.po_item_id, "quantity": item.quantity} for item in data.items]
        warehouse_id = data.warehouse_id

    return receive_purchase_order(db, id, warehouse_id, items=items)
