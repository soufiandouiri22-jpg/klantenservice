"""
klantenservice.ai - Billing Period Helpers

Single source of truth for billing period boundaries.

Period derivation rule:
    period_start = most recent billing_runs.period_end (status in charged/skipped)
                   OR company.subscription_started_at for the first cycle
    period_end   = derived from Stripe invoice line-item period (only in handle_invoice_created)

For real-time queries (get_usage, _check_usage_alerts) we only need period_start
since the current period hasn't ended yet.

Overage rounding rule:
    OVERAGE_ROUNDING_RULE = "ceil_to_whole_minute"
    Total overage is rounded UP to the nearest whole minute via math.ceil().
    Displayed on invoices as "X extra belminuten à €0,25/min".
"""
import math
import logging
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.models.billing_run import BillingRun, BillingRunStatus
from app.models.call_log import CallLog, CallStatus

logger = logging.getLogger(__name__)

OVERAGE_ROUNDING_RULE = "ceil_to_whole_minute"


def get_current_billing_period_start(db: Session, company) -> datetime:
    """
    Return the start of the current (open) billing period for a company.

    Derivation:
      1. Last billing_runs.period_end where status in (charged, skipped).
      2. Fallback: company.subscription_started_at.
      3. Fallback: 1st of current month (safety net for legacy data).
    """
    last_run = (
        db.query(BillingRun.period_end)
        .filter(
            BillingRun.company_id == company.id,
            BillingRun.status.in_([
                BillingRunStatus.charged,
                BillingRunStatus.skipped,
            ]),
        )
        .order_by(desc(BillingRun.period_end))
        .first()
    )

    if last_run:
        return last_run[0]

    if company.subscription_started_at:
        return company.subscription_started_at

    now = datetime.utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def calculate_minutes_used(
    db: Session,
    company_id,
    period_start: datetime,
    period_end: datetime | None = None,
) -> float:
    """
    Sum completed-call minutes in [period_start, period_end).
    If period_end is None, counts up to now (open period).
    """
    filters = [
        CallLog.company_id == company_id,
        CallLog.started_at >= period_start,
        CallLog.status == CallStatus.COMPLETED,
        CallLog.duration_seconds > 0,
    ]
    if period_end is not None:
        filters.append(CallLog.started_at < period_end)

    total_seconds = db.query(
        sqlfunc.coalesce(sqlfunc.sum(CallLog.duration_seconds), 0)
    ).filter(*filters).scalar()

    return total_seconds / 60


def round_overage_minutes(raw_overage: float) -> int:
    """
    Apply the business rounding rule: ceil to whole minute.

    >>> round_overage_minutes(0.0)
    0
    >>> round_overage_minutes(0.1)
    1
    >>> round_overage_minutes(1.0)
    1
    >>> round_overage_minutes(1.01)
    2
    """
    if raw_overage <= 0:
        return 0
    return math.ceil(raw_overage)
