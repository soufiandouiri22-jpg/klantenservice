"""
klantenservice.ai - Notifications Endpoints
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID

from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.notification import Notification
from app.api.deps import get_current_user, get_current_company

router = APIRouter()


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    message: Optional[str] = None
    url: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationsListResponse(BaseModel):
    notifications: List[NotificationResponse]
    unread_count: int


@router.get("/", response_model=NotificationsListResponse)
async def list_notifications(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """
    Get recent notifications for the current company.
    Returns up to `limit` notifications ordered by newest first.
    """
    notifications = db.query(Notification).filter(
        Notification.company_id == company.id,
    ).order_by(desc(Notification.created_at)).limit(limit).all()

    unread_count = db.query(Notification).filter(
        Notification.company_id == company.id,
        Notification.is_read == False,
    ).count()

    return NotificationsListResponse(
        notifications=notifications,
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.company_id == company.id,
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notificatie niet gevonden")

    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    return {"message": "Gelezen"}


@router.post("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current company."""
    db.query(Notification).filter(
        Notification.company_id == company.id,
        Notification.is_read == False,
    ).update({
        Notification.is_read: True,
        Notification.read_at: datetime.utcnow(),
    })
    db.commit()
    return {"message": "Alle notificaties gelezen"}
