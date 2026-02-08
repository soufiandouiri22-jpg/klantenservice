"""
klantenservice.ai - Global Search Endpoint
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, cast, String
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID

from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.ai_worker import AIWorker
from app.models.call_log import CallLog, CallTranscript
from app.models.appointment import Appointment
from app.models.internal_note import InternalNote
from app.models.website_knowledge import WebsiteKnowledge
from app.models.training import ExampleAnswer
from app.api.deps import get_current_user, get_current_company

router = APIRouter()


class SearchResultItem(BaseModel):
    id: str
    type: str  # "call", "ai_worker", "appointment", "note", "website", "training"
    title: str
    subtitle: Optional[str] = None
    url: str  # frontend route to navigate to

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    total: int


@router.get("/", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """
    Global search across all company data:
    - AI workers (name, role)
    - Calls (caller number, summary)
    - Appointments (customer name, title)
    - Notes (title, content, customer name)
    - Website knowledge (URL)
    - Training Q&A (question, answer)
    """
    results: List[SearchResultItem] = []
    search_term = f"%{q.lower()}%"

    # 1. AI Workers - search by name and role
    ai_workers = db.query(AIWorker).filter(
        AIWorker.company_id == company.id,
        or_(
            func.lower(AIWorker.name).like(search_term),
            func.lower(AIWorker.role_title).like(search_term),
        )
    ).limit(3).all()
    for w in ai_workers:
        results.append(SearchResultItem(
            id=str(w.id),
            type="ai_worker",
            title=w.name,
            subtitle=w.role_title,
            url="/dashboard/ai-workers",
        ))

    # 2. Calls - search by caller number or summary
    calls = db.query(CallLog).filter(
        CallLog.company_id == company.id,
        or_(
            CallLog.caller_number.like(search_term),
            func.lower(CallLog.summary).like(search_term),
        )
    ).order_by(CallLog.started_at.desc()).limit(3).all()
    for c in calls:
        started = c.started_at.strftime("%d-%m-%Y %H:%M") if c.started_at else ""
        results.append(SearchResultItem(
            id=str(c.id),
            type="call",
            title=f"Gesprek {c.caller_number}",
            subtitle=c.summary[:80] + "..." if c.summary and len(c.summary) > 80 else c.summary or started,
            url="/dashboard/calls",
        ))

    # 3. Appointments - search by customer name, title, phone
    appointments = db.query(Appointment).filter(
        Appointment.company_id == company.id,
        or_(
            func.lower(Appointment.customer_name).like(search_term),
            func.lower(Appointment.title).like(search_term),
            Appointment.customer_phone.like(search_term),
        )
    ).order_by(Appointment.starts_at.desc()).limit(3).all()
    for a in appointments:
        date_str = a.starts_at.strftime("%d-%m-%Y %H:%M") if a.starts_at else ""
        results.append(SearchResultItem(
            id=str(a.id),
            type="appointment",
            title=a.title,
            subtitle=f"{a.customer_name} · {date_str}",
            url="/dashboard/appointments",
        ))

    # 4. Notes - search by title, content, customer name
    notes = db.query(InternalNote).filter(
        InternalNote.company_id == company.id,
        or_(
            func.lower(InternalNote.title).like(search_term),
            func.lower(InternalNote.content).like(search_term),
            func.lower(InternalNote.customer_name).like(search_term),
        )
    ).order_by(InternalNote.created_at.desc()).limit(3).all()
    for n in notes:
        results.append(SearchResultItem(
            id=str(n.id),
            type="note",
            title=n.title,
            subtitle=n.customer_name or (n.content[:80] + "..." if len(n.content) > 80 else n.content),
            url="/dashboard/notes",
        ))

    # 5. Website Knowledge - search by URL
    websites = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.company_id == company.id,
        func.lower(WebsiteKnowledge.base_url).like(search_term),
    ).limit(3).all()
    for w in websites:
        results.append(SearchResultItem(
            id=str(w.id),
            type="website",
            title=w.base_url,
            subtitle=f"{w.total_pages or 0} pagina's geïndexeerd",
            url="/dashboard/knowledge",
        ))

    # 6. Training Q&A - search by question or answer
    training = db.query(ExampleAnswer).filter(
        ExampleAnswer.company_id == company.id,
        or_(
            func.lower(ExampleAnswer.question).like(search_term),
            func.lower(ExampleAnswer.answer).like(search_term),
        )
    ).limit(3).all()
    for t in training:
        results.append(SearchResultItem(
            id=str(t.id),
            type="training",
            title=t.question,
            subtitle=t.answer[:80] + "..." if len(t.answer) > 80 else t.answer,
            url="/dashboard/training",
        ))

    return SearchResponse(
        results=results[:limit],
        total=len(results),
    )
