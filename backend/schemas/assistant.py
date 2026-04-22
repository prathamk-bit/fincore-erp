"""
Pydantic schemas for the AI Assistant module.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class InsightItem(BaseModel):
    """A single insight/alert/recommendation item."""
    type: str  # warning, insight, recommendation, info
    message: str
    category: Optional[str] = None
    action: Optional[str] = None
    count: Optional[int] = None
    severity: Optional[str] = None


class InsightsResponse(BaseModel):
    """Response containing list of insights."""
    insights: List[InsightItem]
    count: int


class FinancialSummary(BaseModel):
    """Financial summary with period comparison."""
    current_month: Dict[str, Any]
    last_month: Dict[str, Any]
    changes: Dict[str, Optional[float]]
    insights: List[InsightItem]


class QueryRequest(BaseModel):
    """Request schema for natural language queries."""
    query: str


class QueryResponse(BaseModel):
    """Response schema for natural language queries."""
    query: str
    understood: bool
    intent: Optional[List[str]] = None
    results: List[InsightItem]
    summary: Optional[FinancialSummary] = None


class TraceRequest(BaseModel):
    """Request to trace an expense."""
    entry_id: int


class TraceResponse(BaseModel):
    """Response with expense traceability details."""
    entry_id: int
    found: bool
    source: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None
    entry: Optional[Dict[str, Any]] = None
    lines: Optional[List[Dict[str, Any]]] = None
