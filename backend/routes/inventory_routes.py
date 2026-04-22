"""
API routes for the Inventory module.

Endpoints:
    POST /api/inventory/categories       - Create an item category.
    GET  /api/inventory/categories       - List all item categories.
    POST /api/inventory/warehouses       - Create a warehouse.
    GET  /api/inventory/warehouses       - List all warehouses.
    POST /api/inventory/items            - Create an inventory item.
    GET  /api/inventory/items            - List all inventory items.
    GET  /api/inventory/items/{id}       - Get a single inventory item.
    PUT  /api/inventory/items/{id}       - Update an inventory item.
    GET  /api/inventory/stock            - Get current stock for an item.
    GET  /api/inventory/stock-ledger     - Get stock ledger entries.
    GET  /api/inventory/low-stock        - Get items at or below reorder level.
    POST /api/inventory/adjustments      - Create inventory adjustment with journal entry.
    POST /api/inventory/transfers        - Transfer stock between warehouses.
    GET  /api/inventory/warehouse-stock  - Get per-warehouse stock levels.
    GET  /api/inventory/valuation        - Get stock valuation report.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.auth.auth import role_required
from backend.models.database import get_db
from backend.models.user import User
from backend.schemas.inventory import (
    InventoryAdjustmentCreate,
    ItemCategoryCreate,
    ItemCategoryResponse,
    ItemCreate,
    ItemResponse,
    StockLedgerResponse,
    StockTransferCreate,
    StockTransferResponse,
    StockValuationReport,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseStockResponse,
)
from backend.services.inventory_service import (
    adjust_inventory,
    create_category,
    create_item,
    create_warehouse,
    get_categories,
    get_item,
    get_items,
    get_low_stock_items,
    get_stock,
    get_stock_ledger,
    get_stock_valuation,
    get_warehouse_stock,
    get_warehouses,
    transfer_stock,
    update_item,
)

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])

ALLOWED_ROLES = ["admin", "inventory_manager"]


# ---------------------------------------------------------------------------
# Item Categories
# ---------------------------------------------------------------------------

@router.post("/categories", response_model=ItemCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category_route(
    data: ItemCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """Create a new item category."""
    return create_category(db, data)


@router.get("/categories", response_model=List[ItemCategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """List all item categories. Accountants have read-only access for financial reporting."""
    return get_categories(db)


# ---------------------------------------------------------------------------
# Warehouses
# ---------------------------------------------------------------------------

@router.post("/warehouses", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse_route(
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """Create a new warehouse."""
    return create_warehouse(db, data)


@router.get("/warehouses", response_model=List[WarehouseResponse])
def list_warehouses(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """List all warehouses. Accountants have read-only access for financial reporting."""
    return get_warehouses(db)


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@router.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item_route(
    data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """Create a new inventory item."""
    return create_item(db, data)


@router.get("/items", response_model=List[ItemResponse])
def list_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """List all inventory items. Accountants have read-only access for financial reporting."""
    return get_items(db)


@router.get("/items/{id}", response_model=ItemResponse)
def get_item_route(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """Get a single inventory item by ID. Accountants have read-only access."""
    return get_item(db, id)


@router.put("/items/{id}", response_model=ItemResponse)
def update_item_route(
    id: int,
    data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """Update an existing inventory item."""
    return update_item(db, id, data)


# ---------------------------------------------------------------------------
# Stock & Stock Ledger
# ---------------------------------------------------------------------------

@router.get("/stock", response_model=ItemResponse)
def get_stock_route(
    item_id: int = Query(..., description="The ID of the item to check stock for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """Get the current stock information for a specific item. Accountants have read-only access."""
    return get_stock(db, item_id)


@router.get("/stock-ledger", response_model=List[StockLedgerResponse])
def get_stock_ledger_route(
    item_id: Optional[int] = Query(None, description="Filter by item ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """Get stock ledger entries, optionally filtered by item and/or warehouse. Accountants have read-only access."""
    return get_stock_ledger(db, item_id=item_id, warehouse_id=warehouse_id)


# ---------------------------------------------------------------------------
# Low Stock Alerts
# ---------------------------------------------------------------------------

@router.get("/low-stock", response_model=List[ItemResponse])
def get_low_stock_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """Get all items whose current stock is at or below their reorder level. Accountants have read-only access."""
    return get_low_stock_items(db)


# ---------------------------------------------------------------------------
# Inventory Adjustments
# ---------------------------------------------------------------------------

@router.post("/adjustments", response_model=StockLedgerResponse, status_code=status.HTTP_201_CREATED)
def create_inventory_adjustment(
    data: InventoryAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """
    Create an inventory adjustment with corresponding journal entry.

    Use adjustment_type='increase' for found stock, returns, etc.
    Use adjustment_type='decrease' for shrinkage, damage, theft, etc.

    The adjustment will automatically:
    - Update the item's current stock
    - Create a stock ledger entry
    - Create a journal entry for proper accounting
    """
    return adjust_inventory(
        db=db,
        item_id=data.item_id,
        warehouse_id=data.warehouse_id,
        adjustment_type=data.adjustment_type,
        quantity=data.quantity,
        reason=data.reason,
        unit_cost=data.unit_cost,
    )


# ---------------------------------------------------------------------------
# Stock Transfers
# ---------------------------------------------------------------------------

@router.post("/transfers", response_model=StockTransferResponse, status_code=status.HTTP_201_CREATED)
def create_stock_transfer(
    data: StockTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager"])),
):
    """
    Transfer stock from one warehouse to another.

    This moves inventory between locations without changing total value.
    Creates TRANSFER entries in the stock ledger for audit trail.
    No journal entry is created since inventory value doesn't change.
    """
    result = transfer_stock(
        db=db,
        item_id=data.item_id,
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        quantity=data.quantity,
        reason=data.reason,
    )
    return StockTransferResponse(**result)


# ---------------------------------------------------------------------------
# Per-Warehouse Stock
# ---------------------------------------------------------------------------

@router.get("/warehouse-stock", response_model=List[WarehouseStockResponse])
def get_warehouse_stock_route(
    item_id: Optional[int] = Query(None, description="Filter by item ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """
    Get per-warehouse stock levels. Accountants have read-only access.

    Shows quantity of each item in each warehouse.
    Filter by item_id to see one item across all warehouses.
    Filter by warehouse_id to see all items in one warehouse.
    """
    return get_warehouse_stock(db, item_id=item_id, warehouse_id=warehouse_id)


# ---------------------------------------------------------------------------
# Stock Valuation
# ---------------------------------------------------------------------------

@router.get("/valuation", response_model=StockValuationReport)
def get_valuation_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "inventory_manager", "accountant"])),
):
    """
    Get stock valuation report.

    Returns total inventory value calculated as sum of (current_stock * unit_price)
    for all items. Useful for financial reporting and balance sheet preparation.
    """
    return get_stock_valuation(db)
