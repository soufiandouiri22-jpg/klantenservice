"""
klantenservice.ai - Notification Service
Helper to create notifications from anywhere in the codebase.
"""
import uuid
import logging
from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)


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
