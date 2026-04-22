"""
Inventory service layer.

Provides business-logic functions for item categories, warehouses,
inventory items, stock tracking, transfers, and valuation.

This module integrates with the central accounting service to ensure
inventory adjustments are properly recorded in the general ledger.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.inventory import Item, ItemCategory, StockLedger, Warehouse, WarehouseStock
from backend.schemas.inventory import ItemCategoryCreate, ItemCreate, WarehouseCreate
from backend.services.accounting_service import (
    create_journal_entry_from_module,
    JournalLine,
)


# ---------------------------------------------------------------------------
# Item Category
# ---------------------------------------------------------------------------

def create_category(db: Session, data: ItemCategoryCreate) -> ItemCategory:
    """Create a new item category."""
    existing = (
        db.query(ItemCategory).filter(ItemCategory.name == data.name).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item category '{data.name}' already exists",
        )

    category = ItemCategory(
        name=data.name,
        description=data.description,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def get_categories(db: Session) -> List[ItemCategory]:
    """Return all item categories."""
    return db.query(ItemCategory).order_by(ItemCategory.name).all()


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------

def create_warehouse(db: Session, data: WarehouseCreate) -> Warehouse:
    """Create a new warehouse."""
    existing = db.query(Warehouse).filter(Warehouse.name == data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Warehouse '{data.name}' already exists",
        )

    warehouse = Warehouse(
        name=data.name,
        location=data.location,
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def get_warehouses(db: Session) -> List[Warehouse]:
    """Return all warehouses."""
    return db.query(Warehouse).order_by(Warehouse.name).all()


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

def create_item(db: Session, data: ItemCreate) -> Item:
    """Create a new inventory item."""
    existing = db.query(Item).filter(Item.code == data.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item with code '{data.code}' already exists",
        )

    if data.category_id is not None:
        category = (
            db.query(ItemCategory)
            .filter(ItemCategory.id == data.category_id)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item category with id {data.category_id} not found",
            )

    item = Item(
        code=data.code,
        name=data.name,
        description=data.description,
        unit_of_measure=data.unit_of_measure,
        reorder_level=data.reorder_level,
        current_stock=data.current_stock,
        unit_price=data.unit_price,
        category_id=data.category_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_items(db: Session) -> List[Item]:
    """Return all inventory items."""
    return db.query(Item).order_by(Item.code).all()


def get_item(db: Session, item_id: int) -> Item:
    """Return a single inventory item by ID or raise 404."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )
    return item


def update_item(db: Session, item_id: int, data: ItemCreate) -> Item:
    """Update an existing inventory item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )

    # Check for code uniqueness if code is changing
    if data.code != item.code:
        existing = db.query(Item).filter(Item.code == data.code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item with code '{data.code}' already exists",
            )

    if data.category_id is not None:
        category = (
            db.query(ItemCategory)
            .filter(ItemCategory.id == data.category_id)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item category with id {data.category_id} not found",
            )

    item.code = data.code
    item.name = data.name
    item.description = data.description
    item.unit_of_measure = data.unit_of_measure
    item.reorder_level = data.reorder_level
    item.current_stock = data.current_stock
    item.unit_price = data.unit_price
    item.category_id = data.category_id

    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Stock & Stock Ledger
# ---------------------------------------------------------------------------

def get_stock(db: Session, item_id: int) -> Item:
    """
    Return the current stock information for a given item.

    This returns the full Item object which includes ``current_stock``.
    Raises 404 if the item does not exist.
    """
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )
    return item


def get_stock_ledger(
    db: Session,
    item_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> List[StockLedger]:
    """
    Return stock ledger entries, optionally filtered by item and/or warehouse.
    """
    query = db.query(StockLedger)

    if item_id is not None:
        query = query.filter(StockLedger.item_id == item_id)
    if warehouse_id is not None:
        query = query.filter(StockLedger.warehouse_id == warehouse_id)

    return query.order_by(StockLedger.transaction_date.desc(), StockLedger.id.desc()).all()


def get_low_stock_items(db: Session) -> List[Item]:
    """
    Return all items whose current stock is at or below their reorder level.

    This is used to generate low-stock alerts and trigger reorder workflows.
    """
    return (
        db.query(Item)
        .filter(Item.current_stock <= Item.reorder_level)
        .order_by(Item.code)
        .all()
    )


# ---------------------------------------------------------------------------
# Inventory Adjustment (with Journal Entry)
# ---------------------------------------------------------------------------

def adjust_inventory(
    db: Session,
    item_id: int,
    warehouse_id: int,
    adjustment_type: str,
    quantity: Decimal,
    reason: str,
    unit_cost: Optional[Decimal] = None,
) -> StockLedger:
    """
    Adjust inventory with corresponding journal entry.

    For increases (found stock, returns):
        - Debit: Inventory (1002) - asset
        - Credit: Inventory Adjustment Gain (4090) - revenue

    For decreases (shrinkage, damage, theft):
        - Debit: Inventory Adjustment Loss (5090) - expense
        - Credit: Inventory (1002) - asset

    Args:
        db: Database session
        item_id: ID of item being adjusted
        warehouse_id: ID of warehouse
        adjustment_type: "increase" or "decrease"
        quantity: Quantity being adjusted (always positive)
        reason: Reason for adjustment
        unit_cost: Cost per unit (uses item.unit_price if not provided)

    Returns:
        The created StockLedger entry

    Raises:
        HTTPException: If invalid adjustment_type, quantity, or insufficient stock
    """
    if adjustment_type not in ("increase", "decrease"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="adjustment_type must be 'increase' or 'decrease'",
        )

    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be positive",
        )

    # Validate item
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )

    # Validate warehouse
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found",
        )

    # Use provided cost or item's unit price (with safe Decimal conversion)
    if unit_cost is not None:
        cost_per_unit = Decimal(str(unit_cost))
    else:
        cost_per_unit = Decimal(str(item.unit_price)) if item.unit_price is not None else Decimal("0")
    
    safe_quantity = Decimal(str(quantity))
    total_value = safe_quantity * cost_per_unit

    # Update item stock (with safe Decimal conversion)
    current_stock = Decimal(str(item.current_stock)) if item.current_stock is not None else Decimal("0")

    if adjustment_type == "increase":
        item.current_stock = current_stock + safe_quantity
        transaction_type = "IN"
    else:  # decrease
        if current_stock < safe_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {current_stock}, Requested: {safe_quantity}",
            )
        item.current_stock = current_stock - safe_quantity
        transaction_type = "OUT"

    # Create stock ledger entry
    stock_entry = StockLedger(
        item_id=item_id,
        warehouse_id=warehouse_id,
        transaction_type=transaction_type,
        quantity=safe_quantity,
        reference_type="inventory_adjustment",
        reference_id=None,  # Will update after we have the ID
        balance_after=item.current_stock,
    )
    db.add(stock_entry)
    db.flush()  # Get stock_entry.id

    # Update reference_id to point to itself
    stock_entry.reference_id = stock_entry.id

    # Build journal entry lines based on adjustment type
    if adjustment_type == "increase":
        lines = [
            JournalLine(
                account_code="1002",
                account_name="Inventory",
                account_type="asset",
                debit=total_value,
                credit=Decimal("0"),
                description=f"Inventory adjustment (increase) - {item.code}: {reason}",
            ),
            JournalLine(
                account_code="4090",
                account_name="Inventory Adjustment Gain",
                account_type="revenue",
                debit=Decimal("0"),
                credit=total_value,
                description=f"Inventory gain - {item.code}: {reason}",
            ),
        ]
    else:  # decrease
        lines = [
            JournalLine(
                account_code="5090",
                account_name="Inventory Adjustment Loss",
                account_type="expense",
                debit=total_value,
                credit=Decimal("0"),
                description=f"Inventory loss - {item.code}: {reason}",
            ),
            JournalLine(
                account_code="1002",
                account_name="Inventory",
                account_type="asset",
                debit=Decimal("0"),
                credit=total_value,
                description=f"Inventory adjustment (decrease) - {item.code}: {reason}",
            ),
        ]

    # Create journal entry via centralized service
    create_journal_entry_from_module(
        db=db,
        entry_date=date.today(),
        description=f"Inventory adjustment for {item.code} - {reason}",
        reference_type="inventory_adjustment",
        reference_id=stock_entry.id,
        lines=lines,
    )

    db.commit()
    db.refresh(stock_entry)
    return stock_entry


# ---------------------------------------------------------------------------
# Stock Transfer (between warehouses)
# ---------------------------------------------------------------------------

def get_or_create_warehouse_stock(
    db: Session, item_id: int, warehouse_id: int
) -> WarehouseStock:
    """Get or create a WarehouseStock record for item-warehouse pair."""
    ws = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.item_id == item_id,
            WarehouseStock.warehouse_id == warehouse_id,
        )
        .first()
    )
    if not ws:
        ws = WarehouseStock(
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity=Decimal("0"),
        )
        db.add(ws)
        db.flush()
    return ws


def transfer_stock(
    db: Session,
    item_id: int,
    from_warehouse_id: int,
    to_warehouse_id: int,
    quantity: Decimal,
    reason: Optional[str] = None,
) -> Dict:
    """
    Transfer stock from one warehouse to another.

    This does NOT create a journal entry since it's an internal movement
    that doesn't change the total inventory value.

    Args:
        db: Database session
        item_id: ID of item being transferred
        from_warehouse_id: Source warehouse ID
        to_warehouse_id: Destination warehouse ID
        quantity: Quantity to transfer (positive)
        reason: Optional reason for transfer

    Returns:
        Dict with transfer details and new balances

    Raises:
        HTTPException: If invalid quantity, insufficient stock, or invalid warehouses
    """
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be positive",
        )

    if from_warehouse_id == to_warehouse_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination warehouse must be different",
        )

    # Validate item
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )

    # Validate warehouses
    from_warehouse = db.query(Warehouse).filter(Warehouse.id == from_warehouse_id).first()
    if not from_warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source warehouse with id {from_warehouse_id} not found",
        )

    to_warehouse = db.query(Warehouse).filter(Warehouse.id == to_warehouse_id).first()
    if not to_warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination warehouse with id {to_warehouse_id} not found",
        )

    # Get or create warehouse stock records
    source_ws = get_or_create_warehouse_stock(db, item_id, from_warehouse_id)
    dest_ws = get_or_create_warehouse_stock(db, item_id, to_warehouse_id)

    # Validate sufficient stock
    if source_ws.quantity < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient stock in source warehouse. "
                f"Available: {source_ws.quantity}, Requested: {quantity}"
            ),
        )

    # Update warehouse stock levels
    source_ws.quantity -= quantity
    dest_ws.quantity += quantity

    # Create stock ledger entries
    transfer_reason = reason or "Stock transfer"

    # OUT entry for source warehouse
    out_entry = StockLedger(
        item_id=item_id,
        warehouse_id=from_warehouse_id,
        transaction_type="TRANSFER",
        quantity=quantity,
        reference_type="transfer_out",
        reference_id=to_warehouse_id,
        balance_after=source_ws.quantity,
    )
    db.add(out_entry)

    # IN entry for destination warehouse
    in_entry = StockLedger(
        item_id=item_id,
        warehouse_id=to_warehouse_id,
        transaction_type="TRANSFER",
        quantity=quantity,
        reference_type="transfer_in",
        reference_id=from_warehouse_id,
        balance_after=dest_ws.quantity,
    )
    db.add(in_entry)

    db.commit()

    return {
        "item_id": item_id,
        "from_warehouse_id": from_warehouse_id,
        "to_warehouse_id": to_warehouse_id,
        "quantity": quantity,
        "new_source_balance": source_ws.quantity,
        "new_dest_balance": dest_ws.quantity,
        "message": f"Transferred {quantity} of {item.code} from {from_warehouse.name} to {to_warehouse.name}",
    }


# ---------------------------------------------------------------------------
# Per-Warehouse Stock Queries
# ---------------------------------------------------------------------------

def get_warehouse_stock(
    db: Session,
    item_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> List[Dict]:
    """
    Get per-warehouse stock levels.

    If item_id is provided, returns stock for that item across all warehouses.
    If warehouse_id is provided, returns all items in that warehouse.
    If neither is provided, returns all warehouse stock records.
    """
    query = db.query(WarehouseStock).filter(WarehouseStock.quantity > 0)

    if item_id is not None:
        query = query.filter(WarehouseStock.item_id == item_id)
    if warehouse_id is not None:
        query = query.filter(WarehouseStock.warehouse_id == warehouse_id)

    results = []
    for ws in query.all():
        item = db.query(Item).filter(Item.id == ws.item_id).first()
        warehouse = db.query(Warehouse).filter(Warehouse.id == ws.warehouse_id).first()
        if item and warehouse:
            results.append({
                "item_id": ws.item_id,
                "item_code": item.code,
                "item_name": item.name,
                "warehouse_id": ws.warehouse_id,
                "warehouse_name": warehouse.name,
                "quantity": ws.quantity,
                "unit_price": item.unit_price,
                "stock_value": ws.quantity * item.unit_price,
            })

    return results


# ---------------------------------------------------------------------------
# Stock Valuation
# ---------------------------------------------------------------------------

def get_stock_valuation(db: Session) -> Dict:
    """
    Get stock valuation report for all items.

    Returns total inventory value calculated as sum of (current_stock * unit_price)
    for all items.
    """
    items = db.query(Item).filter(Item.current_stock > 0).order_by(Item.code).all()

    valuation_items = []
    total_value = Decimal("0")

    for item in items:
        # Safe Decimal conversion
        current_stock = Decimal(str(item.current_stock)) if item.current_stock is not None else Decimal("0")
        unit_price = Decimal(str(item.unit_price)) if item.unit_price is not None else Decimal("0")
        stock_value = current_stock * unit_price
        total_value += stock_value

        valuation_items.append({
            "item_id": item.id,
            "item_code": item.code,
            "item_name": item.name,
            "current_stock": current_stock,
            "unit_price": unit_price,
            "stock_value": stock_value,
        })

    return {
        "items": valuation_items,
        "total_value": total_value,
        "total_items": len(valuation_items),
    }
