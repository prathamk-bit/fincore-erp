"""
Procurement service layer.

Provides business-logic functions for suppliers, purchase orders, and the
goods-receiving workflow with proper state transitions and partial receipts.

Purchase Order Workflow:
    Draft -> Approved -> Received (or Partially Received)

    - Draft: Initial state, can be edited
    - Approved: Ready for receiving, cannot be edited
    - Received: All items fully received (or status remains 'approved' for partial)

Receiving a purchase order:
    - Requires PO to be in 'approved' status
    - Supports partial receipts (received_quantity tracked per line item)
    - Validates: cannot receive more than ordered quantity
    - Updates ``current_stock`` on each ordered Item
    - Creates StockLedger IN entries for audit trail
    - Creates an accounting JournalEntry:
        * Debit  "1002" Inventory (asset)
        * Credit "2002" Accounts Payable (liability)

This module integrates with the central accounting service to ensure all
procurement transactions are properly recorded in the general ledger.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.inventory import Item, StockLedger, Warehouse
from backend.models.procurement import PurchaseOrder, PurchaseOrderItem, Supplier
from backend.schemas.procurement import PurchaseOrderCreate, ReceivePurchaseOrder, SupplierCreate
from backend.services.accounting_service import (
    create_journal_entry_from_module,
    JournalLine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_po_number(db: Session) -> str:
    """Generate the next sequential purchase-order number (PO-<id>)."""
    last = (
        db.query(PurchaseOrder)
        .order_by(PurchaseOrder.id.desc())
        .first()
    )
    next_id = (last.id + 1) if last else 1
    return f"PO-{next_id:06d}"


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

def create_supplier(db: Session, data: SupplierCreate) -> Supplier:
    """Create a new supplier record."""
    supplier = Supplier(
        name=data.name,
        contact_person=data.contact_person,
        email=data.email,
        phone=data.phone,
        address=data.address,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def get_suppliers(db: Session) -> List[Supplier]:
    """Return all suppliers."""
    return db.query(Supplier).order_by(Supplier.name).all()


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------

def create_purchase_order(
    db: Session, data: PurchaseOrderCreate
) -> PurchaseOrder:
    """
    Create a purchase order with its line items.

    Validates the supplier exists and each referenced item exists.
    Computes `total_price` per line item (quantity * unit_price) and the
    overall `total_amount` on the header.
    """
    # Validate supplier
    supplier = (
        db.query(Supplier).filter(Supplier.id == data.supplier_id).first()
    )
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with id {data.supplier_id} not found",
        )

    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase order must have at least one line item",
        )

    # Validate all referenced items exist
    item_ids = {line.item_id for line in data.items}
    existing_items = db.query(Item).filter(Item.id.in_(item_ids)).all()
    found_ids = {i.id for i in existing_items}
    missing = item_ids - found_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item(s) not found: {sorted(missing)}",
        )

    po_number = _next_po_number(db)

    # Build header
    purchase_order = PurchaseOrder(
        po_number=po_number,
        supplier_id=data.supplier_id,
        order_date=data.order_date,
        expected_delivery_date=data.expected_delivery_date,
        status="draft",
        total_amount=Decimal("0"),
    )

    # Build line items and compute totals
    total_amount = Decimal("0")
    for line_data in data.items:
        line_total = line_data.quantity * line_data.unit_price
        po_item = PurchaseOrderItem(
            item_id=line_data.item_id,
            quantity=line_data.quantity,
            unit_price=line_data.unit_price,
            total_price=line_total,
        )
        purchase_order.items.append(po_item)
        total_amount += line_total

    purchase_order.total_amount = total_amount

    db.add(purchase_order)
    db.commit()
    db.refresh(purchase_order)
    return purchase_order


def get_purchase_orders(db: Session) -> List[PurchaseOrder]:
    """Return all purchase orders ordered by date descending."""
    return (
        db.query(PurchaseOrder)
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
        .all()
    )


def get_purchase_order(db: Session, po_id: int) -> PurchaseOrder:
    """Return a single purchase order by ID or raise 404."""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase order with id {po_id} not found",
        )
    return po


# ---------------------------------------------------------------------------
# Approve Purchase Order
# ---------------------------------------------------------------------------

def approve_purchase_order(db: Session, po_id: int) -> PurchaseOrder:
    """
    Approve a draft purchase order.

    Only 'draft' POs can be approved. Once approved, a PO is ready
    for receiving goods.

    Raises:
        HTTPException: If PO not found or invalid state transition.
    """
    po = get_purchase_order(db, po_id)

    if po.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot approve purchase order. Current status is '{po.status}'. "
                f"Only 'draft' POs can be approved."
            ),
        )

    po.status = "approved"
    db.commit()
    db.refresh(po)
    return po


def cancel_purchase_order(db: Session, po_id: int) -> PurchaseOrder:
    """
    Cancel a purchase order.

    Only 'draft' or 'approved' POs can be cancelled.
    POs that have been partially or fully received cannot be cancelled.

    Raises:
        HTTPException: If PO not found or invalid state transition.
    """
    po = get_purchase_order(db, po_id)

    if po.status not in ["draft", "approved"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot cancel purchase order. Current status is '{po.status}'. "
                f"Only 'draft' or 'approved' POs can be cancelled."
            ),
        )

    # Check if any items have been received
    for po_item in po.items:
        if po_item.received_quantity > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot cancel purchase order. Item {po_item.item_id} has "
                    f"already received {po_item.received_quantity} units."
                ),
            )

    po.status = "cancelled"
    db.commit()
    db.refresh(po)
    return po


# ---------------------------------------------------------------------------
# Receive Purchase Order (with partial receipt support)
# ---------------------------------------------------------------------------

def receive_purchase_order(
    db: Session,
    po_id: int,
    warehouse_id: int,
    items: Optional[List[Dict]] = None,
) -> PurchaseOrder:
    """
    Receive goods for a purchase order (supports partial receipts).

    Steps:
        1. Validate the PO exists and is in 'approved' status.
        2. Validate the target warehouse exists.
        3. For each item being received:
           a. Validate quantity doesn't exceed remaining to receive.
           b. Update received_quantity on PO line item.
           c. Increase the Item's ``current_stock``.
           d. Create a StockLedger IN entry.
        4. If all items fully received, update PO status to 'received'.
        5. Create an accounting JournalEntry for the received amount:
           - Debit  "1002" Inventory       (asset)
           - Credit "2002" Accounts Payable (liability)
        6. Link the journal entry to the PO (first receipt only).

    Args:
        db: Database session
        po_id: Purchase order ID
        warehouse_id: Target warehouse ID
        items: Optional list of {po_item_id, quantity} dicts for partial receipt.
               If None, receives all remaining quantities.

    Raises:
        HTTPException: If validation fails or invalid state.
    """
    # --- 1. Validate PO ---
    po = get_purchase_order(db, po_id)

    if po.status == "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Purchase order {po.po_number} must be approved before receiving.",
        )
    if po.status == "received":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Purchase order {po.po_number} is already fully received.",
        )
    if po.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Purchase order {po.po_number} is cancelled and cannot be received.",
        )

    # --- 2. Validate warehouse ---
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found",
        )

    # --- 3. Build receive quantities map ---
    po_items_map = {poi.id: poi for poi in po.items}

    if items is None:
        # Receive all remaining quantities
        receive_qty: Dict[int, Decimal] = {}
        for poi in po.items:
            remaining = poi.quantity - (poi.received_quantity or Decimal("0"))
            if remaining > 0:
                receive_qty[poi.id] = remaining
    else:
        # Use specified quantities
        receive_qty = {}
        for item_data in items:
            poi_id = item_data.get("po_item_id")
            qty = Decimal(str(item_data.get("quantity", 0)))
            if poi_id not in po_items_map:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"PO item with id {poi_id} not found in this purchase order",
                )
            receive_qty[poi_id] = qty

    if not receive_qty or sum(receive_qty.values()) <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No items to receive",
        )

    # --- 4. Validate and process each item ---
    total_received_value = Decimal("0")

    for poi_id, qty_to_receive in receive_qty.items():
        if qty_to_receive <= 0:
            continue

        po_item = po_items_map[poi_id]
        # Safe Decimal conversions
        po_item_quantity = Decimal(str(po_item.quantity)) if po_item.quantity is not None else Decimal("0")
        po_item_received = Decimal(str(po_item.received_quantity)) if po_item.received_quantity is not None else Decimal("0")
        remaining = po_item_quantity - po_item_received

        if qty_to_receive > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot receive {qty_to_receive} units for item {po_item.item_id}. "
                    f"Only {remaining} remaining to receive "
                    f"(ordered: {po_item_quantity}, already received: {po_item_received})."
                ),
            )

        # Update received quantity
        po_item.received_quantity = po_item_received + qty_to_receive

        # Get inventory item
        item = db.query(Item).filter(Item.id == po_item.item_id).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with id {po_item.item_id} not found",
            )

        # Increase current stock (with safe Decimal conversion)
        current_item_stock = Decimal(str(item.current_stock)) if item.current_stock is not None else Decimal("0")
        item.current_stock = current_item_stock + qty_to_receive

        # Create stock ledger IN entry
        stock_entry = StockLedger(
            item_id=item.id,
            warehouse_id=warehouse_id,
            transaction_type="IN",
            quantity=qty_to_receive,
            reference_type="purchase_order",
            reference_id=po.id,
            balance_after=item.current_stock,
        )
        db.add(stock_entry)

        # Calculate value received (with safe Decimal conversion)
        unit_price = Decimal(str(po_item.unit_price)) if po_item.unit_price is not None else Decimal("0")
        total_received_value += qty_to_receive * unit_price

    # --- 5. Check if fully received ---
    all_received = all(
        (Decimal(str(poi.received_quantity)) if poi.received_quantity is not None else Decimal("0")) >= 
        (Decimal(str(poi.quantity)) if poi.quantity is not None else Decimal("0"))
        for poi in po.items
    )
    if all_received:
        po.status = "received"

    # --- 6. Create accounting journal entry ---
    if total_received_value > 0:
        receipt_description = (
            f"Goods received for {po.po_number}"
            if all_received
            else f"Partial receipt for {po.po_number}"
        )

        journal_entry = create_journal_entry_from_module(
            db=db,
            entry_date=date.today(),
            description=receipt_description,
            reference_type="purchase_order_receipt",
            reference_id=po.id,
            lines=[
                JournalLine(
                    account_code="1002",
                    account_name="Inventory",
                    account_type="asset",
                    debit=total_received_value,
                    credit=Decimal("0"),
                    description=f"Inventory received - {po.po_number}",
                ),
                JournalLine(
                    account_code="2002",
                    account_name="Accounts Payable",
                    account_type="liability",
                    debit=Decimal("0"),
                    credit=total_received_value,
                    description=f"Accounts payable - {po.po_number}",
                ),
            ],
            auto_post=True,
        )

        # Link first journal entry to PO
        if po.journal_entry_id is None:
            po.journal_entry_id = journal_entry.id

    db.commit()
    db.refresh(po)
    return po


# Legacy function for backwards compatibility
def receive_purchase_order_simple(
    db: Session, po_id: int, warehouse_id: int
) -> PurchaseOrder:
    """
    Receive all remaining items for a purchase order.

    This is the simple version that receives all quantities at once.
    For partial receipts, use receive_purchase_order with items parameter.
    """
    return receive_purchase_order(db, po_id, warehouse_id, items=None)
