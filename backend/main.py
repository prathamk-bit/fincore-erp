"""
Main FastAPI application entry point for FreshBite Foods ERP.

Configures the application, registers all routers, sets up CORS,
creates database tables, and seeds default users on startup.
"""

from datetime import date, timedelta
from decimal import Decimal

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.models.database import Base, engine, SessionLocal
from backend.models.user import User
from backend.models.hr import Department, Designation, Employee
from backend.models.inventory import ItemCategory, Warehouse, Item
from backend.models.accounting import Account, JournalEntry, JournalEntryLine
from backend.models.procurement import Supplier, PurchaseOrder, PurchaseOrderItem
from backend.auth.auth import get_password_hash

# Import all models so Base.metadata knows about every table.
# The backend.models package __init__ already does this, but we make the
# intent explicit here.
import backend.models  # noqa: F401

from backend.routes import (
    auth_routes,
    hr_routes,
    accounting_routes,
    finance_routes,
    inventory_routes,
    procurement_routes,
    dashboard_routes,
    assistant_routes,
)

# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FreshBite Foods ERP",
    description="FreshBite Foods - Food & Beverage Manufacturing ERP System",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS (allow all origins for development)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Create all database tables
# ---------------------------------------------------------------------------

Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_routes.router)
app.include_router(hr_routes.router)
app.include_router(accounting_routes.router)
app.include_router(finance_routes.router)
app.include_router(inventory_routes.router)
app.include_router(procurement_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(assistant_routes.router)

# ---------------------------------------------------------------------------
# Static files — mounted LAST so that API routes take priority
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


# ---------------------------------------------------------------------------
# Startup event — seed default admin user
# ---------------------------------------------------------------------------

@app.on_event("startup")
def create_default_users():
    """
    Create default users for each role if they don't exist.
    If they do exist, update their password to the default.

    Credentials:
        admin:             admin@erp.com       / admin123
        accountant:        accountant@erp.com  / acc123
        hr_manager:        hr@erp.com          / hr123
        inventory_manager: inventory@erp.com   / inv123
    """
    db = SessionLocal()
    try:
        default_users = [
            {"username": "admin", "email": "admin@erp.com", "password": "admin123", "role": "admin"},
            {"username": "accountant", "email": "accountant@erp.com", "password": "acc123", "role": "accountant"},
            {"username": "hr_manager", "email": "hr@erp.com", "password": "hr123", "role": "hr_manager"},
            {"username": "inventory_manager", "email": "inventory@erp.com", "password": "inv123", "role": "inventory_manager"},
        ]

        for user_data in default_users:
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            if existing_user is None:
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    hashed_password=get_password_hash(user_data["password"]),
                    role=user_data["role"],
                )
                db.add(new_user)
                print(f"Created user: {user_data['username']} (password: {user_data['password']})")
            else:
                # Update password to latest default
                existing_user.hashed_password = get_password_hash(user_data["password"])

        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def startup_seed():
    seed_demo_data(force=False)

def seed_demo_data(force=False):
    """
    Seed demo data for a Food & Beverage manufacturing company.
    
    Company: "FreshBite Foods" - A bakery and beverage manufacturer
    
    Creates: departments, designations, employees, categories, warehouses,
    items (ingredients, packaging, finished products), accounts, and journal entries.
    """
    db = SessionLocal()
    try:
        if not force:
            # Check if F&B data already exists (look for F&B specific department)
            existing_dept = db.query(Department).filter(Department.name == "Production").first()
            if existing_dept and existing_dept.description == "Bakery and beverage production lines":
                print("F&B demo data already exists — skipping seed.")
                return

        
        # Clear old generic data if it exists
        existing_data = db.query(Department).first()
        if existing_data:
            print("Clearing old generic demo data...")
            # Delete in correct order due to foreign key constraints
            # Use try/except for tables that might not exist
            tables_to_clear = [
                "purchase_order_items",
                "purchase_orders",
                "suppliers",
                "journal_entry_lines",
                "journal_entries",
                "accounts",
                "warehouse_stock",
                "stock_ledger",
                "items",
                "item_categories",
                "warehouses",
                "payroll_components",
                "payrolls",
                "financial_transactions",
                "employees",
                "designations",
                "departments",
            ]
            for table in tables_to_clear:
                try:
                    db.execute(text(f"DELETE FROM {table}"))
                except Exception as e:
                    print(f"  Note: Could not clear {table}: {e}")
            db.commit()
            print("Old data cleared.")

        print("Seeding Food & Beverage industry demo data for FreshBite Foods...")

        # --- Departments (F&B specific) ---
        departments = [
            Department(name="Production", description="Bakery and beverage production lines"),
            Department(name="Quality Control", description="Food safety and quality assurance"),
            Department(name="Procurement", description="Ingredient sourcing and supplier management"),
            Department(name="Warehouse", description="Cold storage, dry storage, and distribution"),
            Department(name="Sales & Marketing", description="B2B and retail sales"),
            Department(name="R&D", description="Recipe development and product innovation"),
            Department(name="Finance", description="Accounting, costing, and budgeting"),
            Department(name="Human Resources", description="HR and compliance"),
        ]
        db.add_all(departments)
        db.flush()

        # --- Designations (F&B specific) ---
        designations = [
            Designation(title="Head Chef / Production Manager", description="Oversees all production operations"),
            Designation(title="Pastry Chef", description="Specializes in baked goods and desserts"),
            Designation(title="Beverage Specialist", description="Manages juice and beverage production"),
            Designation(title="QC Inspector", description="Ensures food safety standards (HACCP, FDA)"),
            Designation(title="QC Manager", description="Leads quality control department"),
            Designation(title="Procurement Officer", description="Sources ingredients and negotiates with suppliers"),
            Designation(title="Warehouse Supervisor", description="Manages inventory and cold chain"),
            Designation(title="Forklift Operator", description="Handles material movement"),
            Designation(title="Sales Manager", description="Manages B2B and distributor relationships"),
            Designation(title="Sales Representative", description="Handles customer orders and accounts"),
            Designation(title="R&D Food Scientist", description="Develops new recipes and products"),
            Designation(title="Cost Accountant", description="Tracks production costs and margins"),
            Designation(title="HR Manager", description="Handles recruitment and compliance"),
            Designation(title="Production Line Worker", description="Operates production machinery"),
            Designation(title="Packaging Technician", description="Handles product packaging and labeling"),
        ]
        db.add_all(designations)
        db.flush()

        # --- Employees (F&B workforce) ---
        today = date.today()
        employees = [
            # Production Team
            Employee(
                employee_code="FB-001", first_name="Marco", last_name="Rossi",
                email="marco.rossi@freshbite.com", phone="+1-555-1001",
                date_of_joining=today - timedelta(days=1095), salary=Decimal("85000.00"),
                department_id=departments[0].id, designation_id=designations[0].id
            ),
            Employee(
                employee_code="FB-002", first_name="Sophie", last_name="Laurent",
                email="sophie.laurent@freshbite.com", phone="+1-555-1002",
                date_of_joining=today - timedelta(days=730), salary=Decimal("62000.00"),
                department_id=departments[0].id, designation_id=designations[1].id
            ),
            Employee(
                employee_code="FB-003", first_name="Carlos", last_name="Mendez",
                email="carlos.mendez@freshbite.com", phone="+1-555-1003",
                date_of_joining=today - timedelta(days=548), salary=Decimal("58000.00"),
                department_id=departments[0].id, designation_id=designations[2].id
            ),
            Employee(
                employee_code="FB-004", first_name="Aisha", last_name="Patel",
                email="aisha.patel@freshbite.com", phone="+1-555-1004",
                date_of_joining=today - timedelta(days=365), salary=Decimal("38000.00"),
                department_id=departments[0].id, designation_id=designations[13].id
            ),
            Employee(
                employee_code="FB-005", first_name="Tommy", last_name="Nguyen",
                email="tommy.nguyen@freshbite.com", phone="+1-555-1005",
                date_of_joining=today - timedelta(days=180), salary=Decimal("36000.00"),
                department_id=departments[0].id, designation_id=designations[14].id
            ),
            # QC Team
            Employee(
                employee_code="FB-006", first_name="Dr. Lisa", last_name="Chen",
                email="lisa.chen@freshbite.com", phone="+1-555-1006",
                date_of_joining=today - timedelta(days=912), salary=Decimal("78000.00"),
                department_id=departments[1].id, designation_id=designations[4].id
            ),
            Employee(
                employee_code="FB-007", first_name="James", last_name="Wilson",
                email="james.wilson@freshbite.com", phone="+1-555-1007",
                date_of_joining=today - timedelta(days=456), salary=Decimal("52000.00"),
                department_id=departments[1].id, designation_id=designations[3].id
            ),
            # Procurement
            Employee(
                employee_code="FB-008", first_name="Maria", last_name="Santos",
                email="maria.santos@freshbite.com", phone="+1-555-1008",
                date_of_joining=today - timedelta(days=640), salary=Decimal("55000.00"),
                department_id=departments[2].id, designation_id=designations[5].id
            ),
            # Warehouse
            Employee(
                employee_code="FB-009", first_name="Robert", last_name="Johnson",
                email="robert.johnson@freshbite.com", phone="+1-555-1009",
                date_of_joining=today - timedelta(days=820), salary=Decimal("48000.00"),
                department_id=departments[3].id, designation_id=designations[6].id
            ),
            Employee(
                employee_code="FB-010", first_name="Kevin", last_name="Brown",
                email="kevin.brown@freshbite.com", phone="+1-555-1010",
                date_of_joining=today - timedelta(days=275), salary=Decimal("35000.00"),
                department_id=departments[3].id, designation_id=designations[7].id
            ),
            # Sales
            Employee(
                employee_code="FB-011", first_name="Jennifer", last_name="Adams",
                email="jennifer.adams@freshbite.com", phone="+1-555-1011",
                date_of_joining=today - timedelta(days=550), salary=Decimal("72000.00"),
                department_id=departments[4].id, designation_id=designations[8].id
            ),
            Employee(
                employee_code="FB-012", first_name="David", last_name="Lee",
                email="david.lee@freshbite.com", phone="+1-555-1012",
                date_of_joining=today - timedelta(days=320), salary=Decimal("45000.00"),
                department_id=departments[4].id, designation_id=designations[9].id
            ),
            # R&D
            Employee(
                employee_code="FB-013", first_name="Dr. Emily", last_name="Thompson",
                email="emily.thompson@freshbite.com", phone="+1-555-1013",
                date_of_joining=today - timedelta(days=485), salary=Decimal("82000.00"),
                department_id=departments[5].id, designation_id=designations[10].id
            ),
            # Finance
            Employee(
                employee_code="FB-014", first_name="Michael", last_name="Garcia",
                email="michael.garcia@freshbite.com", phone="+1-555-1014",
                date_of_joining=today - timedelta(days=730), salary=Decimal("68000.00"),
                department_id=departments[6].id, designation_id=designations[11].id
            ),
            # HR
            Employee(
                employee_code="FB-015", first_name="Sarah", last_name="Miller",
                email="sarah.miller@freshbite.com", phone="+1-555-1015",
                date_of_joining=today - timedelta(days=912), salary=Decimal("65000.00"),
                department_id=departments[7].id, designation_id=designations[12].id
            ),
        ]
        db.add_all(employees)
        db.flush()

        # --- Item Categories (F&B specific - complex hierarchy) ---
        categories = [
            # Raw Ingredients
            ItemCategory(name="Flour & Grains", description="Wheat flour, bread flour, whole grain, oats"),
            ItemCategory(name="Dairy & Eggs", description="Milk, cream, butter, eggs, cheese"),
            ItemCategory(name="Sweeteners", description="Sugar, honey, maple syrup, stevia"),
            ItemCategory(name="Fats & Oils", description="Vegetable oil, olive oil, shortening, butter"),
            ItemCategory(name="Fruits (Fresh)", description="Fresh fruits for juices and baked goods"),
            ItemCategory(name="Fruits (Frozen)", description="Frozen berries, tropical fruits"),
            ItemCategory(name="Nuts & Seeds", description="Almonds, walnuts, sunflower seeds, chia"),
            ItemCategory(name="Flavorings", description="Vanilla, cocoa, cinnamon, extracts"),
            ItemCategory(name="Leavening Agents", description="Yeast, baking powder, baking soda"),
            # Packaging Materials
            ItemCategory(name="Boxes & Containers", description="Cake boxes, pastry boxes, clamshells"),
            ItemCategory(name="Bottles & Caps", description="Juice bottles, caps, seals"),
            ItemCategory(name="Labels & Tags", description="Product labels, nutrition facts, barcodes"),
            ItemCategory(name="Wrapping Materials", description="Plastic wrap, foil, parchment paper"),
            # Finished Products
            ItemCategory(name="Breads", description="Loaves, baguettes, rolls, artisan breads"),
            ItemCategory(name="Pastries & Cakes", description="Croissants, muffins, cakes, cookies"),
            ItemCategory(name="Fresh Juices", description="Orange, apple, mixed berry juices"),
            ItemCategory(name="Smoothies", description="Ready-to-drink smoothie blends"),
        ]
        db.add_all(categories)
        db.flush()

        # --- Warehouses (F&B requires temperature-controlled storage) ---
        warehouses = [
            Warehouse(name="Dry Storage A", location="Building 1, Zone A - Ambient temp (15-25°C)"),
            Warehouse(name="Cold Storage - Dairy", location="Building 1, Zone B - Refrigerated (2-4°C)"),
            Warehouse(name="Freezer Storage", location="Building 1, Zone C - Frozen (-18°C)"),
            Warehouse(name="Packaging Warehouse", location="Building 2 - Ambient"),
            Warehouse(name="Finished Goods - Bakery", location="Building 3, Zone A - Cool (10-15°C)"),
            Warehouse(name="Finished Goods - Beverages", location="Building 3, Zone B - Refrigerated (2-4°C)"),
            Warehouse(name="Quarantine / QC Hold", location="Building 4 - Multi-temp (pending inspection)"),
        ]
        db.add_all(warehouses)
        db.flush()

        # --- Items (Comprehensive F&B inventory) ---
        items = [
            # ===== RAW INGREDIENTS =====
            # Flour & Grains (Category 0)
            Item(code="ING-001", name="All-Purpose Flour", description="Premium wheat flour, 25kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("500"), current_stock=Decimal("2500"),
                 unit_price=Decimal("0.85"), category_id=categories[0].id),
            Item(code="ING-002", name="Bread Flour", description="High-gluten flour for breads, 25kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("300"), current_stock=Decimal("1200"),
                 unit_price=Decimal("0.95"), category_id=categories[0].id),
            Item(code="ING-003", name="Whole Wheat Flour", description="Stone-ground whole wheat, 25kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("200"), current_stock=Decimal("600"),
                 unit_price=Decimal("1.10"), category_id=categories[0].id),
            Item(code="ING-004", name="Rolled Oats", description="Organic rolled oats, 20kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("100"), current_stock=Decimal("350"),
                 unit_price=Decimal("2.25"), category_id=categories[0].id),
            
            # Dairy & Eggs (Category 1)
            Item(code="ING-010", name="Whole Milk", description="Fresh whole milk, 20L container",
                 unit_of_measure="L", reorder_level=Decimal("200"), current_stock=Decimal("480"),
                 unit_price=Decimal("1.20"), category_id=categories[1].id),
            Item(code="ING-011", name="Heavy Cream", description="36% fat cream, 5L container",
                 unit_of_measure="L", reorder_level=Decimal("50"), current_stock=Decimal("120"),
                 unit_price=Decimal("4.50"), category_id=categories[1].id),
            Item(code="ING-012", name="Unsalted Butter", description="Premium butter, 5kg block",
                 unit_of_measure="kg", reorder_level=Decimal("80"), current_stock=Decimal("200"),
                 unit_price=Decimal("8.50"), category_id=categories[1].id),
            Item(code="ING-013", name="Large Eggs", description="Grade A large eggs, 30-count flat",
                 unit_of_measure="pcs", reorder_level=Decimal("500"), current_stock=Decimal("1800"),
                 unit_price=Decimal("0.25"), category_id=categories[1].id),
            Item(code="ING-014", name="Cream Cheese", description="Full-fat cream cheese, 2kg block",
                 unit_of_measure="kg", reorder_level=Decimal("40"), current_stock=Decimal("85"),
                 unit_price=Decimal("7.20"), category_id=categories[1].id),
            
            # Sweeteners (Category 2)
            Item(code="ING-020", name="Granulated Sugar", description="Fine white sugar, 50kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("300"), current_stock=Decimal("1500"),
                 unit_price=Decimal("0.75"), category_id=categories[2].id),
            Item(code="ING-021", name="Brown Sugar", description="Light brown sugar, 25kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("150"), current_stock=Decimal("400"),
                 unit_price=Decimal("0.90"), category_id=categories[2].id),
            Item(code="ING-022", name="Honey", description="Pure clover honey, 5kg container",
                 unit_of_measure="kg", reorder_level=Decimal("30"), current_stock=Decimal("75"),
                 unit_price=Decimal("12.00"), category_id=categories[2].id),
            Item(code="ING-023", name="Maple Syrup", description="Grade A maple syrup, 4L jug",
                 unit_of_measure="L", reorder_level=Decimal("20"), current_stock=Decimal("48"),
                 unit_price=Decimal("28.00"), category_id=categories[2].id),
            
            # Fats & Oils (Category 3)
            Item(code="ING-030", name="Vegetable Oil", description="Refined vegetable oil, 20L container",
                 unit_of_measure="L", reorder_level=Decimal("100"), current_stock=Decimal("280"),
                 unit_price=Decimal("1.80"), category_id=categories[3].id),
            Item(code="ING-031", name="Extra Virgin Olive Oil", description="Cold-pressed EVOO, 5L tin",
                 unit_of_measure="L", reorder_level=Decimal("30"), current_stock=Decimal("60"),
                 unit_price=Decimal("12.50"), category_id=categories[3].id),
            Item(code="ING-032", name="Vegetable Shortening", description="All-purpose shortening, 15kg pail",
                 unit_of_measure="kg", reorder_level=Decimal("50"), current_stock=Decimal("120"),
                 unit_price=Decimal("3.20"), category_id=categories[3].id),
            
            # Fresh Fruits (Category 4)
            Item(code="ING-040", name="Fresh Oranges", description="Valencia oranges for juicing, per kg",
                 unit_of_measure="kg", reorder_level=Decimal("200"), current_stock=Decimal("450"),
                 unit_price=Decimal("2.50"), category_id=categories[4].id),
            Item(code="ING-041", name="Fresh Apples", description="Gala apples for juice/baking, per kg",
                 unit_of_measure="kg", reorder_level=Decimal("150"), current_stock=Decimal("320"),
                 unit_price=Decimal("2.80"), category_id=categories[4].id),
            Item(code="ING-042", name="Fresh Lemons", description="Eureka lemons, per kg",
                 unit_of_measure="kg", reorder_level=Decimal("50"), current_stock=Decimal("85"),
                 unit_price=Decimal("3.50"), category_id=categories[4].id),
            Item(code="ING-043", name="Fresh Strawberries", description="Fresh strawberries, per kg",
                 unit_of_measure="kg", reorder_level=Decimal("40"), current_stock=Decimal("65"),
                 unit_price=Decimal("8.00"), category_id=categories[4].id),
            Item(code="ING-044", name="Fresh Bananas", description="Ripe bananas for smoothies, per kg",
                 unit_of_measure="kg", reorder_level=Decimal("80"), current_stock=Decimal("150"),
                 unit_price=Decimal("1.50"), category_id=categories[4].id),
            
            # Frozen Fruits (Category 5)
            Item(code="ING-050", name="Frozen Mixed Berries", description="IQF berry blend, 10kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("100"), current_stock=Decimal("280"),
                 unit_price=Decimal("6.50"), category_id=categories[5].id),
            Item(code="ING-051", name="Frozen Mango Chunks", description="IQF mango pieces, 10kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("60"), current_stock=Decimal("140"),
                 unit_price=Decimal("5.80"), category_id=categories[5].id),
            Item(code="ING-052", name="Frozen Blueberries", description="IQF wild blueberries, 10kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("50"), current_stock=Decimal("95"),
                 unit_price=Decimal("9.00"), category_id=categories[5].id),
            
            # Nuts & Seeds (Category 6)
            Item(code="ING-060", name="Sliced Almonds", description="Blanched sliced almonds, 5kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("30"), current_stock=Decimal("75"),
                 unit_price=Decimal("18.00"), category_id=categories[6].id),
            Item(code="ING-061", name="Chopped Walnuts", description="Raw walnut pieces, 5kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("25"), current_stock=Decimal("55"),
                 unit_price=Decimal("16.50"), category_id=categories[6].id),
            Item(code="ING-062", name="Chia Seeds", description="Organic chia seeds, 2kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("15"), current_stock=Decimal("32"),
                 unit_price=Decimal("14.00"), category_id=categories[6].id),
            
            # Flavorings (Category 7)
            Item(code="ING-070", name="Pure Vanilla Extract", description="Madagascar vanilla, 1L bottle",
                 unit_of_measure="L", reorder_level=Decimal("5"), current_stock=Decimal("12"),
                 unit_price=Decimal("85.00"), category_id=categories[7].id),
            Item(code="ING-071", name="Dutch Cocoa Powder", description="Alkalized cocoa, 5kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("20"), current_stock=Decimal("48"),
                 unit_price=Decimal("12.00"), category_id=categories[7].id),
            Item(code="ING-072", name="Ground Cinnamon", description="Ceylon cinnamon, 1kg container",
                 unit_of_measure="kg", reorder_level=Decimal("5"), current_stock=Decimal("12"),
                 unit_price=Decimal("22.00"), category_id=categories[7].id),
            Item(code="ING-073", name="Chocolate Chips", description="Semi-sweet chips, 10kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("40"), current_stock=Decimal("95"),
                 unit_price=Decimal("8.50"), category_id=categories[7].id),
            
            # Leavening Agents (Category 8)
            Item(code="ING-080", name="Active Dry Yeast", description="Professional baker's yeast, 500g pack",
                 unit_of_measure="kg", reorder_level=Decimal("5"), current_stock=Decimal("15"),
                 unit_price=Decimal("18.00"), category_id=categories[8].id),
            Item(code="ING-081", name="Instant Yeast", description="Fast-acting yeast, 500g pack",
                 unit_of_measure="kg", reorder_level=Decimal("5"), current_stock=Decimal("12"),
                 unit_price=Decimal("20.00"), category_id=categories[8].id),
            Item(code="ING-082", name="Baking Powder", description="Double-acting, 2.5kg can",
                 unit_of_measure="kg", reorder_level=Decimal("10"), current_stock=Decimal("25"),
                 unit_price=Decimal("6.50"), category_id=categories[8].id),
            Item(code="ING-083", name="Baking Soda", description="Pure sodium bicarbonate, 2.5kg bag",
                 unit_of_measure="kg", reorder_level=Decimal("10"), current_stock=Decimal("28"),
                 unit_price=Decimal("3.00"), category_id=categories[8].id),
            
            # ===== PACKAGING MATERIALS =====
            # Boxes & Containers (Category 9)
            Item(code="PKG-001", name="Cake Box 10x10x5", description="White cake box, 100/case",
                 unit_of_measure="pcs", reorder_level=Decimal("500"), current_stock=Decimal("2200"),
                 unit_price=Decimal("0.85"), category_id=categories[9].id),
            Item(code="PKG-002", name="Pastry Box 6x6x3", description="Window pastry box, 200/case",
                 unit_of_measure="pcs", reorder_level=Decimal("800"), current_stock=Decimal("3500"),
                 unit_price=Decimal("0.45"), category_id=categories[9].id),
            Item(code="PKG-003", name="Bread Bag (Kraft)", description="Brown kraft bread bag, 500/case",
                 unit_of_measure="pcs", reorder_level=Decimal("1000"), current_stock=Decimal("4500"),
                 unit_price=Decimal("0.12"), category_id=categories[9].id),
            Item(code="PKG-004", name="Cupcake Container 6-ct", description="Clear 6-cupcake container, 100/case",
                 unit_of_measure="pcs", reorder_level=Decimal("400"), current_stock=Decimal("1800"),
                 unit_price=Decimal("0.65"), category_id=categories[9].id),
            
            # Bottles & Caps (Category 10)
            Item(code="PKG-010", name="Juice Bottle 500ml", description="PET bottle with tamper cap, 200/case",
                 unit_of_measure="pcs", reorder_level=Decimal("2000"), current_stock=Decimal("8500"),
                 unit_price=Decimal("0.28"), category_id=categories[10].id),
            Item(code="PKG-011", name="Juice Bottle 1L", description="PET bottle with tamper cap, 100/case",
                 unit_of_measure="pcs", reorder_level=Decimal("1500"), current_stock=Decimal("5200"),
                 unit_price=Decimal("0.42"), category_id=categories[10].id),
            Item(code="PKG-012", name="Smoothie Cup 16oz", description="Clear PET cup with dome lid, 500/case",
                 unit_of_measure="pcs", reorder_level=Decimal("1000"), current_stock=Decimal("4200"),
                 unit_price=Decimal("0.18"), category_id=categories[10].id),
            
            # Labels & Tags (Category 11)
            Item(code="PKG-020", name="Product Label (Bread)", description="Self-adhesive bread labels, 1000/roll",
                 unit_of_measure="pcs", reorder_level=Decimal("3000"), current_stock=Decimal("12000"),
                 unit_price=Decimal("0.02"), category_id=categories[11].id),
            Item(code="PKG-021", name="Product Label (Juice)", description="Self-adhesive juice labels, 1000/roll",
                 unit_of_measure="pcs", reorder_level=Decimal("4000"), current_stock=Decimal("15000"),
                 unit_price=Decimal("0.025"), category_id=categories[11].id),
            Item(code="PKG-022", name="Nutrition Facts Sticker", description="FDA-compliant labels, 1000/roll",
                 unit_of_measure="pcs", reorder_level=Decimal("5000"), current_stock=Decimal("18000"),
                 unit_price=Decimal("0.015"), category_id=categories[11].id),
            
            # Wrapping Materials (Category 12)
            Item(code="PKG-030", name="Plastic Wrap Roll", description="Commercial food wrap, 18\"x2000ft",
                 unit_of_measure="roll", reorder_level=Decimal("20"), current_stock=Decimal("65"),
                 unit_price=Decimal("32.00"), category_id=categories[12].id),
            Item(code="PKG-031", name="Parchment Paper Sheets", description="Pre-cut sheets, 1000/case",
                 unit_of_measure="pcs", reorder_level=Decimal("2000"), current_stock=Decimal("6500"),
                 unit_price=Decimal("0.03"), category_id=categories[12].id),
            Item(code="PKG-032", name="Aluminum Foil Roll", description="Heavy-duty foil, 18\"x500ft",
                 unit_of_measure="roll", reorder_level=Decimal("15"), current_stock=Decimal("42"),
                 unit_price=Decimal("45.00"), category_id=categories[12].id),
            
            # ===== FINISHED PRODUCTS =====
            # Breads (Category 13)
            Item(code="FIN-001", name="Artisan Sourdough Loaf", description="800g rustic sourdough",
                 unit_of_measure="pcs", reorder_level=Decimal("50"), current_stock=Decimal("120"),
                 unit_price=Decimal("5.50"), category_id=categories[13].id),
            Item(code="FIN-002", name="Whole Wheat Sandwich Loaf", description="680g sliced bread",
                 unit_of_measure="pcs", reorder_level=Decimal("80"), current_stock=Decimal("180"),
                 unit_price=Decimal("4.25"), category_id=categories[13].id),
            Item(code="FIN-003", name="French Baguette", description="350g traditional baguette",
                 unit_of_measure="pcs", reorder_level=Decimal("100"), current_stock=Decimal("220"),
                 unit_price=Decimal("2.75"), category_id=categories[13].id),
            Item(code="FIN-004", name="Ciabatta Roll 4-pack", description="4x100g ciabatta rolls",
                 unit_of_measure="pack", reorder_level=Decimal("60"), current_stock=Decimal("145"),
                 unit_price=Decimal("4.50"), category_id=categories[13].id),
            Item(code="FIN-005", name="Multigrain Loaf", description="700g seeded multigrain",
                 unit_of_measure="pcs", reorder_level=Decimal("40"), current_stock=Decimal("95"),
                 unit_price=Decimal("5.25"), category_id=categories[13].id),
            
            # Pastries & Cakes (Category 14)
            Item(code="FIN-010", name="Butter Croissant", description="Large all-butter croissant",
                 unit_of_measure="pcs", reorder_level=Decimal("100"), current_stock=Decimal("280"),
                 unit_price=Decimal("2.95"), category_id=categories[14].id),
            Item(code="FIN-011", name="Chocolate Croissant", description="Pain au chocolat",
                 unit_of_measure="pcs", reorder_level=Decimal("80"), current_stock=Decimal("195"),
                 unit_price=Decimal("3.25"), category_id=categories[14].id),
            Item(code="FIN-012", name="Blueberry Muffin", description="Fresh-baked blueberry muffin",
                 unit_of_measure="pcs", reorder_level=Decimal("120"), current_stock=Decimal("320"),
                 unit_price=Decimal("2.50"), category_id=categories[14].id),
            Item(code="FIN-013", name="Chocolate Chip Cookie", description="Large gourmet cookie",
                 unit_of_measure="pcs", reorder_level=Decimal("150"), current_stock=Decimal("400"),
                 unit_price=Decimal("1.75"), category_id=categories[14].id),
            Item(code="FIN-014", name="New York Cheesecake Slice", description="Classic cheesecake portion",
                 unit_of_measure="pcs", reorder_level=Decimal("40"), current_stock=Decimal("85"),
                 unit_price=Decimal("4.95"), category_id=categories[14].id),
            Item(code="FIN-015", name="Carrot Cake Slice", description="Cream cheese frosted carrot cake",
                 unit_of_measure="pcs", reorder_level=Decimal("35"), current_stock=Decimal("72"),
                 unit_price=Decimal("4.50"), category_id=categories[14].id),
            Item(code="FIN-016", name="Cinnamon Roll", description="Large iced cinnamon roll",
                 unit_of_measure="pcs", reorder_level=Decimal("80"), current_stock=Decimal("165"),
                 unit_price=Decimal("3.50"), category_id=categories[14].id),
            
            # Fresh Juices (Category 15)
            Item(code="FIN-020", name="Fresh Orange Juice 500ml", description="100% freshly squeezed",
                 unit_of_measure="pcs", reorder_level=Decimal("150"), current_stock=Decimal("380"),
                 unit_price=Decimal("4.50"), category_id=categories[15].id),
            Item(code="FIN-021", name="Fresh Orange Juice 1L", description="100% freshly squeezed",
                 unit_of_measure="pcs", reorder_level=Decimal("80"), current_stock=Decimal("195"),
                 unit_price=Decimal("7.95"), category_id=categories[15].id),
            Item(code="FIN-022", name="Apple Juice 500ml", description="Fresh-pressed apple juice",
                 unit_of_measure="pcs", reorder_level=Decimal("120"), current_stock=Decimal("290"),
                 unit_price=Decimal("4.25"), category_id=categories[15].id),
            Item(code="FIN-023", name="Mixed Berry Juice 500ml", description="Berry blend juice",
                 unit_of_measure="pcs", reorder_level=Decimal("100"), current_stock=Decimal("245"),
                 unit_price=Decimal("5.25"), category_id=categories[15].id),
            Item(code="FIN-024", name="Green Detox Juice 500ml", description="Kale, apple, celery blend",
                 unit_of_measure="pcs", reorder_level=Decimal("60"), current_stock=Decimal("140"),
                 unit_price=Decimal("5.95"), category_id=categories[15].id),
            
            # Smoothies (Category 16)
            Item(code="FIN-030", name="Tropical Mango Smoothie 16oz", description="Mango, pineapple, coconut",
                 unit_of_measure="pcs", reorder_level=Decimal("80"), current_stock=Decimal("180"),
                 unit_price=Decimal("5.50"), category_id=categories[16].id),
            Item(code="FIN-031", name="Berry Blast Smoothie 16oz", description="Mixed berries with yogurt",
                 unit_of_measure="pcs", reorder_level=Decimal("90"), current_stock=Decimal("210"),
                 unit_price=Decimal("5.50"), category_id=categories[16].id),
            Item(code="FIN-032", name="Banana Protein Smoothie 16oz", description="Banana, peanut butter, protein",
                 unit_of_measure="pcs", reorder_level=Decimal("70"), current_stock=Decimal("155"),
                 unit_price=Decimal("6.25"), category_id=categories[16].id),
            Item(code="FIN-033", name="Green Power Smoothie 16oz", description="Spinach, banana, apple",
                 unit_of_measure="pcs", reorder_level=Decimal("50"), current_stock=Decimal("115"),
                 unit_price=Decimal("5.95"), category_id=categories[16].id),
        ]
        db.add_all(items)
        db.flush()

        # --- Chart of Accounts (F&B Industry-Specific) ---
        accounts = [
            # ASSETS (1xxx)
            Account(code="1000", name="Cash - Operating Account", account_type="asset", balance=Decimal("0")),
            Account(code="1010", name="Cash - Petty Cash", account_type="asset", balance=Decimal("0")),
            Account(code="1100", name="Accounts Receivable - Trade", account_type="asset", balance=Decimal("0")),
            Account(code="1110", name="Accounts Receivable - Distributors", account_type="asset", balance=Decimal("0")),
            Account(code="1200", name="Inventory - Raw Materials", account_type="asset", balance=Decimal("0")),
            Account(code="1210", name="Inventory - Work in Progress", account_type="asset", balance=Decimal("0")),
            Account(code="1220", name="Inventory - Finished Goods", account_type="asset", balance=Decimal("0")),
            Account(code="1230", name="Inventory - Packaging Materials", account_type="asset", balance=Decimal("0")),
            Account(code="1300", name="Prepaid Expenses", account_type="asset", balance=Decimal("0")),
            Account(code="1400", name="Production Equipment", account_type="asset", balance=Decimal("0")),
            Account(code="1410", name="Refrigeration Equipment", account_type="asset", balance=Decimal("0")),
            Account(code="1420", name="Delivery Vehicles", account_type="asset", balance=Decimal("0")),
            Account(code="1500", name="Accum. Depreciation - Equipment", account_type="asset", balance=Decimal("0")),
            
            # LIABILITIES (2xxx)
            Account(code="2000", name="Accounts Payable - Suppliers", account_type="liability", balance=Decimal("0")),
            Account(code="2010", name="Accounts Payable - Packaging", account_type="liability", balance=Decimal("0")),
            Account(code="2100", name="Accrued Wages Payable", account_type="liability", balance=Decimal("0")),
            Account(code="2110", name="Accrued Payroll Taxes", account_type="liability", balance=Decimal("0")),
            Account(code="2200", name="Sales Tax Payable", account_type="liability", balance=Decimal("0")),
            Account(code="2300", name="Short-term Loan - Bank", account_type="liability", balance=Decimal("0")),
            Account(code="2500", name="Long-term Debt - Equipment Loan", account_type="liability", balance=Decimal("0")),
            
            # EQUITY (3xxx)
            Account(code="3000", name="Owner's Capital", account_type="equity", balance=Decimal("0")),
            Account(code="3100", name="Retained Earnings", account_type="equity", balance=Decimal("0")),
            Account(code="3200", name="Owner's Drawings", account_type="equity", balance=Decimal("0")),
            
            # REVENUE (4xxx)
            Account(code="4000", name="Sales - Bakery Products", account_type="revenue", balance=Decimal("0")),
            Account(code="4010", name="Sales - Breads", account_type="revenue", balance=Decimal("0")),
            Account(code="4020", name="Sales - Pastries & Cakes", account_type="revenue", balance=Decimal("0")),
            Account(code="4100", name="Sales - Beverages", account_type="revenue", balance=Decimal("0")),
            Account(code="4110", name="Sales - Fresh Juices", account_type="revenue", balance=Decimal("0")),
            Account(code="4120", name="Sales - Smoothies", account_type="revenue", balance=Decimal("0")),
            Account(code="4500", name="Sales - Wholesale/Distributors", account_type="revenue", balance=Decimal("0")),
            Account(code="4900", name="Sales Discounts", account_type="revenue", balance=Decimal("0")),
            Account(code="4910", name="Sales Returns", account_type="revenue", balance=Decimal("0")),
            
            # COST OF GOODS SOLD (5xxx)
            Account(code="5000", name="COGS - Raw Materials", account_type="expense", balance=Decimal("0")),
            Account(code="5010", name="COGS - Flour & Grains", account_type="expense", balance=Decimal("0")),
            Account(code="5020", name="COGS - Dairy & Eggs", account_type="expense", balance=Decimal("0")),
            Account(code="5030", name="COGS - Fruits", account_type="expense", balance=Decimal("0")),
            Account(code="5040", name="COGS - Sweeteners & Flavorings", account_type="expense", balance=Decimal("0")),
            Account(code="5100", name="COGS - Packaging Materials", account_type="expense", balance=Decimal("0")),
            Account(code="5200", name="COGS - Direct Labor", account_type="expense", balance=Decimal("0")),
            Account(code="5300", name="COGS - Production Overhead", account_type="expense", balance=Decimal("0")),
            Account(code="5400", name="Inventory Spoilage & Waste", account_type="expense", balance=Decimal("0")),
            
            # OPERATING EXPENSES (6xxx)
            Account(code="6000", name="Wages - Production Staff", account_type="expense", balance=Decimal("0")),
            Account(code="6010", name="Wages - QC Staff", account_type="expense", balance=Decimal("0")),
            Account(code="6020", name="Wages - Warehouse Staff", account_type="expense", balance=Decimal("0")),
            Account(code="6030", name="Wages - Admin & Office", account_type="expense", balance=Decimal("0")),
            Account(code="6100", name="Payroll Taxes Expense", account_type="expense", balance=Decimal("0")),
            Account(code="6110", name="Employee Benefits", account_type="expense", balance=Decimal("0")),
            Account(code="6200", name="Rent - Production Facility", account_type="expense", balance=Decimal("0")),
            Account(code="6210", name="Rent - Retail/Office Space", account_type="expense", balance=Decimal("0")),
            Account(code="6300", name="Utilities - Electric", account_type="expense", balance=Decimal("0")),
            Account(code="6310", name="Utilities - Gas", account_type="expense", balance=Decimal("0")),
            Account(code="6320", name="Utilities - Water", account_type="expense", balance=Decimal("0")),
            Account(code="6400", name="Equipment Maintenance", account_type="expense", balance=Decimal("0")),
            Account(code="6410", name="Refrigeration Maintenance", account_type="expense", balance=Decimal("0")),
            Account(code="6500", name="Vehicle Expenses - Fuel", account_type="expense", balance=Decimal("0")),
            Account(code="6510", name="Vehicle Expenses - Maintenance", account_type="expense", balance=Decimal("0")),
            Account(code="6600", name="Insurance - General Liability", account_type="expense", balance=Decimal("0")),
            Account(code="6610", name="Insurance - Product Liability", account_type="expense", balance=Decimal("0")),
            Account(code="6700", name="Marketing & Advertising", account_type="expense", balance=Decimal("0")),
            Account(code="6800", name="Professional Fees - Accounting", account_type="expense", balance=Decimal("0")),
            Account(code="6810", name="Professional Fees - Legal", account_type="expense", balance=Decimal("0")),
            Account(code="6820", name="Food Safety Certification (HACCP)", account_type="expense", balance=Decimal("0")),
            Account(code="6900", name="Depreciation Expense", account_type="expense", balance=Decimal("0")),
            Account(code="6950", name="Bank Charges & Fees", account_type="expense", balance=Decimal("0")),
            Account(code="6990", name="Miscellaneous Expense", account_type="expense", balance=Decimal("0")),
            
            # OTHER INCOME/EXPENSE (7xxx)
            Account(code="7000", name="Interest Income", account_type="revenue", balance=Decimal("0")),
            Account(code="7100", name="Interest Expense", account_type="expense", balance=Decimal("0")),
            Account(code="7200", name="Gain on Asset Sale", account_type="revenue", balance=Decimal("0")),
            Account(code="7300", name="Loss on Asset Disposal", account_type="expense", balance=Decimal("0")),
        ]
        db.add_all(accounts)
        db.flush()

        # Build account lookup by code for journal entries
        acct_map = {a.code: a for a in accounts}

        # --- Journal Entries (F&B Industry Transactions) ---
        journal_entries = [
            # Opening Balance
            JournalEntry(
                entry_number="JE-000001", date=today - timedelta(days=90),
                description="Opening Balances - FreshBite Foods startup", status="posted",
                total_debit=Decimal("450000.00"), total_credit=Decimal("450000.00")
            ),
            # Ingredient Purchase - Flour Supplier
            JournalEntry(
                entry_number="JE-000002", date=today - timedelta(days=85),
                description="Purchase flour & grains from Miller's Flour Co (on credit)", status="posted",
                total_debit=Decimal("8500.00"), total_credit=Decimal("8500.00")
            ),
            # Ingredient Purchase - Dairy Supplier
            JournalEntry(
                entry_number="JE-000003", date=today - timedelta(days=82),
                description="Purchase dairy products from Valley Fresh Dairy (on credit)", status="posted",
                total_debit=Decimal("5200.00"), total_credit=Decimal("5200.00")
            ),
            # Packaging Purchase
            JournalEntry(
                entry_number="JE-000004", date=today - timedelta(days=80),
                description="Purchase packaging materials from PackRight Solutions", status="posted",
                total_debit=Decimal("3800.00"), total_credit=Decimal("3800.00")
            ),
            # Wholesale Bread Sales
            JournalEntry(
                entry_number="JE-000005", date=today - timedelta(days=75),
                description="Wholesale bread sales to CityMart Supermarkets (on credit)", status="posted",
                total_debit=Decimal("12500.00"), total_credit=Decimal("12500.00")
            ),
            # COGS for Bread Sales
            JournalEntry(
                entry_number="JE-000006", date=today - timedelta(days=75),
                description="COGS recognized for wholesale bread delivery", status="posted",
                total_debit=Decimal("6250.00"), total_credit=Decimal("6250.00")
            ),
            # Pay Supplier - Flour
            JournalEntry(
                entry_number="JE-000007", date=today - timedelta(days=70),
                description="Payment to Miller's Flour Co - Invoice #FL-2024-089", status="posted",
                total_debit=Decimal("8500.00"), total_credit=Decimal("8500.00")
            ),
            # Retail Pastry Sales (Cash)
            JournalEntry(
                entry_number="JE-000008", date=today - timedelta(days=65),
                description="Daily retail sales - Pastries & Cakes (cash & card)", status="posted",
                total_debit=Decimal("4850.00"), total_credit=Decimal("4850.00")
            ),
            # Juice Sales to Distributor
            JournalEntry(
                entry_number="JE-000009", date=today - timedelta(days=60),
                description="Fresh juice delivery to HealthyLife Distributors (on credit)", status="posted",
                total_debit=Decimal("8750.00"), total_credit=Decimal("8750.00")
            ),
            # Production Payroll
            JournalEntry(
                entry_number="JE-000010", date=today - timedelta(days=55),
                description="March payroll - Production staff wages", status="posted",
                total_debit=Decimal("18500.00"), total_credit=Decimal("18500.00")
            ),
            # Facility Rent
            JournalEntry(
                entry_number="JE-000011", date=today - timedelta(days=50),
                description="Monthly rent - Production facility & cold storage", status="posted",
                total_debit=Decimal("8500.00"), total_credit=Decimal("8500.00")
            ),
            # Utility Bills
            JournalEntry(
                entry_number="JE-000012", date=today - timedelta(days=48),
                description="Monthly utilities - Electric (high due to refrigeration)", status="posted",
                total_debit=Decimal("3200.00"), total_credit=Decimal("3200.00")
            ),
            # Fresh Fruit Purchase
            JournalEntry(
                entry_number="JE-000013", date=today - timedelta(days=45),
                description="Purchase fresh fruits from Orchard Fresh Farms (COD)", status="posted",
                total_debit=Decimal("4200.00"), total_credit=Decimal("4200.00")
            ),
            # Receive Customer Payment
            JournalEntry(
                entry_number="JE-000014", date=today - timedelta(days=40),
                description="Payment received from CityMart Supermarkets", status="posted",
                total_debit=Decimal("12500.00"), total_credit=Decimal("12500.00")
            ),
            # Smoothie Sales - Retail
            JournalEntry(
                entry_number="JE-000015", date=today - timedelta(days=35),
                description="Weekly retail sales - Smoothies & beverages (cash)", status="posted",
                total_debit=Decimal("3250.00"), total_credit=Decimal("3250.00")
            ),
            # Equipment Maintenance
            JournalEntry(
                entry_number="JE-000016", date=today - timedelta(days=30),
                description="Quarterly maintenance - Commercial ovens & mixers", status="posted",
                total_debit=Decimal("1850.00"), total_credit=Decimal("1850.00")
            ),
            # Refrigeration Repair
            JournalEntry(
                entry_number="JE-000017", date=today - timedelta(days=28),
                description="Emergency repair - Walk-in freezer compressor", status="posted",
                total_debit=Decimal("2400.00"), total_credit=Decimal("2400.00")
            ),
            # Inventory Spoilage
            JournalEntry(
                entry_number="JE-000018", date=today - timedelta(days=25),
                description="Write-off: Spoiled dairy products (refrigeration failure)", status="posted",
                total_debit=Decimal("850.00"), total_credit=Decimal("850.00")
            ),
            # Food Safety Certification
            JournalEntry(
                entry_number="JE-000019", date=today - timedelta(days=20),
                description="Annual HACCP certification renewal", status="posted",
                total_debit=Decimal("2500.00"), total_credit=Decimal("2500.00")
            ),
            # Marketing Campaign
            JournalEntry(
                entry_number="JE-000020", date=today - timedelta(days=15),
                description="Social media marketing - Spring product launch", status="posted",
                total_debit=Decimal("1500.00"), total_credit=Decimal("1500.00")
            ),
            # Wholesale Order - Cafe Chain
            JournalEntry(
                entry_number="JE-000021", date=today - timedelta(days=10),
                description="Wholesale pastry order - Bean & Brew Cafe (12 locations)", status="posted",
                total_debit=Decimal("15800.00"), total_credit=Decimal("15800.00")
            ),
            # Pay Dairy Supplier
            JournalEntry(
                entry_number="JE-000022", date=today - timedelta(days=8),
                description="Payment to Valley Fresh Dairy - Outstanding invoices", status="posted",
                total_debit=Decimal("5200.00"), total_credit=Decimal("5200.00")
            ),
            # Vehicle Fuel Expense
            JournalEntry(
                entry_number="JE-000023", date=today - timedelta(days=5),
                description="Monthly fuel - Delivery vehicles (3 vans)", status="posted",
                total_debit=Decimal("1850.00"), total_credit=Decimal("1850.00")
            ),
            # Insurance Premium
            JournalEntry(
                entry_number="JE-000024", date=today - timedelta(days=3),
                description="Quarterly insurance - General & product liability", status="posted",
                total_debit=Decimal("4200.00"), total_credit=Decimal("4200.00")
            ),
            # Daily Retail Sales
            JournalEntry(
                entry_number="JE-000025", date=today - timedelta(days=1),
                description="Daily retail sales - All products (Saturday rush)", status="posted",
                total_debit=Decimal("6800.00"), total_credit=Decimal("6800.00")
            ),
        ]
        db.add_all(journal_entries)
        db.flush()

        # --- Journal Entry Lines (Double-entry for each transaction) ---
        lines = [
            # JE-000001: Opening Balances
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1000"].id, debit=Decimal("120000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1010"].id, debit=Decimal("2000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1100"].id, debit=Decimal("35000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1200"].id, debit=Decimal("45000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1220"].id, debit=Decimal("28000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1230"].id, debit=Decimal("15000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1400"].id, debit=Decimal("150000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1410"].id, debit=Decimal("35000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["1420"].id, debit=Decimal("20000.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["2000"].id, debit=Decimal("0"), credit=Decimal("25000.00")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["2100"].id, debit=Decimal("0"), credit=Decimal("8000.00")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["2500"].id, debit=Decimal("0"), credit=Decimal("75000.00")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["3000"].id, debit=Decimal("0"), credit=Decimal("300000.00")),
            JournalEntryLine(journal_entry_id=journal_entries[0].id, account_id=acct_map["3100"].id, debit=Decimal("0"), credit=Decimal("42000.00")),
            
            # JE-000002: Flour Purchase (DR: Raw Materials Inventory, CR: AP - Suppliers)
            JournalEntryLine(journal_entry_id=journal_entries[1].id, account_id=acct_map["1200"].id, debit=Decimal("8500.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[1].id, account_id=acct_map["2000"].id, debit=Decimal("0"), credit=Decimal("8500.00")),
            
            # JE-000003: Dairy Purchase (DR: Raw Materials Inventory, CR: AP - Suppliers)
            JournalEntryLine(journal_entry_id=journal_entries[2].id, account_id=acct_map["1200"].id, debit=Decimal("5200.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[2].id, account_id=acct_map["2000"].id, debit=Decimal("0"), credit=Decimal("5200.00")),
            
            # JE-000004: Packaging Purchase (DR: Packaging Inventory, CR: AP - Packaging)
            JournalEntryLine(journal_entry_id=journal_entries[3].id, account_id=acct_map["1230"].id, debit=Decimal("3800.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[3].id, account_id=acct_map["2010"].id, debit=Decimal("0"), credit=Decimal("3800.00")),
            
            # JE-000005: Wholesale Bread Sales (DR: AR - Distributors, CR: Sales - Breads)
            JournalEntryLine(journal_entry_id=journal_entries[4].id, account_id=acct_map["1110"].id, debit=Decimal("12500.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[4].id, account_id=acct_map["4010"].id, debit=Decimal("0"), credit=Decimal("12500.00")),
            
            # JE-000006: COGS for Bread (DR: COGS - Flour, CR: Finished Goods Inventory)
            JournalEntryLine(journal_entry_id=journal_entries[5].id, account_id=acct_map["5010"].id, debit=Decimal("6250.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[5].id, account_id=acct_map["1220"].id, debit=Decimal("0"), credit=Decimal("6250.00")),
            
            # JE-000007: Pay Flour Supplier (DR: AP - Suppliers, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[6].id, account_id=acct_map["2000"].id, debit=Decimal("8500.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[6].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("8500.00")),
            
            # JE-000008: Retail Pastry Sales (DR: Cash, CR: Sales - Pastries)
            JournalEntryLine(journal_entry_id=journal_entries[7].id, account_id=acct_map["1000"].id, debit=Decimal("4850.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[7].id, account_id=acct_map["4020"].id, debit=Decimal("0"), credit=Decimal("4850.00")),
            
            # JE-000009: Juice Sales to Distributor (DR: AR - Distributors, CR: Sales - Juices)
            JournalEntryLine(journal_entry_id=journal_entries[8].id, account_id=acct_map["1110"].id, debit=Decimal("8750.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[8].id, account_id=acct_map["4110"].id, debit=Decimal("0"), credit=Decimal("8750.00")),
            
            # JE-000010: Production Payroll (DR: Wages - Production, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[9].id, account_id=acct_map["6000"].id, debit=Decimal("18500.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[9].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("18500.00")),
            
            # JE-000011: Facility Rent (DR: Rent - Production, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[10].id, account_id=acct_map["6200"].id, debit=Decimal("8500.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[10].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("8500.00")),
            
            # JE-000012: Electric Bill (DR: Utilities - Electric, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[11].id, account_id=acct_map["6300"].id, debit=Decimal("3200.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[11].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("3200.00")),
            
            # JE-000013: Fresh Fruit Purchase COD (DR: Raw Materials, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[12].id, account_id=acct_map["1200"].id, debit=Decimal("4200.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[12].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("4200.00")),
            
            # JE-000014: Customer Payment (DR: Cash, CR: AR - Distributors)
            JournalEntryLine(journal_entry_id=journal_entries[13].id, account_id=acct_map["1000"].id, debit=Decimal("12500.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[13].id, account_id=acct_map["1110"].id, debit=Decimal("0"), credit=Decimal("12500.00")),
            
            # JE-000015: Smoothie Retail Sales (DR: Cash, CR: Sales - Smoothies)
            JournalEntryLine(journal_entry_id=journal_entries[14].id, account_id=acct_map["1000"].id, debit=Decimal("3250.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[14].id, account_id=acct_map["4120"].id, debit=Decimal("0"), credit=Decimal("3250.00")),
            
            # JE-000016: Equipment Maintenance (DR: Equipment Maint., CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[15].id, account_id=acct_map["6400"].id, debit=Decimal("1850.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[15].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("1850.00")),
            
            # JE-000017: Refrigeration Repair (DR: Refrigeration Maint., CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[16].id, account_id=acct_map["6410"].id, debit=Decimal("2400.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[16].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("2400.00")),
            
            # JE-000018: Spoilage Write-off (DR: Inventory Spoilage, CR: Raw Materials)
            JournalEntryLine(journal_entry_id=journal_entries[17].id, account_id=acct_map["5400"].id, debit=Decimal("850.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[17].id, account_id=acct_map["1200"].id, debit=Decimal("0"), credit=Decimal("850.00")),
            
            # JE-000019: HACCP Certification (DR: Food Safety Cert., CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[18].id, account_id=acct_map["6820"].id, debit=Decimal("2500.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[18].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("2500.00")),
            
            # JE-000020: Marketing Campaign (DR: Marketing, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[19].id, account_id=acct_map["6700"].id, debit=Decimal("1500.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[19].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("1500.00")),
            
            # JE-000021: Wholesale Pastry Order (DR: AR - Distributors, CR: Sales - Pastries)
            JournalEntryLine(journal_entry_id=journal_entries[20].id, account_id=acct_map["1110"].id, debit=Decimal("15800.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[20].id, account_id=acct_map["4020"].id, debit=Decimal("0"), credit=Decimal("15800.00")),
            
            # JE-000022: Pay Dairy Supplier (DR: AP - Suppliers, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[21].id, account_id=acct_map["2000"].id, debit=Decimal("5200.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[21].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("5200.00")),
            
            # JE-000023: Vehicle Fuel (DR: Vehicle Fuel, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[22].id, account_id=acct_map["6500"].id, debit=Decimal("1850.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[22].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("1850.00")),
            
            # JE-000024: Insurance (DR: Insurance - both types, CR: Cash)
            JournalEntryLine(journal_entry_id=journal_entries[23].id, account_id=acct_map["6600"].id, debit=Decimal("2100.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[23].id, account_id=acct_map["6610"].id, debit=Decimal("2100.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[23].id, account_id=acct_map["1000"].id, debit=Decimal("0"), credit=Decimal("4200.00")),
            
            # JE-000025: Daily Retail Sales (DR: Cash, CR: Multiple sales accounts)
            JournalEntryLine(journal_entry_id=journal_entries[24].id, account_id=acct_map["1000"].id, debit=Decimal("6800.00"), credit=Decimal("0")),
            JournalEntryLine(journal_entry_id=journal_entries[24].id, account_id=acct_map["4010"].id, debit=Decimal("0"), credit=Decimal("2200.00")),
            JournalEntryLine(journal_entry_id=journal_entries[24].id, account_id=acct_map["4020"].id, debit=Decimal("0"), credit=Decimal("2800.00")),
            JournalEntryLine(journal_entry_id=journal_entries[24].id, account_id=acct_map["4110"].id, debit=Decimal("0"), credit=Decimal("1100.00")),
            JournalEntryLine(journal_entry_id=journal_entries[24].id, account_id=acct_map["4120"].id, debit=Decimal("0"), credit=Decimal("700.00")),
        ]
        db.add_all(lines)
        db.flush()

        # --- Apply balance updates for all posted journal entries ---
        for line in lines:
            account = next(a for a in accounts if a.id == line.account_id)
            journal_entry = next(je for je in journal_entries if je.id == line.journal_entry_id)
            if journal_entry.status == "posted":
                if account.account_type in ("asset", "expense"):
                    account.balance += line.debit - line.credit
                else:
                    account.balance += line.credit - line.debit

        # --- Suppliers (F&B Industry-Specific) ---
        suppliers = [
            Supplier(
                name="Miller's Flour Company", contact_person="Thomas Miller",
                email="orders@millersflour.com", phone="+1-555-2001",
                address="1200 Grain Mill Road, Wheat Valley, KS 67801"
            ),
            Supplier(
                name="Valley Fresh Dairy", contact_person="Linda Peterson",
                email="sales@valleyfreshdairy.com", phone="+1-555-2002",
                address="500 Dairy Farm Lane, Green Pastures, WI 53001"
            ),
            Supplier(
                name="Orchard Fresh Farms", contact_person="Miguel Rodriguez",
                email="orders@orchardfresh.com", phone="+1-555-2003",
                address="800 Orchard Way, Fruitland, CA 93001"
            ),
            Supplier(
                name="Sweet Supply Co", contact_person="Jennifer Sweet",
                email="jennifer@sweetsupply.com", phone="+1-555-2004",
                address="250 Sugar Lane, Sweetwater, FL 33001"
            ),
            Supplier(
                name="PackRight Solutions", contact_person="David Chen",
                email="sales@packright.com", phone="+1-555-2005",
                address="1500 Industrial Pkwy, Package City, OH 44001"
            ),
            Supplier(
                name="Tropical Fruits International", contact_person="Maria Santos",
                email="maria@tropicalfruits.com", phone="+1-555-2006",
                address="2000 Import Plaza, Miami, FL 33101"
            ),
            Supplier(
                name="Premium Nuts & Seeds", contact_person="Ahmed Hassan",
                email="orders@premiumnuts.com", phone="+1-555-2007",
                address="750 Nut Grove Ave, Almond Hills, CA 95001"
            ),
            Supplier(
                name="Chef's Essentials", contact_person="Pierre Dubois",
                email="pierre@chefsessentials.com", phone="+1-555-2008",
                address="100 Gourmet Street, Flavor Town, NY 10001"
            ),
        ]
        db.add_all(suppliers)
        db.flush()

        # --- Purchase Orders (F&B complex orders) ---
        purchase_orders = [
            PurchaseOrder(
                po_number="PO-FB-001", supplier_id=suppliers[0].id,
                order_date=today - timedelta(days=30),
                expected_delivery_date=today - timedelta(days=25),
                status="received", total_amount=Decimal("4250.00")
            ),
            PurchaseOrder(
                po_number="PO-FB-002", supplier_id=suppliers[1].id,
                order_date=today - timedelta(days=25),
                expected_delivery_date=today - timedelta(days=20),
                status="received", total_amount=Decimal("3680.00")
            ),
            PurchaseOrder(
                po_number="PO-FB-003", supplier_id=suppliers[2].id,
                order_date=today - timedelta(days=15),
                expected_delivery_date=today - timedelta(days=12),
                status="received", total_amount=Decimal("2850.00")
            ),
            PurchaseOrder(
                po_number="PO-FB-004", supplier_id=suppliers[4].id,
                order_date=today - timedelta(days=10),
                expected_delivery_date=today - timedelta(days=5),
                status="approved", total_amount=Decimal("5420.00")
            ),
            PurchaseOrder(
                po_number="PO-FB-005", supplier_id=suppliers[5].id,
                order_date=today - timedelta(days=5),
                expected_delivery_date=today + timedelta(days=3),
                status="approved", total_amount=Decimal("3200.00")
            ),
            PurchaseOrder(
                po_number="PO-FB-006", supplier_id=suppliers[6].id,
                order_date=today - timedelta(days=3),
                expected_delivery_date=today + timedelta(days=7),
                status="draft", total_amount=Decimal("2750.00")
            ),
        ]
        db.add_all(purchase_orders)
        db.flush()

        # --- Purchase Order Items ---
        po_items = [
            # PO-FB-001: Flour order
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[0].id, item_id=items[0].id,
                quantity=Decimal("2000"), received_quantity=Decimal("2000"),
                unit_price=Decimal("0.85"), total_price=Decimal("1700.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[0].id, item_id=items[1].id,
                quantity=Decimal("1500"), received_quantity=Decimal("1500"),
                unit_price=Decimal("0.95"), total_price=Decimal("1425.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[0].id, item_id=items[2].id,
                quantity=Decimal("750"), received_quantity=Decimal("750"),
                unit_price=Decimal("1.10"), total_price=Decimal("825.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[0].id, item_id=items[3].id,
                quantity=Decimal("150"), received_quantity=Decimal("150"),
                unit_price=Decimal("2.00"), total_price=Decimal("300.00")
            ),
            
            # PO-FB-002: Dairy order
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[1].id, item_id=items[4].id,
                quantity=Decimal("400"), received_quantity=Decimal("400"),
                unit_price=Decimal("1.20"), total_price=Decimal("480.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[1].id, item_id=items[5].id,
                quantity=Decimal("100"), received_quantity=Decimal("100"),
                unit_price=Decimal("4.50"), total_price=Decimal("450.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[1].id, item_id=items[6].id,
                quantity=Decimal("200"), received_quantity=Decimal("200"),
                unit_price=Decimal("8.50"), total_price=Decimal("1700.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[1].id, item_id=items[7].id,
                quantity=Decimal("1500"), received_quantity=Decimal("1500"),
                unit_price=Decimal("0.25"), total_price=Decimal("375.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[1].id, item_id=items[8].id,
                quantity=Decimal("80"), received_quantity=Decimal("80"),
                unit_price=Decimal("7.20"), total_price=Decimal("576.00")
            ),
            
            # PO-FB-003: Fresh Fruits
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[2].id, item_id=items[16].id,
                quantity=Decimal("350"), received_quantity=Decimal("350"),
                unit_price=Decimal("2.50"), total_price=Decimal("875.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[2].id, item_id=items[17].id,
                quantity=Decimal("250"), received_quantity=Decimal("250"),
                unit_price=Decimal("2.80"), total_price=Decimal("700.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[2].id, item_id=items[19].id,
                quantity=Decimal("60"), received_quantity=Decimal("60"),
                unit_price=Decimal("8.00"), total_price=Decimal("480.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[2].id, item_id=items[20].id,
                quantity=Decimal("120"), received_quantity=Decimal("120"),
                unit_price=Decimal("1.50"), total_price=Decimal("180.00")
            ),
            
            # PO-FB-004: Packaging
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[3].id, item_id=items[34].id,
                quantity=Decimal("2000"), received_quantity=Decimal("0"),
                unit_price=Decimal("0.85"), total_price=Decimal("1700.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[3].id, item_id=items[35].id,
                quantity=Decimal("3000"), received_quantity=Decimal("0"),
                unit_price=Decimal("0.45"), total_price=Decimal("1350.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[3].id, item_id=items[38].id,
                quantity=Decimal("6000"), received_quantity=Decimal("0"),
                unit_price=Decimal("0.28"), total_price=Decimal("1680.00")
            ),
            
            # PO-FB-005: Frozen Fruits
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[4].id, item_id=items[21].id,
                quantity=Decimal("200"), received_quantity=Decimal("0"),
                unit_price=Decimal("6.50"), total_price=Decimal("1300.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[4].id, item_id=items[22].id,
                quantity=Decimal("150"), received_quantity=Decimal("0"),
                unit_price=Decimal("5.80"), total_price=Decimal("870.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[4].id, item_id=items[23].id,
                quantity=Decimal("100"), received_quantity=Decimal("0"),
                unit_price=Decimal("9.00"), total_price=Decimal("900.00")
            ),
            
            # PO-FB-006: Nuts (Draft)
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[5].id, item_id=items[24].id,
                quantity=Decimal("50"), received_quantity=Decimal("0"),
                unit_price=Decimal("18.00"), total_price=Decimal("900.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[5].id, item_id=items[25].id,
                quantity=Decimal("40"), received_quantity=Decimal("0"),
                unit_price=Decimal("16.50"), total_price=Decimal("660.00")
            ),
            PurchaseOrderItem(
                purchase_order_id=purchase_orders[5].id, item_id=items[29].id,
                quantity=Decimal("100"), received_quantity=Decimal("0"),
                unit_price=Decimal("8.50"), total_price=Decimal("850.00")
            ),
        ]
        db.add_all(po_items)

        db.commit()
        print("Food & Beverage industry demo data seeded successfully!")
        print("Company: FreshBite Foods - Bakery & Beverage Manufacturer")

    except Exception as e:
        db.rollback()
        print(f"Error seeding demo data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Development server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
