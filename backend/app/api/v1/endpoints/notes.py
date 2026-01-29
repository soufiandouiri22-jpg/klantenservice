"""
klantenservice.ai - Internal Note Endpoints
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.internal_note import InternalNote, NotePriority
from app.schemas.note import (
    InternalNoteCreate,
    InternalNoteUpdate,
    InternalNoteResponse,
    InternalNoteListResponse,
    NoteResolveRequest,
)
from app.api.deps import get_current_user, get_current_company, require_manager

router = APIRouter()


@router.get("/", response_model=InternalNoteListResponse)
async def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    priority: Optional[NotePriority] = None,
    category: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    action_required: Optional[bool] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List internal notes with filters and pagination.
    """
    query = db.query(InternalNote).filter(InternalNote.company_id == company.id)
    
    if start_date:
        query = query.filter(InternalNote.created_at >= start_date)
    if end_date:
        query = query.filter(InternalNote.created_at <= end_date)
    if priority:
        query = query.filter(InternalNote.priority == priority)
    if category:
        query = query.filter(InternalNote.category == category)
    if is_resolved is not None:
        query = query.filter(InternalNote.is_resolved == is_resolved)
    if action_required is not None:
        query = query.filter(InternalNote.action_required == action_required)
    if search:
        query = query.filter(
            (InternalNote.title.ilike(f"%{search}%")) |
            (InternalNote.content.ilike(f"%{search}%")) |
            (InternalNote.customer_name.ilike(f"%{search}%"))
        )
    
    total = query.count()
    total_pages = (total + page_size - 1) // page_size
    
    notes = query.order_by(InternalNote.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    return InternalNoteListResponse(
        items=notes,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/", response_model=InternalNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    data: InternalNoteCreate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Create a new internal note manually.
    """
    note = InternalNote(
        id=uuid4(),
        company_id=company.id,
        title=data.title,
        content=data.content,
        category=data.category,
        tags=data.tags or [],
        priority=data.priority,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        customer_email=data.customer_email,
        action_required=data.action_required,
        action_description=data.action_description,
        action_due_at=data.action_due_at,
        is_resolved=False,
    )
    
    db.add(note)
    db.commit()
    db.refresh(note)
    
    return note


@router.get("/action-required")
async def get_action_required_notes(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get notes that require action.
    """
    notes = db.query(InternalNote).filter(
        InternalNote.company_id == company.id,
        InternalNote.action_required == True,
        InternalNote.is_resolved == False
    ).order_by(
        InternalNote.priority.desc(),
        InternalNote.created_at.desc()
    ).limit(limit).all()
    
    return notes


@router.get("/categories")
async def list_note_categories(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all unique note categories.
    """
    categories = db.query(InternalNote.category).filter(
        InternalNote.company_id == company.id,
        InternalNote.category.isnot(None)
    ).distinct().all()
    
    return [c[0] for c in categories if c[0]]


@router.get("/{note_id}", response_model=InternalNoteResponse)
async def get_note(
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get a specific internal note.
    """
    note = db.query(InternalNote).filter(
        InternalNote.id == note_id,
        InternalNote.company_id == company.id
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notitie niet gevonden",
        )
    
    return note


@router.patch("/{note_id}", response_model=InternalNoteResponse)
async def update_note(
    note_id: UUID,
    data: InternalNoteUpdate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update an internal note.
    """
    note = db.query(InternalNote).filter(
        InternalNote.id == note_id,
        InternalNote.company_id == company.id
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notitie niet gevonden",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)
    
    db.commit()
    db.refresh(note)
    
    return note


@router.post("/{note_id}/resolve")
async def resolve_note(
    note_id: UUID,
    data: NoteResolveRequest,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Mark a note as resolved.
    """
    note = db.query(InternalNote).filter(
        InternalNote.id == note_id,
        InternalNote.company_id == company.id
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notitie niet gevonden",
        )
    
    note.is_resolved = True
    note.resolved_at = datetime.utcnow()
    note.resolved_by_user_id = current_user.id
    note.resolution_notes = data.resolution_notes
    
    db.commit()
    
    return {"message": "Notitie gemarkeerd als opgelost"}


@router.post("/{note_id}/reopen")
async def reopen_note(
    note_id: UUID,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Reopen a resolved note.
    """
    note = db.query(InternalNote).filter(
        InternalNote.id == note_id,
        InternalNote.company_id == company.id
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notitie niet gevonden",
        )
    
    note.is_resolved = False
    note.resolved_at = None
    note.resolved_by_user_id = None
    
    db.commit()
    
    return {"message": "Notitie heropend"}


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Delete an internal note.
    """
    note = db.query(InternalNote).filter(
        InternalNote.id == note_id,
        InternalNote.company_id == company.id
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notitie niet gevonden",
        )
    
    db.delete(note)
    db.commit()
