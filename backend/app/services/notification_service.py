"""
klantenservice.ai - Notification Service
Helper to create notifications from anywhere in the codebase.
"""
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30


def create_notification(
    db: Session,
    company_id: str,
    type: NotificationType,
    title: str,
    message: str = None,
    url: str = None,
) -> Notification:
    """Create a new in-app notification."""
    try:
        notification = Notification(
            id=uuid.uuid4(),
            company_id=company_id,
            type=type,
            title=title,
            message=message,
            url=url,
        )
        db.add(notification)
        db.commit()
        return notification
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        db.rollback()
        return None


def cleanup_old_notifications(db: Session, company_id: str = None) -> int:
    """Delete notifications older than RETENTION_DAYS. Returns count deleted."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        query = db.query(Notification).filter(Notification.created_at < cutoff)
        if company_id:
            query = query.filter(Notification.company_id == company_id)
        count = query.delete()
        db.commit()
        if count:
            logger.info(f"Cleaned up {count} old notifications")
        return count
    except Exception as e:
        logger.error(f"Failed to cleanup notifications: {e}")
        db.rollback()
        return 0
