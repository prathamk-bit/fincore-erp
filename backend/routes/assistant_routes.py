"""
API routes for the AI Assistant module.

Endpoints:
    GET  /api/assistant/insights     - Get all insights for current user
    GET  /api/assistant/summary      - Get financial summary
    POST /api/assistant/query        - Process natural language query
    POST /api/assistant/trace        - Trace expense to source
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user
from backend.models.database import get_db
from backend.models.user import User
from backend.schemas.assistant import (
    InsightsResponse,
    InsightItem,
    QueryRequest,
    QueryResponse,
    TraceRequest,
    TraceResponse,
    FinancialSummary,
)
from backend.services.assistant_service import (
    generate_insights,
    get_financial_summary,
    process_query,
    trace_expense,
)

router = APIRouter(prefix="/api/assistant", tags=["AI Assistant"])


@router.get("/insights", response_model=InsightsResponse)
def get_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all insights, warnings, and recommendations for the current user.
    
    Results are filtered based on user role:
    - Admin: All insights
    - Accountant: Financial and journal insights
    - HR Manager: Payroll and employee insights
    - Inventory Manager: Inventory and procurement insights
    """
    insights = generate_insights(db, current_user.role)
    return InsightsResponse(
        insights=[InsightItem(**i) for i in insights],
        count=len(insights),
    )


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get financial summary with month-over-month comparison.
    
    Returns revenue, expenses, profit, and percentage changes.
    """
    summary = get_financial_summary(db)
    return summary


@router.post("/query", response_model=QueryResponse)
def query_assistant(
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process a natural language query.
    
    Supports queries about:
    - Pending tasks ("what is pending?")
    - Financial summary ("how are we doing?")
    - Anomalies ("any issues?")
    - Recommendations ("any suggestions?")
    - Specific areas (payroll, inventory, expenses, revenue)
    """
    result = process_query(db, request.query, current_user.role)
    return QueryResponse(
        query=result["query"],
        understood=result["understood"],
        intent=result.get("intent"),
        results=[InsightItem(**r) for r in result["results"]],
        summary=result.get("summary"),
    )


@router.post("/trace", response_model=TraceResponse)
def trace_entry(
    request: TraceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trace a journal entry back to its source module.
    
    Helps understand where an expense came from (Payroll, Purchase Order, etc.)
    """
    result = trace_expense(db, request.entry_id)
    return TraceResponse(**result)


# ---------------------------------------------------------------------------
# AI Chatbot Endpoints
# ---------------------------------------------------------------------------

from backend.services.chatbot_service import chat_with_ai, get_quick_stats
from pydantic import BaseModel
from typing import List, Optional


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    success: bool
    response: str
    conversation_history: List[ChatMessage]
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    fallback: Optional[bool] = False
    error: Optional[str] = None


class QuickStatsResponse(BaseModel):
    revenue: float
    expenses: float
    profit: float
    employees: int
    low_stock_items: int
    pending_tasks: int
    period: str


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat with the AI assistant.
    
    Send any business-related question and get an intelligent response.
    Supports conversation history for context-aware responses.
    """
    # Convert pydantic models to dicts
    history = None
    if request.conversation_history:
        history = [{"role": m.role, "content": m.content} for m in request.conversation_history]
    
    result = chat_with_ai(
        db=db,
        user_message=request.message,
        conversation_history=history,
        user_role=current_user.role
    )
    
    # Convert history back to ChatMessage objects
    conv_history = [
        ChatMessage(role=m["role"], content=m["content"]) 
        for m in result.get("conversation_history", [])
    ]
    
    return ChatResponse(
        success=result.get("success", False),
        response=result.get("response", "Sorry, I couldn't process your request."),
        conversation_history=conv_history,
        model=result.get("model"),
        tokens_used=result.get("tokens_used"),
        fallback=result.get("fallback", False),
        error=result.get("error")
    )


@router.get("/stats", response_model=QuickStatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get quick business statistics.
    """
    stats = get_quick_stats(db)
    return QuickStatsResponse(**stats)

