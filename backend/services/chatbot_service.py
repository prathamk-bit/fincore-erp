"""
FinCore AI Chatbot Service.

Intelligent chatbot powered by OpenAI GPT that can answer any business question
by querying the database and generating contextual responses.
"""

import os
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import text, func
from sqlalchemy.orm import Session

from backend.models.accounting import Account, JournalEntry, JournalEntryLine
from backend.models.hr import Employee, Payroll, Department
from backend.models.inventory import Item
from backend.models.procurement import PurchaseOrder, Supplier

# Check for OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


# ---------------------------------------------------------------------------
# Database Schema Context for the AI
# ---------------------------------------------------------------------------

DATABASE_SCHEMA = """
You have access to a business ERP system database with these tables:

1. EMPLOYEES (employees):
   - id, employee_id, first_name, last_name, email, phone, department, position
   - hire_date, salary (monthly), is_active, created_at

2. PAYROLL (payrolls):
   - id, employee_id, pay_period_start, pay_period_end, gross_salary, total_deductions
   - net_salary, status (draft/processed/paid), payment_date, created_at

3. ITEMS/INVENTORY (items):
   - id, sku, name, description, category, unit_price, cost_price
   - current_stock, reorder_level, is_active

4. SUPPLIERS (suppliers):
   - id, name, contact_person, email, phone, address, is_active

5. PURCHASE ORDERS (purchase_orders):
   - id, po_number, supplier_id, order_date, expected_date, status (draft/approved/received/cancelled)
   - total_amount, notes

6. ACCOUNTS (accounts):
   - id, account_number, name, account_type (asset/liability/equity/revenue/expense)
   - balance, is_active

7. JOURNAL ENTRIES (journal_entries):
   - id, entry_number, date, description, status (draft/posted)
   - reference_type, reference_id, total_debit, total_credit

8. JOURNAL ENTRY LINES (journal_entry_lines):
   - id, journal_entry_id, account_id, description, debit, credit

9. USERS (users):
   - id, username, email, role (admin/accountant/hr_manager/inventory_manager), is_active
"""

SYSTEM_PROMPT = """You are FinCore AI, a friendly and intelligent business assistant for an ERP system called FreshBite Foods.
You help users understand their business data and provide a great conversational experience.

Your personality:
- Friendly, helpful, and professional
- You greet users warmly and remember conversation context
- You can have casual conversations while still being helpful about business topics
- Use emojis occasionally to make responses more engaging

You can help with:
- Financial performance (revenue, expenses, profit)
- Employee and payroll information
- Inventory and stock levels
- Purchase orders and suppliers
- Accounting entries and transactions
- General business questions and advice

{schema}

When answering:
1. Be conversational and friendly
2. Use actual numbers from the data when available
3. Provide business insights and recommendations when relevant
4. Format currency as ₹ (Indian Rupees)
5. If you don't have enough data, say so clearly
6. For greetings like "hi", "hello", respond warmly and offer to help
7. For "thanks" or "bye", respond appropriately

Current date: {current_date}
"""


# ---------------------------------------------------------------------------
# Data Extraction Functions
# ---------------------------------------------------------------------------

def get_business_context(db: Session) -> Dict[str, Any]:
    """Extract current business state for AI context."""
    context = {}
    
    try:
        # Current month range
        today = date.today()
        month_start = date(today.year, today.month, 1)
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        
        # Employee stats
        total_employees = db.query(func.count(Employee.id)).filter(Employee.is_active == True).scalar() or 0
        context["employees"] = {
            "total_active": total_employees,
            "departments": []
        }
        
        # Get department breakdown
        dept_query = db.query(
            Department.name, 
            func.count(Employee.id)
        ).join(Employee, Employee.department_id == Department.id
        ).filter(Employee.is_active == True
        ).group_by(Department.name).all()
        context["employees"]["departments"] = [{"name": d[0], "count": d[1]} for d in dept_query if d[0]]
        
        # Payroll stats
        pending_payrolls = db.query(func.count(Payroll.id)).filter(
            Payroll.status.in_(["draft", "processed"])
        ).scalar() or 0
        
        # Get payroll paid this month (using pay_period_end as proxy for payment)
        total_payroll_month = db.query(func.sum(Payroll.net_salary)).filter(
            Payroll.status == "paid",
            Payroll.pay_period_end >= month_start,
            Payroll.pay_period_end <= month_end
        ).scalar() or 0
        
        context["payroll"] = {
            "pending_count": pending_payrolls,
            "paid_this_month": float(total_payroll_month)
        }
        
        # Inventory stats
        total_items = db.query(func.count(Item.id)).scalar() or 0
        low_stock = db.query(Item).filter(
            Item.current_stock <= Item.reorder_level
        ).all()
        
        context["inventory"] = {
            "total_items": total_items,
            "low_stock_count": len(low_stock),
            "low_stock_items": [{"name": i.name, "stock": float(i.current_stock), "reorder_level": float(i.reorder_level)} for i in low_stock[:5]]
        }
        
        # Purchase order stats
        po_stats = {}
        for status in ["draft", "approved", "received", "cancelled"]:
            count = db.query(func.count(PurchaseOrder.id)).filter(PurchaseOrder.status == status).scalar() or 0
            po_stats[status] = count
        
        context["purchase_orders"] = po_stats
        
        # Financial stats
        revenue_accounts = db.query(Account).filter(Account.account_type == "revenue").all()
        expense_accounts = db.query(Account).filter(Account.account_type == "expense").all()
        rev_ids = [a.id for a in revenue_accounts]
        exp_ids = [a.id for a in expense_accounts]
        
        current_revenue = 0
        current_expenses = 0
        
        if rev_ids:
            result = db.query(func.sum(JournalEntryLine.credit)).join(JournalEntry).filter(
                JournalEntryLine.account_id.in_(rev_ids),
                JournalEntry.date >= month_start,
                JournalEntry.date <= month_end,
                JournalEntry.status == "posted"
            ).scalar()
            current_revenue = float(result or 0)
        
        if exp_ids:
            result = db.query(func.sum(JournalEntryLine.debit)).join(JournalEntry).filter(
                JournalEntryLine.account_id.in_(exp_ids),
                JournalEntry.date >= month_start,
                JournalEntry.date <= month_end,
                JournalEntry.status == "posted"
            ).scalar()
            current_expenses = float(result or 0)
        
        context["financials"] = {
            "period": today.strftime("%B %Y"),
            "revenue": current_revenue,
            "expenses": current_expenses,
            "profit": current_revenue - current_expenses
        }
        
        # Pending tasks summary
        pending_jes = db.query(func.count(JournalEntry.id)).filter(JournalEntry.status == "draft").scalar() or 0
        context["pending_tasks"] = {
            "draft_journal_entries": pending_jes,
            "pending_payrolls": pending_payrolls,
            "draft_purchase_orders": po_stats.get("draft", 0)
        }
        
    except Exception as e:
        context["error"] = str(e)
    
    return context


def query_specific_data(db: Session, query_type: str, params: Dict = None) -> Any:
    """Query specific data based on type."""
    params = params or {}
    
    try:
        if query_type == "top_expenses":
            # Get top expense categories this month
            today = date.today()
            month_start = date(today.year, today.month, 1)
            
            result = db.query(
                Account.name,
                func.sum(JournalEntryLine.debit).label('total')
            ).join(JournalEntryLine, Account.id == JournalEntryLine.account_id
            ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
            ).filter(
                Account.account_type == "expense",
                JournalEntry.date >= month_start,
                JournalEntry.status == "posted"
            ).group_by(Account.name).order_by(text('total DESC')).limit(5).all()
            
            return [{"category": r[0], "amount": float(r[1] or 0)} for r in result]
        
        elif query_type == "employee_details":
            emp_id = params.get("employee_id")
            if emp_id:
                emp = db.query(Employee).filter(Employee.employee_code == emp_id).first()
                if emp:
                    dept = db.query(Department).filter(Department.id == emp.department_id).first()
                    return {
                        "id": emp.employee_code,
                        "name": f"{emp.first_name} {emp.last_name}",
                        "department": dept.name if dept else "Unknown",
                        "salary": float(emp.salary),
                        "hire_date": emp.date_of_joining.isoformat() if emp.date_of_joining else None
                    }
            return None
        
        elif query_type == "all_employees":
            employees = db.query(Employee, Department.name).join(
                Department, Employee.department_id == Department.id
            ).filter(Employee.is_active == True).all()
            return [{
                "id": e.employee_code,
                "name": f"{e.first_name} {e.last_name}",
                "department": dept_name or "Unknown",
                "salary": float(e.salary)
            } for e, dept_name in employees]
        
        elif query_type == "supplier_list":
            suppliers = db.query(Supplier).filter(Supplier.is_active == True).all()
            return [{"id": s.id, "name": s.name, "contact": s.contact_person} for s in suppliers]
        
        elif query_type == "recent_transactions":
            entries = db.query(JournalEntry).filter(
                JournalEntry.status == "posted"
            ).order_by(JournalEntry.date.desc()).limit(10).all()
            
            return [{
                "date": e.date.isoformat() if e.date else None,
                "description": e.description,
                "amount": float(e.total_debit or 0)
            } for e in entries]
        
        elif query_type == "item_stock":
            item_name = params.get("item_name", "").lower()
            items = db.query(Item).filter(
                func.lower(Item.name).contains(item_name)
            ).all()
            return [{
                "name": i.name,
                "code": i.code,
                "stock": float(i.current_stock),
                "reorder_level": float(i.reorder_level),
                "unit_price": float(i.unit_price)
            } for i in items]
        
    except Exception as e:
        return {"error": str(e)}
    
    return None


# ---------------------------------------------------------------------------
# Helper function for building responses
# ---------------------------------------------------------------------------

def _build_response(user_message: str, response_text: str) -> Dict[str, Any]:
    """Build a standard response dictionary."""
    return {
        "success": True,
        "response": response_text,
        "conversation_history": [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response_text}
        ],
        "model": "rule-based",
        "fallback": True
    }


# ---------------------------------------------------------------------------
# OpenAI Chat Function
# ---------------------------------------------------------------------------

def chat_with_ai(
    db: Session,
    user_message: str,
    conversation_history: List[Dict] = None,
    user_role: str = "admin"
) -> Dict[str, Any]:
    """
    Process a user message and generate an AI response.
    
    Args:
        db: Database session
        user_message: The user's question
        conversation_history: Previous messages for context
        user_role: User's role for access control
    
    Returns:
        Dict with response, conversation history, and metadata
    """
    conversation_history = conversation_history or []
    
    # Check if OpenAI is available
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not OPENAI_AVAILABLE or not api_key:
        # Fallback to rule-based response
        return fallback_response(db, user_message, user_role)
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Get current business context
        business_context = get_business_context(db)
        
        # Build system prompt with schema and context
        system_message = SYSTEM_PROMPT.format(
            schema=DATABASE_SCHEMA,
            current_date=date.today().strftime("%B %d, %Y")
        )
        
        # Add business context
        system_message += f"\n\nCurrent Business State:\n{json.dumps(business_context, indent=2, default=str)}"
        
        # Build messages for API
        messages = [{"role": "system", "content": system_message}]
        
        # Add conversation history (last 10 messages)
        for msg in conversation_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cost-effective model
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )
        
        assistant_message = response.choices[0].message.content
        
        # Update conversation history
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "assistant", "content": assistant_message})
        
        return {
            "success": True,
            "response": assistant_message,
            "conversation_history": conversation_history,
            "model": "gpt-4o-mini",
            "tokens_used": response.usage.total_tokens if response.usage else None
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # Check for specific errors
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return {
                "success": False,
                "response": "API key error. Please check your OPENAI_API_KEY environment variable.",
                "error": error_msg,
                "conversation_history": conversation_history
            }
        
        # Fallback to rule-based for other errors
        fallback = fallback_response(db, user_message, user_role)
        fallback["error"] = error_msg
        fallback["fallback"] = True
        return fallback


# ---------------------------------------------------------------------------
# Fallback Rule-Based Response
# ---------------------------------------------------------------------------

def fallback_response(db: Session, user_message: str, user_role: str) -> Dict[str, Any]:
    """Generate a response without AI using business data."""
    query_lower = user_message.lower().strip()
    context = get_business_context(db)
    
    response_text = ""
    
    # -------------------------------------------------------------------------
    # GREETINGS & CASUAL CONVERSATION (Check these first!)
    # -------------------------------------------------------------------------
    
    # Greetings
    greetings = ["hi", "hello", "hey", "hola", "good morning", "good afternoon", 
                 "good evening", "howdy", "yo", "sup", "what's up", "whats up"]
    if any(query_lower == g or query_lower.startswith(g + " ") or query_lower.startswith(g + "!") for g in greetings):
        fin = context.get("financials", {})
        response_text = f"""👋 Hello! Welcome to FinCore AI!

I'm your business assistant for FreshBite Foods. I'm here to help you with anything related to your business.

📊 **Quick Overview:**
• Revenue: ₹{fin.get('revenue', 0):,.2f}
• Expenses: ₹{fin.get('expenses', 0):,.2f}
• Net Profit: ₹{fin.get('profit', 0):,.2f}

Feel free to ask me anything! For example:
• "How is our business doing?"
• "Show me the employees"
• "What's our inventory status?"
• "Any pending tasks?"

How can I help you today? 😊"""
        return _build_response(user_message, response_text)
    
    # Thanks/Appreciation
    thanks_words = ["thank", "thanks", "thx", "appreciate", "grateful", "cheers"]
    if any(word in query_lower for word in thanks_words):
        response_text = """😊 You're welcome! I'm always happy to help.

Is there anything else you'd like to know about the business? Feel free to ask about:
• Financials (revenue, expenses, profit)
• Employees and payroll
• Inventory and stock
• Purchase orders"""
        return _build_response(user_message, response_text)
    
    # Goodbyes
    goodbye_words = ["bye", "goodbye", "see you", "take care", "cya", "later", "gtg"]
    if any(word in query_lower for word in goodbye_words):
        response_text = """👋 Goodbye! It was great chatting with you.

Feel free to come back anytime you need help with business insights or data. Have a great day! 🌟"""
        return _build_response(user_message, response_text)
    
    # How are you / Personal questions
    personal_questions = ["how are you", "how r u", "how do you do", "how's it going", 
                         "what's your name", "who are you", "what are you", "tell me about yourself"]
    if any(q in query_lower for q in personal_questions):
        response_text = """😊 I'm FinCore AI, your friendly business assistant! I'm doing great, thanks for asking!

I'm here to help you navigate your ERP system and make sense of your business data. I can provide insights on:
• 📊 Financial performance
• 👥 Employee information
• 📦 Inventory status
• 🛒 Purchase orders
• 📋 Pending tasks

What would you like to explore today?"""
        return _build_response(user_message, response_text)
    
    # General "how is" or "how's" questions about business
    if query_lower in ["how is everything", "how's everything", "how are things", "how is it going", 
                       "how's it going", "what's happening", "what is happening", "status"]:
        fin = context.get("financials", {})
        tasks = context.get("pending_tasks", {})
        inv = context.get("inventory", {})
        total_tasks = sum(tasks.values())
        
        health = "🟢 Healthy" if fin.get('profit', 0) > 0 else "🟡 Needs attention"
        response_text = f"""📊 **Business Status Overview**

**Overall Health:** {health}

**Financial Summary ({fin.get('period', 'This Month')}):**
• Revenue: ₹{fin.get('revenue', 0):,.2f}
• Expenses: ₹{fin.get('expenses', 0):,.2f}
• Profit: ₹{fin.get('profit', 0):,.2f}

**Attention Needed:**
• {total_tasks} pending tasks
• {inv.get('low_stock_count', 0)} items need reorder

Would you like more details on any of these areas?"""
        return _build_response(user_message, response_text)
    
    # Yes/No/Okay responses
    if query_lower in ["yes", "yeah", "yep", "sure", "ok", "okay", "alright", "no", "nope", "nah"]:
        if query_lower in ["no", "nope", "nah"]:
            response_text = """Alright! Let me know if you change your mind or need anything else. 

I'm here to help with any business questions you have. 😊"""
        else:
            response_text = """Great! 👍 What would you like to know? 

You can ask me about:
• Financial data (revenue, expenses, profit)
• Employee information
• Inventory and stock levels
• Purchase orders
• Pending tasks

Just ask in natural language!"""
        return _build_response(user_message, response_text)
    
    # Random/unclear messages - be friendly about it
    unclear_patterns = ["hmm", "um", "uh", "huh", "idk", "dunno", "?", "...", "what"]
    if query_lower in unclear_patterns or len(query_lower) < 3:
        response_text = """🤔 I'm not quite sure what you're looking for. 

Here's what I can help with:
• **Financials**: "What's our revenue?" or "Show profit"
• **Team**: "How many employees?" or "Show departments"
• **Stock**: "Inventory status" or "Low stock items"
• **Orders**: "Purchase order status"
• **Tasks**: "What's pending?"

Try asking a specific question, or type **"help"** for more options!"""
        return _build_response(user_message, response_text)
    
    # -------------------------------------------------------------------------
    # BUSINESS QUERIES (Original logic with improvements)
    # -------------------------------------------------------------------------
    
    # Financial queries
    if any(word in query_lower for word in ["revenue", "sales", "income"]):
        fin = context.get("financials", {})
        response_text = f"📊 **Revenue for {fin.get('period', 'this month')}**: ₹{fin.get('revenue', 0):,.2f}"
    
    elif any(word in query_lower for word in ["expense", "cost", "spending"]):
        fin = context.get("financials", {})
        response_text = f"💸 **Expenses for {fin.get('period', 'this month')}**: ₹{fin.get('expenses', 0):,.2f}"
        
        # Add top expenses
        top_exp = query_specific_data(db, "top_expenses")
        if top_exp:
            response_text += "\n\n**Top expense categories:**"
            for i, exp in enumerate(top_exp[:3], 1):
                response_text += f"\n{i}. {exp['category']}: ₹{exp['amount']:,.2f}"
    
    elif any(word in query_lower for word in ["profit", "loss", "margin", "bottom line"]):
        fin = context.get("financials", {})
        profit = fin.get("profit", 0)
        status = "profit" if profit >= 0 else "loss"
        response_text = f"📈 **Net {status} for {fin.get('period', 'this month')}**: ₹{abs(profit):,.2f}"
    
    elif any(word in query_lower for word in ["financial", "summary", "overview", "how are we doing", "how is our business", "business doing", "business status"]):
        fin = context.get("financials", {})
        response_text = f"""📊 **Financial Summary - {fin.get('period', 'This Month')}**

• Revenue: ₹{fin.get('revenue', 0):,.2f}
• Expenses: ₹{fin.get('expenses', 0):,.2f}
• Net Profit: ₹{fin.get('profit', 0):,.2f}

Health Score: {'🟢 Good' if fin.get('profit', 0) > 0 else '🔴 Needs Attention'}"""
    
    # Employee queries
    elif any(word in query_lower for word in ["employee", "staff", "team", "people"]):
        emp = context.get("employees", {})
        response_text = f"👥 **Employee Summary**\n\nTotal Active: {emp.get('total_active', 0)}"
        
        if emp.get("departments"):
            response_text += "\n\n**By Department:**"
            for dept in emp["departments"]:
                response_text += f"\n• {dept['name']}: {dept['count']}"
        
        if "list" in query_lower or "all" in query_lower:
            all_emp = query_specific_data(db, "all_employees")
            if all_emp:
                response_text += "\n\n**Employee List:**"
                for e in all_emp[:10]:
                    response_text += f"\n• {e['name']} ({e['department']}) - ₹{e['salary']:,.0f}/month"
    
    # Payroll queries
    elif any(word in query_lower for word in ["payroll", "salary", "wage", "pay"]):
        pay = context.get("payroll", {})
        response_text = f"""💰 **Payroll Status**

• Pending Payrolls: {pay.get('pending_count', 0)}
• Paid This Month: ₹{pay.get('paid_this_month', 0):,.2f}"""
    
    # Inventory queries
    elif any(word in query_lower for word in ["inventory", "stock", "item", "product"]):
        inv = context.get("inventory", {})
        response_text = f"""📦 **Inventory Summary**

• Total Items: {inv.get('total_items', 0)}
• Low Stock Alerts: {inv.get('low_stock_count', 0)}"""
        
        if inv.get("low_stock_items"):
            response_text += "\n\n**Items Needing Reorder:**"
            for item in inv["low_stock_items"]:
                response_text += f"\n• {item['name']}: {item['stock']:.0f} units (reorder at {item['reorder_level']:.0f})"
    
    # Purchase order queries
    elif any(word in query_lower for word in ["purchase", "order", "po", "supplier", "procurement"]):
        po = context.get("purchase_orders", {})
        response_text = f"""🛒 **Purchase Orders**

• Draft: {po.get('draft', 0)}
• Approved: {po.get('approved', 0)}
• Received: {po.get('received', 0)}
• Cancelled: {po.get('cancelled', 0)}"""
    
    # Pending tasks
    elif any(word in query_lower for word in ["pending", "todo", "task", "outstanding"]):
        tasks = context.get("pending_tasks", {})
        total = sum(tasks.values())
        response_text = f"""📋 **Pending Tasks** ({total} total)

• Draft Journal Entries: {tasks.get('draft_journal_entries', 0)}
• Pending Payrolls: {tasks.get('pending_payrolls', 0)}
• Draft Purchase Orders: {tasks.get('draft_purchase_orders', 0)}"""
    
    # Help / capabilities
    elif any(word in query_lower for word in ["help", "what can you", "capabilities", "how to"]):
        response_text = """🤖 **I can help you with:**

• **Financials**: "What's our revenue?", "Show me expenses", "How's our profit?"
• **Employees**: "How many employees?", "List all staff", "Show departments"
• **Payroll**: "Payroll status", "Pending salaries"
• **Inventory**: "Stock levels", "Low stock items", "Check inventory"
• **Purchases**: "Purchase orders status", "Pending POs"
• **Tasks**: "What's pending?", "Outstanding tasks"

Just ask in natural language and I'll help!"""
    
    # Default response - be more conversational
    else:
        fin = context.get("financials", {})
        tasks = context.get("pending_tasks", {})
        
        # Try to provide a more helpful response
        response_text = f"""🤔 I'm not quite sure what you mean by "{user_message[:50]}{'...' if len(user_message) > 50 else ''}".

But no worries! Here's a quick snapshot of your business:

📊 **{fin.get('period', 'This Month')}:**
• Revenue: ₹{fin.get('revenue', 0):,.2f}
• Expenses: ₹{fin.get('expenses', 0):,.2f}
• Net Profit: ₹{fin.get('profit', 0):,.2f}

📋 **{sum(tasks.values())} pending tasks** need attention

Try asking something like:
• "How is our business doing?"
• "Show me the employees"
• "What's the inventory status?"
• "Any pending tasks?"

Or just say **"help"** to see all my capabilities! 😊"""
    
    return _build_response(user_message, response_text)


# ---------------------------------------------------------------------------
# Quick Stats Function
# ---------------------------------------------------------------------------

def get_quick_stats(db: Session) -> Dict[str, Any]:
    """Get quick business statistics for dashboard."""
    context = get_business_context(db)
    
    fin = context.get("financials", {})
    emp = context.get("employees", {})
    inv = context.get("inventory", {})
    tasks = context.get("pending_tasks", {})
    
    return {
        "revenue": fin.get("revenue", 0),
        "expenses": fin.get("expenses", 0),
        "profit": fin.get("profit", 0),
        "employees": emp.get("total_active", 0),
        "low_stock_items": inv.get("low_stock_count", 0),
        "pending_tasks": sum(tasks.values()),
        "period": fin.get("period", "This Month")
    }
