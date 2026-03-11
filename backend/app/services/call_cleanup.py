"""
klantenservice.ai - Stale Active Call Cleanup

Marks CallLogs stuck in IN_PROGRESS/RINGING for too long as ABANDONED.
Prevents "ghost" active calls from demo/test sessions where the browser was closed.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.call_log import CallLog, CallStatus

logger = logging.getLogger(__name__)

STALE_THRESHOLD_MINUTES = 30


def cleanup_stale_active_calls(
    db: Session,
    max_age_minutes: int = STALE_THRESHOLD_MINUTES,
) -> int:
    """
    Mark CallLogs stuck in RINGING or IN_PROGRESS for longer than max_age_minutes as ABANDONED.
    If max_age_minutes is 0, clean up ALL stuck calls regardless of age.
    Returns the number of calls that were cleaned up.
    """
    query = db.query(CallLog).filter(
        CallLog.status.in_([CallStatus.RINGING, CallStatus.IN_PROGRESS]),
    )
    if max_age_minutes > 0:
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        query = query.filter(CallLog.started_at < cutoff)

    stale = query.all()

    if not stale:
        return 0

    for call in stale:
        call.status = CallStatus.ABANDONED
        call.ended_at = datetime.utcnow()
        if call.started_at:
            call.duration_seconds = int(
                (datetime.utcnow() - call.started_at).total_seconds()
            )

    db.commit()
    logger.info(f"Cleaned up {len(stale)} stale active call(s)")
    return len(stale)
