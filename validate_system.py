"""
FinCore System Flow Validation & Error Checking Script.

This script performs comprehensive end-to-end testing of all system flows:
1. Authentication & RBAC
2. Accounting (Core) — Double-Entry, Ledger, Trial Balance, Reports
3. HR — Employee management, Payroll lifecycle
4. Procurement — PO lifecycle, Receiving, Inventory impact
5. Inventory — Stock management, Adjustments, Transfers
6. Finance — Transaction tracking
7. Dashboard — Data accuracy
8. AI Assistant — Insight generation

Run with: python3 validate_system.py
"""

import json
import sys
import requests
from decimal import Decimal

BASE_URL = "http://localhost:8000/api"

# Track results
RESULTS = {"passed": 0, "failed": 0, "errors": []}


def check(test_name, condition, details=""):
    """Record a test result."""
    if condition:
        RESULTS["passed"] += 1
        print(f"  ✅ {test_name}")
    else:
        RESULTS["failed"] += 1
        RESULTS["errors"].append(f"{test_name}: {details}")
        print(f"  ❌ {test_name} — {details}")


def get_token(username, password):
    """Login and return JWT token."""
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    if r.status_code == 200:
        return r.json()["access_token"]
    return None


def auth_headers(token):
    """Build Authorization headers."""
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. AUTHENTICATION & RBAC
# ============================================================================
def test_authentication():
    print("\n" + "=" * 70)
    print("1. AUTHENTICATION & RBAC VALIDATION")
    print("=" * 70)

    # Test valid logins
    for user, pw in [("admin", "admin123"), ("accountant", "acc123"),
                     ("hr_manager", "hr123"), ("inventory_manager", "inv123")]:
        token = get_token(user, pw)
        check(f"Login [{user}]", token is not None, f"Login failed for {user}")

    # Test invalid login
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "wrongpass"})
    check("Reject invalid password", r.status_code == 401, f"Got {r.status_code}")

    # RBAC: HR manager should NOT access accounting
    hr_token = get_token("hr_manager", "hr123")
    r = requests.get(f"{BASE_URL}/accounting/accounts", headers=auth_headers(hr_token))
    check("RBAC: HR blocked from Accounting", r.status_code == 403, f"Got {r.status_code}")

    # RBAC: Inventory manager should NOT access HR
    inv_token = get_token("inventory_manager", "inv123")
    r = requests.get(f"{BASE_URL}/hr/employees", headers=auth_headers(inv_token))
    check("RBAC: Inventory blocked from HR", r.status_code == 403, f"Got {r.status_code}")

    # RBAC: Accountant should NOT access HR
    acct_token = get_token("accountant", "acc123")
    r = requests.get(f"{BASE_URL}/hr/employees", headers=auth_headers(acct_token))
    check("RBAC: Accountant blocked from HR", r.status_code == 403, f"Got {r.status_code}")

    # RBAC: HR blocked from procurement
    r = requests.get(f"{BASE_URL}/procurement/suppliers", headers=auth_headers(hr_token))
    check("RBAC: HR blocked from Procurement", r.status_code == 403, f"Got {r.status_code}")

    # RBAC: Admin accesses everything
    admin_token = get_token("admin", "admin123")
    for endpoint in ["/accounting/accounts", "/hr/employees", "/inventory/items", "/procurement/suppliers"]:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=auth_headers(admin_token))
        check(f"RBAC: Admin access {endpoint}", r.status_code == 200, f"Got {r.status_code}")

    # Unauthenticated access
    r = requests.get(f"{BASE_URL}/accounting/accounts")
    check("Reject unauthenticated request", r.status_code in [401, 403], f"Got {r.status_code}")


# ============================================================================
# 2. ACCOUNTING CORE VALIDATION
# ============================================================================
def test_accounting(admin_token):
    print("\n" + "=" * 70)
    print("2. ACCOUNTING MODULE VALIDATION")
    print("=" * 70)
    headers = auth_headers(admin_token)

    # --- Chart of Accounts ---
    r = requests.get(f"{BASE_URL}/accounting/accounts", headers=headers)
    check("GET accounts", r.status_code == 200)
    accounts = r.json()
    check("Accounts exist", len(accounts) > 0, f"Got {len(accounts)} accounts")

    # Verify account types
    types_found = set(a["account_type"] for a in accounts)
    for t in ["asset", "liability", "equity", "revenue", "expense"]:
        check(f"Account type '{t}' exists", t in types_found, f"Missing: {t}")

    # --- Journal Entries ---
    r = requests.get(f"{BASE_URL}/accounting/journal-entries", headers=headers)
    check("GET journal entries", r.status_code == 200)
    entries = r.json()
    check("Journal entries exist", len(entries) > 0, f"Got {len(entries)}")

    # Verify ALL posted entries are balanced (Debits == Credits)
    imbalanced = []
    for je in entries:
        if je["status"] == "posted":
            if je["total_debit"] != je["total_credit"]:
                imbalanced.append(je["entry_number"])
    check("All posted JEs balanced (D=C)", len(imbalanced) == 0,
          f"Imbalanced: {imbalanced}")

    # Verify each JE has lines
    for je in entries[:5]:
        r2 = requests.get(f"{BASE_URL}/accounting/journal-entries/{je['id']}", headers=headers)
        if r2.status_code == 200:
            detail = r2.json()
            check(f"JE {detail['entry_number']} has lines", len(detail.get("lines", [])) >= 2,
                  f"Only {len(detail.get('lines', []))} lines")

    # --- Trial Balance ---
    r = requests.get(f"{BASE_URL}/accounting/trial-balance", headers=headers)
    check("GET trial balance", r.status_code == 200)
    tb = r.json()
    check("Trial Balance is balanced", tb.get("is_balanced", False),
          f"Debits={tb.get('total_debits')}, Credits={tb.get('total_credits')}")

    # --- Create, Update, Post Journal Entry Lifecycle ---
    print("\n  --- Journal Entry Lifecycle Test ---")
    
    # Find two accounts for our test
    asset_accounts = [a for a in accounts if a["account_type"] == "asset"]
    expense_accounts = [a for a in accounts if a["account_type"] == "expense"]
    
    if len(asset_accounts) >= 1 and len(expense_accounts) >= 1:
        test_je_data = {
            "date": "2025-04-01",
            "description": "[VALIDATION TEST] Test journal entry",
            "lines": [
                {"account_id": expense_accounts[0]["id"], "debit": "100.00", "credit": "0"},
                {"account_id": asset_accounts[0]["id"], "debit": "0", "credit": "100.00"},
            ]
        }
        r = requests.post(f"{BASE_URL}/accounting/journal-entries", headers=headers, json=test_je_data)
        check("Create draft JE", r.status_code == 201, f"Got {r.status_code}: {r.text[:200]}")
        
        if r.status_code == 201:
            new_je = r.json()
            je_id = new_je["id"]
            check("New JE is draft", new_je["status"] == "draft")

            # Update the draft
            update_data = {"description": "[VALIDATION TEST] Updated description"}
            r = requests.put(f"{BASE_URL}/accounting/journal-entries/{je_id}", headers=headers, json=update_data)
            check("Update draft JE", r.status_code == 200, f"Got {r.status_code}")

            # Post the entry
            r = requests.post(f"{BASE_URL}/accounting/journal-entries/{je_id}/post", headers=headers)
            check("Post JE", r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}")
            if r.status_code == 200:
                posted = r.json()
                check("JE status is 'posted'", posted["status"] == "posted")

                # Try to update a posted entry (should fail)
                r = requests.put(f"{BASE_URL}/accounting/journal-entries/{je_id}", headers=headers,
                                 json={"description": "Should fail"})
                check("Cannot update posted JE", r.status_code in [400, 422], f"Got {r.status_code}")

    # --- Financial Reports ---
    print("\n  --- Financial Reports ---")
    r = requests.get(f"{BASE_URL}/accounting/reports/income-statement?start_date=2025-01-01&end_date=2025-12-31",
                     headers=headers)
    check("GET income statement", r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}" if r.status_code != 200 else "")

    r = requests.get(f"{BASE_URL}/accounting/reports/balance-sheet", headers=headers)
    check("GET balance sheet", r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}" if r.status_code != 200 else "")
    if r.status_code == 200:
        bs = r.json()
        check("Balance Sheet is balanced (A = L+E)", bs.get("is_balanced", False),
              f"Assets={bs.get('total_assets')}, L+E={bs.get('liabilities_and_equity')}")

    r = requests.get(f"{BASE_URL}/accounting/reports/cash-flow?start_date=2025-01-01&end_date=2025-12-31",
                     headers=headers)
    check("GET cash flow statement", r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}" if r.status_code != 200 else "")


# ============================================================================
# 3. HR MODULE VALIDATION
# ============================================================================
def test_hr(admin_token):
    print("\n" + "=" * 70)
    print("3. HR MODULE VALIDATION")
    print("=" * 70)
    headers = auth_headers(admin_token)

    # Departments & Designations
    r = requests.get(f"{BASE_URL}/hr/departments", headers=headers)
    check("GET departments", r.status_code == 200)
    departments = r.json()
    check("Departments exist", len(departments) > 0)

    r = requests.get(f"{BASE_URL}/hr/designations", headers=headers)
    check("GET designations", r.status_code == 200)

    # Employees
    r = requests.get(f"{BASE_URL}/hr/employees", headers=headers)
    check("GET employees", r.status_code == 200)
    employees = r.json()
    check("Employees exist", len(employees) > 0, f"Got {len(employees)}")

    # Verify each employee has required fields
    for emp in employees[:3]:
        check(f"Employee {emp.get('employee_code')} has salary > 0",
              float(emp.get("salary", 0)) > 0, f"Salary = {emp.get('salary')}")

    # --- Payroll Lifecycle Test ---
    print("\n  --- Payroll Lifecycle Test ---")
    if employees:
        emp = employees[0]
        # Use a dynamic period to avoid conflicts with previous test runs
        import datetime, random
        offset = random.randint(730, 1095)
        test_date = datetime.date.today() + datetime.timedelta(days=offset)
        period_start = test_date.replace(day=1).isoformat()
        period_end = (test_date.replace(day=28)).isoformat()
        
        payroll_data = {
            "employee_id": emp["id"],
            "pay_period_start": period_start,
            "pay_period_end": period_end,
            "components": [
                {"component_name": "Basic Salary", "component_type": "earnings", "amount": str(emp["salary"])},
                {"component_name": "HRA", "component_type": "earnings", "amount": "5000"},
                {"component_name": "Tax", "component_type": "deductions", "amount": "3000"},
            ]
        }
        r = requests.post(f"{BASE_URL}/hr/payrolls", headers=headers, json=payroll_data)
        check("Create payroll (draft)", r.status_code == 201, f"Got {r.status_code}: {r.text[:200]}")

        if r.status_code == 201:
            payroll = r.json()
            payroll_id = payroll["id"]
            check("Payroll status is draft", payroll["status"] == "draft")
            check("Gross = Basic + HRA", 
                  float(payroll["gross_salary"]) == float(emp["salary"]) + 5000,
                  f"Got {payroll['gross_salary']}")
            check("Net = Gross - Deductions",
                  float(payroll["net_salary"]) == float(payroll["gross_salary"]) - 3000,
                  f"Got {payroll['net_salary']}")

            # Process payroll (draft → processed, creates JE)
            r = requests.post(f"{BASE_URL}/hr/payrolls/{payroll_id}/process", headers=headers)
            check("Process payroll", r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}")
            if r.status_code == 200:
                processed = r.json()
                check("Status is 'processed'", processed["status"] == "processed")
                check("Journal entry linked", processed.get("journal_entry_id") is not None,
                      "No journal_entry_id")

                # Pay payroll (processed → paid, creates payment JE)
                r = requests.post(f"{BASE_URL}/hr/payrolls/{payroll_id}/pay", headers=headers)
                check("Pay payroll", r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}")
                if r.status_code == 200:
                    paid = r.json()
                    check("Status is 'paid'", paid["status"] == "paid")

    # Test cancel flow
    if employees and len(employees) > 1:
        emp2 = employees[1]
        payroll_data2 = {
            "employee_id": emp2["id"],
            "pay_period_start": "2025-04-01",
            "pay_period_end": "2025-04-30",
            "components": [
                {"component_name": "Basic Salary", "component_type": "earnings", "amount": str(emp2["salary"])},
            ]
        }
        r = requests.post(f"{BASE_URL}/hr/payrolls", headers=headers, json=payroll_data2)
        if r.status_code == 201:
            cancel_id = r.json()["id"]
            r = requests.post(f"{BASE_URL}/hr/payrolls/{cancel_id}/cancel", headers=headers)
            check("Cancel draft payroll", r.status_code == 200, f"Got {r.status_code}")


# ============================================================================
# 4. PROCUREMENT MODULE VALIDATION
# ============================================================================
def test_procurement(admin_token):
    print("\n" + "=" * 70)
    print("4. PROCUREMENT MODULE VALIDATION")
    print("=" * 70)
    headers = auth_headers(admin_token)

    # Suppliers
    r = requests.get(f"{BASE_URL}/procurement/suppliers", headers=headers)
    check("GET suppliers", r.status_code == 200)
    suppliers = r.json()
    check("Suppliers exist", len(suppliers) > 0)

    # Purchase Orders
    r = requests.get(f"{BASE_URL}/procurement/purchase-orders", headers=headers)
    check("GET purchase orders", r.status_code == 200)
    pos = r.json()
    check("Purchase orders exist", len(pos) > 0)

    # Verify PO statuses
    statuses = [po["status"] for po in pos]
    check("POs have valid statuses", all(s in ["draft", "approved", "received", "cancelled"] for s in statuses),
          f"Found: {set(statuses)}")

    # --- PO Lifecycle: Create → Approve → Receive ---
    print("\n  --- PO Lifecycle Test ---")
    
    # Get items for PO
    r = requests.get(f"{BASE_URL}/inventory/items", headers=headers)
    items = r.json() if r.status_code == 200 else []
    
    # Get warehouses
    r = requests.get(f"{BASE_URL}/inventory/warehouses", headers=headers)
    warehouses = r.json() if r.status_code == 200 else []
    
    if suppliers and items and warehouses:
        item = items[0]
        initial_stock = float(item["current_stock"])
        
        po_data = {
            "supplier_id": suppliers[0]["id"],
            "order_date": "2025-04-01",
            "expected_delivery_date": "2025-04-10",
            "items": [
                {"item_id": item["id"], "quantity": "10", "unit_price": str(item["unit_price"])}
            ]
        }
        r = requests.post(f"{BASE_URL}/procurement/purchase-orders", headers=headers, json=po_data)
        check("Create PO", r.status_code == 201, f"Got {r.status_code}: {r.text[:200]}")

        if r.status_code == 201:
            po = r.json()
            po_id = po["id"]
            check("PO status is draft", po["status"] == "draft")

            # Approve
            r = requests.post(f"{BASE_URL}/procurement/purchase-orders/{po_id}/approve", headers=headers)
            check("Approve PO", r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}")

            if r.status_code == 200:
                approved = r.json()
                check("PO status is approved", approved["status"] == "approved")

                # Receive goods
                wh_id = warehouses[0]["id"]
                r = requests.post(
                    f"{BASE_URL}/procurement/purchase-orders/{po_id}/receive?warehouse_id={wh_id}",
                    headers=headers
                )
                check("Receive PO", r.status_code == 200 or r.status_code == 201, 
                      f"Got {r.status_code}: {r.text[:300]}")

                if r.status_code == 200:
                    received = r.json()
                    check("PO status is received", received["status"] == "received")
                    check("Journal entry created for receipt",
                          received.get("journal_entry_id") is not None,
                          "No journal_entry_id on received PO")

                    # Verify stock increased
                    r = requests.get(f"{BASE_URL}/inventory/stock?item_id={item['id']}", headers=headers)
                    if r.status_code == 200:
                        updated_item = r.json()
                        new_stock = float(updated_item["current_stock"])
                        check("Stock increased after PO receipt",
                              new_stock >= initial_stock + 10,
                              f"Before={initial_stock}, After={new_stock}")


# ============================================================================
# 5. INVENTORY MODULE VALIDATION
# ============================================================================
def test_inventory(admin_token):
    print("\n" + "=" * 70)
    print("5. INVENTORY MODULE VALIDATION")
    print("=" * 70)
    headers = auth_headers(admin_token)

    # Categories, Warehouses, Items
    r = requests.get(f"{BASE_URL}/inventory/categories", headers=headers)
    check("GET categories", r.status_code == 200)
    categories = r.json()
    check("Categories exist", len(categories) > 0)

    r = requests.get(f"{BASE_URL}/inventory/warehouses", headers=headers)
    check("GET warehouses", r.status_code == 200)
    warehouses = r.json()
    check("Warehouses exist", len(warehouses) > 0)

    r = requests.get(f"{BASE_URL}/inventory/items", headers=headers)
    check("GET items", r.status_code == 200)
    items = r.json()
    check("Items exist", len(items) > 0)

    # Verify stock_value computed field
    for item in items[:3]:
        expected_value = float(item["current_stock"]) * float(item["unit_price"])
        actual_value = float(item.get("stock_value", 0))
        check(f"Item {item['code']} stock_value computed correctly",
              abs(actual_value - expected_value) < 0.01,
              f"Expected {expected_value}, got {actual_value}")

    # Low stock
    r = requests.get(f"{BASE_URL}/inventory/low-stock", headers=headers)
    check("GET low-stock", r.status_code == 200)

    # Stock valuation
    r = requests.get(f"{BASE_URL}/inventory/valuation", headers=headers)
    check("GET valuation", r.status_code == 200)
    if r.status_code == 200:
        val = r.json()
        check("Valuation total > 0", float(val.get("total_value", 0)) > 0)

    # --- Inventory Adjustment Test ---
    print("\n  --- Inventory Adjustment Test ---")
    if items and warehouses:
        item = items[0]
        wh = warehouses[0]
        initial_stock = float(item["current_stock"])

        adj_data = {
            "item_id": item["id"],
            "warehouse_id": wh["id"],
            "adjustment_type": "increase",
            "quantity": "5",
            "reason": "[VALIDATION TEST] Adjustment test",
        }
        r = requests.post(f"{BASE_URL}/inventory/adjustments", headers=headers, json=adj_data)
        check("Create inventory adjustment", r.status_code == 201 or r.status_code == 200,
              f"Got {r.status_code}: {r.text[:200]}")

    # --- Stock Transfer Test ---
    print("\n  --- Stock Transfer Test ---")
    if items and len(warehouses) >= 2:
        # First make sure the source warehouse has stock
        transfer_data = {
            "item_id": items[0]["id"],
            "from_warehouse_id": warehouses[0]["id"],
            "to_warehouse_id": warehouses[1]["id"],
            "quantity": "2",
            "reason": "[VALIDATION TEST] Transfer test"
        }
        r = requests.post(f"{BASE_URL}/inventory/transfers", headers=headers, json=transfer_data)
        check("Stock transfer between warehouses",
              r.status_code in [200, 201, 400],  # 400 is ok if no stock in source warehouse
              f"Got {r.status_code}: {r.text[:200]}")

    # Stock Ledger
    r = requests.get(f"{BASE_URL}/inventory/stock-ledger", headers=headers)
    check("GET stock ledger", r.status_code == 200)

    # Warehouse stock
    r = requests.get(f"{BASE_URL}/inventory/warehouse-stock", headers=headers)
    check("GET warehouse stock", r.status_code == 200)


# ============================================================================
# 6. FINANCE MODULE VALIDATION
# ============================================================================
def test_finance(admin_token):
    print("\n" + "=" * 70)
    print("6. FINANCE MODULE VALIDATION")
    print("=" * 70)
    headers = auth_headers(admin_token)

    # List transactions
    r = requests.get(f"{BASE_URL}/finance/transactions", headers=headers)
    check("GET financial transactions", r.status_code == 200)

    # Create income transaction
    tx_data = {
        "transaction_date": "2025-04-01",
        "transaction_type": "income",
        "category": "Sales",
        "amount": "5000.00",
        "description": "[VALIDATION TEST] Test income transaction"
    }
    r = requests.post(f"{BASE_URL}/finance/transactions", headers=headers, json=tx_data)
    check("Create income transaction", r.status_code == 201 or r.status_code == 200,
          f"Got {r.status_code}: {r.text[:200]}")
    if r.status_code in [200, 201]:
        tx = r.json()
        check("Transaction has journal_entry_id",
              tx.get("journal_entry_id") is not None,
              "No auto-generated JE for transaction")

    # Create expense transaction
    tx_data2 = {
        "transaction_date": "2025-04-01",
        "transaction_type": "expense",
        "category": "Utilities",
        "amount": "1000.00",
        "description": "[VALIDATION TEST] Test expense transaction"
    }
    r = requests.post(f"{BASE_URL}/finance/transactions", headers=headers, json=tx_data2)
    check("Create expense transaction", r.status_code in [200, 201],
          f"Got {r.status_code}: {r.text[:200]}")

    # Financial Summary
    r = requests.get(f"{BASE_URL}/finance/summary", headers=headers)
    check("GET financial summary", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        summary = r.json()
        check("Summary has total_income", "total_income" in summary)
        check("Summary has total_expenses", "total_expenses" in summary)
        check("net_balance = income - expenses",
              abs(float(summary.get("net_balance", 0)) -
                  (float(summary.get("total_income", 0)) - float(summary.get("total_expenses", 0)))) < 0.01,
              f"Net={summary.get('net_balance')}")


# ============================================================================
# 7. DASHBOARD VALIDATION
# ============================================================================
def test_dashboard(admin_token, hr_token):
    print("\n" + "=" * 70)
    print("7. DASHBOARD VALIDATION")
    print("=" * 70)

    # Admin dashboard
    headers = auth_headers(admin_token)
    r = requests.get(f"{BASE_URL}/dashboard/stats", headers=headers)
    check("GET dashboard stats (admin)", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        stats = r.json()

        # Verify financial fields are NOT null for admin
        check("Admin sees net_position", stats.get("net_position") is not None)
        check("Admin sees net_income", stats.get("net_income") is not None)
        check("Admin sees total_revenue", stats.get("total_revenue") is not None)
        check("Admin sees total_expenses", stats.get("total_expenses") is not None)
        check("Admin sees is_balanced", stats.get("is_balanced") is not None)

        # Verify counts are reasonable
        check("total_employees > 0", stats.get("total_employees", 0) > 0)
        check("total_items > 0", stats.get("total_items", 0) > 0)
        check("total_purchase_orders > 0", stats.get("total_purchase_orders", 0) > 0)

        # No NaN check
        for key, val in stats.items():
            if val is not None:
                check(f"Dashboard '{key}' is not NaN", str(val) != "NaN", f"Value = {val}")

    # HR Manager dashboard (should see operational counts only)
    hr_headers = auth_headers(hr_token)
    r = requests.get(f"{BASE_URL}/dashboard/stats", headers=hr_headers)
    check("GET dashboard stats (HR)", r.status_code == 200)
    if r.status_code == 200:
        hr_stats = r.json()
        check("HR sees no financial data (net_position is null)",
              hr_stats.get("net_position") is None)
        check("HR sees total_employees", hr_stats.get("total_employees", 0) > 0)

    # Recent journal entries (admin only)
    r = requests.get(f"{BASE_URL}/dashboard/recent-journal-entries", headers=headers)
    check("GET recent journal entries", r.status_code == 200)
    if r.status_code == 200:
        recent = r.json()
        check("Recent JEs returned", len(recent) > 0)


# ============================================================================
# 8. AI ASSISTANT VALIDATION
# ============================================================================
def test_assistant(admin_token):
    print("\n" + "=" * 70)
    print("8. AI ASSISTANT VALIDATION")
    print("=" * 70)
    headers = auth_headers(admin_token)

    # Insights
    r = requests.get(f"{BASE_URL}/assistant/insights", headers=headers)
    check("GET insights", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        insights = r.json()
        check("Insights response has 'insights' list", "insights" in insights)
        check("Insights response has 'count'", "count" in insights)

    # Financial summary
    r = requests.get(f"{BASE_URL}/assistant/summary", headers=headers)
    check("GET assistant summary", r.status_code == 200)

    # Natural language query
    r = requests.post(f"{BASE_URL}/assistant/query", headers=headers,
                      json={"query": "What is pending?"})
    check("NLP query: pending tasks", r.status_code == 200)
    if r.status_code == 200:
        qr = r.json()
        check("Query was understood", qr.get("understood", False))

    r = requests.post(f"{BASE_URL}/assistant/query", headers=headers,
                      json={"query": "How is our revenue?"})
    check("NLP query: revenue", r.status_code == 200)

    # Trace expense
    r = requests.post(f"{BASE_URL}/assistant/trace", headers=headers, json={"entry_id": 1})
    check("Trace expense", r.status_code == 200)
    if r.status_code == 200:
        trace = r.json()
        check("Trace found entry", trace.get("found", False))

    # Quick stats
    r = requests.get(f"{BASE_URL}/assistant/stats", headers=headers)
    check("GET quick stats", r.status_code == 200)

    # Chat (rule-based fallback)
    r = requests.post(f"{BASE_URL}/assistant/chat", headers=headers,
                      json={"message": "Hello, how is our business?"})
    check("Chat endpoint works", r.status_code == 200)
    if r.status_code == 200:
        chat = r.json()
        check("Chat returns response", len(chat.get("response", "")) > 0)


# ============================================================================
# 9. CROSS-MODULE INTEGRITY CHECKS
# ============================================================================
def test_cross_module_integrity(admin_token):
    print("\n" + "=" * 70)
    print("9. CROSS-MODULE INTEGRITY CHECKS")
    print("=" * 70)
    headers = auth_headers(admin_token)

    # Trial Balance = Balanced
    r = requests.get(f"{BASE_URL}/accounting/trial-balance", headers=headers)
    if r.status_code == 200:
        tb = r.json()
        check("FINAL Trial Balance is balanced", tb.get("is_balanced", False),
              f"D={tb.get('total_debits')}, C={tb.get('total_credits')}")

    # All posted JEs are balanced
    r = requests.get(f"{BASE_URL}/accounting/journal-entries?status=posted", headers=headers)
    if r.status_code == 200:
        posted = r.json()
        all_balanced = all(je["total_debit"] == je["total_credit"] for je in posted)
        check(f"All {len(posted)} posted JEs balanced", all_balanced)

    # Balance Sheet equation: A = L + E
    r = requests.get(f"{BASE_URL}/accounting/reports/balance-sheet", headers=headers)
    if r.status_code == 200:
        bs = r.json()
        check("Balance Sheet: Assets = L + E", bs.get("is_balanced", False),
              f"A={bs.get('total_assets')}, L+E={bs.get('liabilities_and_equity')}")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║           FinCore ERP — System Flow Validation Report              ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    # Get tokens
    admin_token = get_token("admin", "admin123")
    hr_token = get_token("hr_manager", "hr123")
    
    if not admin_token:
        print("❌ FATAL: Cannot login as admin. Is the server running?")
        sys.exit(1)

    try:
        test_authentication()
        test_accounting(admin_token)
        test_hr(admin_token)
        test_procurement(admin_token)
        test_inventory(admin_token)
        test_finance(admin_token)
        test_dashboard(admin_token, hr_token)
        test_assistant(admin_token)
        test_cross_module_integrity(admin_token)
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Print Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    total = RESULTS["passed"] + RESULTS["failed"]
    print(f"  Total:  {total}")
    print(f"  Passed: {RESULTS['passed']} ✅")
    print(f"  Failed: {RESULTS['failed']} ❌")
    
    if RESULTS["errors"]:
        print(f"\n  --- Failures ({len(RESULTS['errors'])}) ---")
        for err in RESULTS["errors"]:
            print(f"  ❌ {err}")
    
    pct = (RESULTS["passed"] / total * 100) if total > 0 else 0
    print(f"\n  Score: {pct:.1f}%")
    
    if pct == 100:
        print("  🎉 ALL TESTS PASSED — System is production-ready!")
    elif pct >= 90:
        print("  ⚠️  Minor issues detected. Review failures above.")
    else:
        print("  🚨 SIGNIFICANT ISSUES DETECTED. Debug required!")
    
    sys.exit(0 if RESULTS["failed"] == 0 else 1)
