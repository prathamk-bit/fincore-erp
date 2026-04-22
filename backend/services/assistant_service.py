"""
FinCore AI Assistant Service.

Provides intelligent financial insights, anomaly detection, pending task
identification, and recommendations using rule-based logic with optional
AI-powered natural language understanding.
"""

import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.accounting import Account, JournalEntry, JournalEntryLine
from backend.models.hr import Payroll, Employee
from backend.models.inventory import Item
from backend.models.procurement import PurchaseOrder, Supplier


# ---------------------------------------------------------------------------
# Role-based insight categories
# ---------------------------------------------------------------------------

ROLE_INSIGHTS = {
    "admin": ["all"],
    "accountant": ["financial", "journal", "anomaly"],
    "hr_manager": ["payroll", "employee"],
    "inventory_manager": ["inventory", "procurement"],
}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _get_month_range(months_ago: int = 0) -> Tuple[date, date]:
    """Get the start and end date for a month relative to current."""
    today = date.today()
    year = today.year
    month = today.month - months_ago
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    return start_date, end_date


def _safe_decimal(value: Any) -> Decimal:
    """Safely convert a value to Decimal."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _format_currency(amount: Decimal) -> str:
    """Format a decimal as currency string."""
    try:
        return f"₹{float(amount):,.2f}"
    except Exception:
        return "₹0.00"


def _calculate_percentage_change(current: Decimal, previous: Decimal) -> Optional[float]:
    """Calculate percentage change between two values."""
    try:
        if previous == 0 or previous is None:
            return None
        return float((current - previous) / previous * 100)
    except Exception:
        return None


def _check_role_access(user_role: str, category: str) -> bool:
    """Check if user role has access to a category."""
    allowed = ROLE_INSIGHTS.get(user_role, [])
    return "all" in allowed or category in allowed


# ---------------------------------------------------------------------------
# Pending Task Detection
# ---------------------------------------------------------------------------

def get_pending_tasks(db: Session, user_role: str) -> List[Dict[str, Any]]:
    """Detect pending tasks across the system."""
    insights = []
    
    # 1. Unposted journal entries
    if _check_role_access(user_role, "financial") or _check_role_access(user_role, "journal"):
        try:
            unposted_count = db.query(func.count(JournalEntry.id)).filter(
                JournalEntry.status == "draft"
            ).scalar() or 0
            
            if unposted_count > 0:
                insights.append({
                    "type": "warning",
                    "category": "journal",
                    "title": "Pending Journal Entries",
                    "message": f"{unposted_count} journal {'entries are' if unposted_count > 1 else 'entry is'} pending posting",
                    "action": "Review and post pending journal entries",
                    "count": unposted_count,
                    "priority": 1,
                })
        except Exception:
            pass
    
    # 2. Pending payrolls
    if _check_role_access(user_role, "payroll"):
        try:
            draft_payrolls = db.query(func.count(Payroll.id)).filter(
                Payroll.status == "draft"
            ).scalar() or 0
            
            processed_payrolls = db.query(func.count(Payroll.id)).filter(
                Payroll.status == "processed"
            ).scalar() or 0
            
            if draft_payrolls > 0:
                insights.append({
                    "type": "warning",
                    "category": "payroll",
                    "title": "Draft Payrolls",
                    "message": f"{draft_payrolls} payroll{'s are' if draft_payrolls > 1 else ' is'} in draft status",
                    "action": "Process draft payrolls",
                    "count": draft_payrolls,
                    "priority": 1,
                })
            
            if processed_payrolls > 0:
                insights.append({
                    "type": "warning",
                    "category": "payroll",
                    "title": "Unpaid Payrolls",
                    "message": f"{processed_payrolls} payroll{'s are' if processed_payrolls > 1 else ' is'} processed but not paid",
                    "action": "Complete payment for processed payrolls",
                    "count": processed_payrolls,
                    "priority": 2,
                })
        except Exception:
            pass
    
    # 3. Unapproved purchase orders
    if _check_role_access(user_role, "procurement"):
        try:
            draft_pos = db.query(func.count(PurchaseOrder.id)).filter(
                PurchaseOrder.status == "draft"
            ).scalar() or 0
            
            approved_pos = db.query(func.count(PurchaseOrder.id)).filter(
                PurchaseOrder.status == "approved"
            ).scalar() or 0
            
            if draft_pos > 0:
                insights.append({
                    "type": "warning",
                    "category": "procurement",
                    "title": "Pending Approvals",
                    "message": f"{draft_pos} purchase order{'s need' if draft_pos > 1 else ' needs'} approval",
                    "action": "Review and approve pending purchase orders",
                    "count": draft_pos,
                    "priority": 1,
                })
            
            if approved_pos > 0:
                insights.append({
                    "type": "info",
                    "category": "procurement",
                    "title": "Awaiting Receipt",
                    "message": f"{approved_pos} approved PO{'s are' if approved_pos > 1 else ' is'} awaiting goods receipt",
                    "action": "Receive goods for approved purchase orders",
                    "count": approved_pos,
                    "priority": 3,
                })
        except Exception:
            pass
    
    # 4. Low stock items
    if _check_role_access(user_role, "inventory"):
        try:
            low_stock_items = db.query(Item).filter(
                Item.current_stock <= Item.reorder_level,
                Item.is_active == True
            ).limit(10).all()
            
            if low_stock_items:
                item_list = ", ".join([f"'{item.name}'" for item in low_stock_items[:3]])
                if len(low_stock_items) > 3:
                    item_list += f" and {len(low_stock_items) - 3} more"
                
                insights.append({
                    "type": "warning",
                    "category": "inventory",
                    "title": "Low Stock Alert",
                    "message": f"{len(low_stock_items)} item{'s are' if len(low_stock_items) > 1 else ' is'} below reorder level: {item_list}",
                    "action": "Create purchase orders for low stock items",
                    "count": len(low_stock_items),
                    "priority": 1,
                })
        except Exception:
            pass
    
    insights.sort(key=lambda x: x.get("priority", 99))
    return insights


# ---------------------------------------------------------------------------
# Financial Anomaly Detection
# ---------------------------------------------------------------------------

def detect_anomalies(db: Session) -> List[Dict[str, Any]]:
    """Detect financial anomalies using rule-based logic."""
    insights = []
    
    try:
        curr_start, curr_end = _get_month_range(0)
        last_start, last_end = _get_month_range(1)
        
        expense_accounts = db.query(Account).filter(Account.account_type == "expense").all()
        expense_ids = [a.id for a in expense_accounts]
        
        revenue_accounts = db.query(Account).filter(Account.account_type == "revenue").all()
        revenue_ids = [a.id for a in revenue_accounts]
        
        # Current month totals
        current_expenses = Decimal("0")
        current_revenue = Decimal("0")
        
        if expense_ids:
            result = db.query(func.coalesce(func.sum(JournalEntryLine.debit), 0)).join(
                JournalEntry
            ).filter(
                JournalEntryLine.account_id.in_(expense_ids),
                JournalEntry.date >= curr_start,
                JournalEntry.date <= curr_end,
                JournalEntry.status == "posted"
            ).scalar()
            current_expenses = _safe_decimal(result)
        
        if revenue_ids:
            result = db.query(func.coalesce(func.sum(JournalEntryLine.credit), 0)).join(
                JournalEntry
            ).filter(
                JournalEntryLine.account_id.in_(revenue_ids),
                JournalEntry.date >= curr_start,
                JournalEntry.date <= curr_end,
                JournalEntry.status == "posted"
            ).scalar()
            current_revenue = _safe_decimal(result)
        
        # Last month totals
        last_expenses = Decimal("0")
        last_revenue = Decimal("0")
        
        if expense_ids:
            result = db.query(func.coalesce(func.sum(JournalEntryLine.debit), 0)).join(
                JournalEntry
            ).filter(
                JournalEntryLine.account_id.in_(expense_ids),
                JournalEntry.date >= last_start,
                JournalEntry.date <= last_end,
                JournalEntry.status == "posted"
            ).scalar()
            last_expenses = _safe_decimal(result)
        
        if revenue_ids:
            result = db.query(func.coalesce(func.sum(JournalEntryLine.credit), 0)).join(
                JournalEntry
            ).filter(
                JournalEntryLine.account_id.in_(revenue_ids),
                JournalEntry.date >= last_start,
                JournalEntry.date <= last_end,
                JournalEntry.status == "posted"
            ).scalar()
            last_revenue = _safe_decimal(result)
        
        # Expense spike detection (>50% increase)
        if last_expenses > 0:
            expense_change = _calculate_percentage_change(current_expenses, last_expenses)
            if expense_change and expense_change > 50:
                insights.append({
                    "type": "warning",
                    "category": "anomaly",
                    "title": "Expense Spike",
                    "message": f"Expenses increased by {expense_change:.0f}% vs last month ({_format_currency(last_expenses)} → {_format_currency(current_expenses)})",
                    "severity": "high" if expense_change > 100 else "medium",
                    "priority": 1,
                })
        
        # Revenue drop detection (>30% decrease)
        if last_revenue > 0:
            revenue_change = _calculate_percentage_change(current_revenue, last_revenue)
            if revenue_change and revenue_change < -30:
                insights.append({
                    "type": "warning",
                    "category": "anomaly",
                    "title": "Revenue Decline",
                    "message": f"Revenue decreased by {abs(revenue_change):.0f}% vs last month ({_format_currency(last_revenue)} → {_format_currency(current_revenue)})",
                    "severity": "high",
                    "priority": 1,
                })
        
        # Negative profit warning
        current_profit = current_revenue - current_expenses
        if current_revenue > 0 and current_profit < 0:
            insights.append({
                "type": "warning",
                "category": "anomaly",
                "title": "Negative Profit",
                "message": f"Operating at a loss: {_format_currency(current_profit)}",
                "severity": "high",
                "priority": 1,
            })
    
    except Exception:
        pass
    
    return insights


# ---------------------------------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------------------------------

def get_recommendations(db: Session, user_role: str) -> List[Dict[str, Any]]:
    """Generate actionable recommendations."""
    insights = []
    
    # Stock reorder recommendations
    if _check_role_access(user_role, "inventory"):
        try:
            critical_stock = db.query(Item).filter(
                Item.current_stock <= Item.reorder_level * Decimal("0.3"),
                Item.is_active == True
            ).limit(3).all()
            
            for item in critical_stock:
                reorder_qty = _safe_decimal(item.reorder_level) * Decimal("2") - _safe_decimal(item.current_stock)
                insights.append({
                    "type": "recommendation",
                    "category": "inventory",
                    "title": f"Reorder: {item.name}",
                    "message": f"Only {_safe_decimal(item.current_stock):.0f} units left. Suggest ordering {reorder_qty:.0f} units.",
                    "priority": 1,
                })
        except Exception:
            pass
    
    # Month-end payroll reminder
    if _check_role_access(user_role, "payroll"):
        try:
            today = date.today()
            if today.day >= 25:
                pending = db.query(func.count(Payroll.id)).filter(
                    Payroll.status.in_(["draft", "processed"])
                ).scalar() or 0
                
                if pending > 0:
                    insights.append({
                        "type": "recommendation",
                        "category": "payroll",
                        "title": "Month-End Payroll",
                        "message": f"Month-end approaching. {pending} payroll{'s' if pending > 1 else ''} still pending.",
                        "priority": 1,
                    })
        except Exception:
            pass
    
    return insights


# ---------------------------------------------------------------------------
# Financial Summary
# ---------------------------------------------------------------------------

def get_financial_summary(db: Session) -> Dict[str, Any]:
    """Get financial summary with month-over-month comparison."""
    summary = {
        "current_month": {"revenue": 0, "expenses": 0, "profit": 0, "period": ""},
        "last_month": {"revenue": 0, "expenses": 0, "profit": 0, "period": ""},
        "changes": {"revenue": None, "expenses": None, "profit": None},
        "insights": [],
        "health_score": 50,
    }
    
    try:
        curr_start, curr_end = _get_month_range(0)
        last_start, last_end = _get_month_range(1)
        
        summary["current_month"]["period"] = curr_start.strftime("%b %Y")
        summary["last_month"]["period"] = last_start.strftime("%b %Y")
        
        revenue_ids = [a.id for a in db.query(Account).filter(Account.account_type == "revenue").all()]
        expense_ids = [a.id for a in db.query(Account).filter(Account.account_type == "expense").all()]
        
        # Current month
        if revenue_ids:
            result = db.query(func.coalesce(func.sum(JournalEntryLine.credit), 0)).join(
                JournalEntry
            ).filter(
                JournalEntryLine.account_id.in_(revenue_ids),
                JournalEntry.date >= curr_start,
                JournalEntry.date <= curr_end,
                JournalEntry.status == "posted"
            ).scalar()
            summary["current_month"]["revenue"] = float(_safe_decimal(result))
        
        if expense_ids:
            result = db.query(func.coalesce(func.sum(JournalEntryLine.debit), 0)).join(
                JournalEntry
            ).filter(
                JournalEntryLine.account_id.in_(expense_ids),
                JournalEntry.date >= curr_start,
                JournalEntry.date <= curr_end,
                JournalEntry.status == "posted"
            ).scalar()
            summary["current_month"]["expenses"] = float(_safe_decimal(result))
        
        summary["current_month"]["profit"] = summary["current_month"]["revenue"] - summary["current_month"]["expenses"]
        
        # Last month
        if revenue_ids:
            result = db.query(func.coalesce(func.sum(JournalEntryLine.credit), 0)).join(
                JournalEntry
            ).filter(
                JournalEntryLine.account_id.in_(revenue_ids),
                JournalEntry.date >= last_start,
                JournalEntry.date <= last_end,
                JournalEntry.status == "posted"
            ).scalar()
            summary["last_month"]["revenue"] = float(_safe_decimal(result))
        
        if expense_ids:
            result = db.query(func.coalesce(func.sum(JournalEntryLine.debit), 0)).join(
                JournalEntry
            ).filter(
                JournalEntryLine.account_id.in_(expense_ids),
                JournalEntry.date >= last_start,
                JournalEntry.date <= last_end,
                JournalEntry.status == "posted"
            ).scalar()
            summary["last_month"]["expenses"] = float(_safe_decimal(result))
        
        summary["last_month"]["profit"] = summary["last_month"]["revenue"] - summary["last_month"]["expenses"]
        
        # Calculate changes
        if summary["last_month"]["revenue"] > 0:
            summary["changes"]["revenue"] = _calculate_percentage_change(
                Decimal(str(summary["current_month"]["revenue"])),
                Decimal(str(summary["last_month"]["revenue"]))
            )
        
        if summary["last_month"]["expenses"] > 0:
            summary["changes"]["expenses"] = _calculate_percentage_change(
                Decimal(str(summary["current_month"]["expenses"])),
                Decimal(str(summary["last_month"]["expenses"]))
            )
        
        # Generate insights
        rev_change = summary["changes"]["revenue"]
        exp_change = summary["changes"]["expenses"]
        
        if rev_change is not None:
            direction = "increased" if rev_change > 0 else "decreased"
            summary["insights"].append({
                "type": "insight" if rev_change >= 0 else "warning",
                "message": f"Revenue {direction} by {abs(rev_change):.1f}% vs {summary['last_month']['period']}",
            })
        
        if exp_change is not None:
            direction = "increased" if exp_change > 0 else "decreased"
            summary["insights"].append({
                "type": "warning" if exp_change > 20 else "insight",
                "message": f"Expenses {direction} by {abs(exp_change):.1f}% vs {summary['last_month']['period']}",
            })
        
        curr_profit = summary["current_month"]["profit"]
        if curr_profit > 0:
            summary["insights"].append({
                "type": "success",
                "message": f"Net profit: {_format_currency(Decimal(str(curr_profit)))}",
            })
        elif curr_profit < 0:
            summary["insights"].append({
                "type": "warning",
                "message": f"Net loss: {_format_currency(Decimal(str(abs(curr_profit))))}",
            })
        
        # Health score
        health = 50
        if rev_change and rev_change > 0:
            health += min(20, rev_change / 2)
        if exp_change and exp_change < 0:
            health += min(15, abs(exp_change) / 2)
        if curr_profit > 0:
            health += 15
        elif curr_profit < 0:
            health -= 20
        
        summary["health_score"] = max(0, min(100, int(health)))
    
    except Exception:
        pass
    
    return summary


# ---------------------------------------------------------------------------
# Expense Traceability
# ---------------------------------------------------------------------------

def trace_expense(db: Session, entry_id: int) -> Dict[str, Any]:
    """Trace an expense back to its source module."""
    result = {"entry_id": entry_id, "found": False, "source": None, "details": None, "entry": None, "lines": []}
    
    try:
        entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        if not entry:
            return result
        
        result["found"] = True
        result["entry"] = {
            "id": entry.id,
            "date": entry.entry_date.isoformat() if entry.entry_date else None,
            "description": entry.description,
            "status": entry.status,
        }
        
        if entry.reference_type:
            result["source"] = {"type": entry.reference_type, "id": entry.reference_id}
            
            if entry.reference_type == "payroll":
                payroll = db.query(Payroll).filter(Payroll.id == entry.reference_id).first()
                if payroll:
                    employee = db.query(Employee).filter(Employee.id == payroll.employee_id).first()
                    result["details"] = {
                        "module": "Payroll",
                        "employee": f"{employee.first_name} {employee.last_name}" if employee else f"Employee #{payroll.employee_id}",
                        "gross_salary": float(payroll.gross_salary),
                        "net_salary": float(payroll.net_salary),
                    }
            
            elif entry.reference_type in ["purchase_order", "purchase_order_receipt"]:
                po = db.query(PurchaseOrder).filter(PurchaseOrder.id == entry.reference_id).first()
                if po:
                    supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
                    result["details"] = {
                        "module": "Procurement",
                        "po_number": po.po_number,
                        "supplier": supplier.name if supplier else f"Supplier #{po.supplier_id}",
                        "total_amount": float(po.total_amount),
                    }
        
        lines = db.query(JournalEntryLine).filter(JournalEntryLine.journal_entry_id == entry_id).all()
        for line in lines:
            account = db.query(Account).filter(Account.id == line.account_id).first()
            result["lines"].append({
                "account": account.name if account else f"Account #{line.account_id}",
                "debit": float(line.debit) if line.debit else 0,
                "credit": float(line.credit) if line.credit else 0,
            })
    
    except Exception:
        pass
    
    return result


# ---------------------------------------------------------------------------
# Natural Language Query Processing
# ---------------------------------------------------------------------------

QUERY_PATTERNS = {
    "pending": ["pending", "outstanding", "waiting", "draft", "incomplete", "todo", "to do"],
    "summary": ["summary", "overview", "financial overview", "financial summary", "dashboard", "how are we doing"],
    "anomaly": ["issue", "problem", "anomaly", "unusual", "spike", "concern", "wrong", "alert"],
    "recommendation": ["suggest", "recommendation", "should", "advice", "improve", "tip", "help"],
    "revenue": ["revenue", "income", "sales", "earning"],
    "expense": ["expense", "cost", "spending", "expenditure"],
    "profit": ["profit", "loss", "net", "margin"],
    "payroll": ["payroll", "salary", "wage", "employee pay", "hr"],
    "inventory": ["inventory", "stock", "item", "warehouse", "product"],
    "purchase": ["purchase", "procurement", "order", "supplier", "po", "buy"],
    "health": ["health", "score", "rating", "performance"],
}


def process_query(db: Session, query: str, user_role: str) -> Dict[str, Any]:
    """Process a natural language query."""
    query_lower = query.lower().strip()
    response = {"query": query, "understood": False, "intent": [], "results": [], "summary": None}
    
    # Detect intents
    detected = []
    for intent, keywords in QUERY_PATTERNS.items():
        if any(kw in query_lower for kw in keywords):
            detected.append(intent)
    
    if not detected:
        response["results"] = [{
            "type": "info",
            "message": "I can help with: pending tasks, financial summary, anomalies, recommendations, revenue, expenses, inventory, payroll, and purchase orders.",
        }]
        return response
    
    response["understood"] = True
    response["intent"] = detected
    
    if "pending" in detected:
        pending = get_pending_tasks(db, user_role)
        if pending:
            response["results"].extend(pending)
        else:
            response["results"].append({"type": "success", "message": "No pending tasks. All caught up!"})
    
    if any(i in detected for i in ["summary", "health", "revenue", "expense", "profit"]):
        summary = get_financial_summary(db)
        response["summary"] = summary
        
        curr = summary.get("current_month", {})
        
        if "revenue" in detected:
            response["results"].append({
                "type": "info",
                "message": f"Revenue this month: {_format_currency(Decimal(str(curr.get('revenue', 0))))}",
            })
        
        if "expense" in detected:
            response["results"].append({
                "type": "info",
                "message": f"Expenses this month: {_format_currency(Decimal(str(curr.get('expenses', 0))))}",
            })
        
        if "profit" in detected:
            profit = curr.get("profit", 0)
            response["results"].append({
                "type": "success" if profit >= 0 else "warning",
                "message": f"Net {'profit' if profit >= 0 else 'loss'}: {_format_currency(Decimal(str(abs(profit))))}",
            })
        
        if "health" in detected:
            score = summary.get("health_score", 0)
            status = "Excellent" if score >= 80 else ("Good" if score >= 60 else "Needs Attention")
            response["results"].append({
                "type": "success" if score >= 60 else "warning",
                "message": f"Financial Health: {score}/100 ({status})",
            })
        
        if "summary" in detected:
            response["results"].extend(summary.get("insights", []))
    
    if "anomaly" in detected:
        anomalies = detect_anomalies(db)
        if anomalies:
            response["results"].extend(anomalies)
        else:
            response["results"].append({"type": "success", "message": "No anomalies detected."})
    
    if "recommendation" in detected:
        recommendations = get_recommendations(db, user_role)
        if recommendations:
            response["results"].extend(recommendations)
        else:
            response["results"].append({"type": "info", "message": "No specific recommendations at this time."})
    
    if "payroll" in detected:
        pending = get_pending_tasks(db, "hr_manager")
        payroll_items = [p for p in pending if p.get("category") == "payroll"]
        if payroll_items:
            response["results"].extend(payroll_items)
        else:
            response["results"].append({"type": "success", "message": "All payrolls processed and paid."})
    
    if "inventory" in detected:
        pending = get_pending_tasks(db, "inventory_manager")
        inv_items = [p for p in pending if p.get("category") == "inventory"]
        if inv_items:
            response["results"].extend(inv_items)
        else:
            response["results"].append({"type": "success", "message": "Inventory levels healthy."})
    
    if "purchase" in detected:
        pending = get_pending_tasks(db, "inventory_manager")
        po_items = [p for p in pending if p.get("category") == "procurement"]
        if po_items:
            response["results"].extend(po_items)
        else:
            response["results"].append({"type": "success", "message": "No pending purchase orders."})
    
    # Deduplicate
    seen = set()
    unique = []
    for r in response["results"]:
        key = r.get("message", "")
        if key not in seen:
            seen.add(key)
            unique.append(r)
    response["results"] = unique
    
    return response


# ---------------------------------------------------------------------------
# Main Insight Generator
# ---------------------------------------------------------------------------

def generate_insights(db: Session, user_role: str) -> List[Dict[str, Any]]:
    """Main entry point for generating all insights."""
    all_insights = []
    
    try:
        pending = get_pending_tasks(db, user_role)
        all_insights.extend(pending)
        
        if _check_role_access(user_role, "financial") or _check_role_access(user_role, "anomaly"):
            anomalies = detect_anomalies(db)
            all_insights.extend(anomalies)
        
        recommendations = get_recommendations(db, user_role)
        all_insights.extend(recommendations)
        
        if _check_role_access(user_role, "financial"):
            summary = get_financial_summary(db)
            for insight in summary.get("insights", []):
                insight["category"] = "summary"
                all_insights.append(insight)
    
    except Exception:
        all_insights.append({
            "type": "warning",
            "category": "system",
            "message": "Some insights could not be generated.",
        })
    
    type_priority = {"warning": 0, "recommendation": 1, "insight": 2, "success": 3, "info": 4}
    all_insights.sort(key=lambda x: (type_priority.get(x.get("type", "info"), 5), x.get("priority", 99)))
    
    return all_insights
