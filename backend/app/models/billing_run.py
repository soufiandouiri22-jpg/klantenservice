"""
klantenservice.ai - BillingRun Model

Tracks each overage billing calculation per Stripe invoice.
The stripe_invoice_id UNIQUE constraint acts as the idempotency key,
guaranteeing at most one overage charge per invoice.
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, String, DateTime, Integer, Float, Text,
    Enum as SQLEnum, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class BillingRunStatus(str, Enum):
    calculated = "calculated"
    charged = "charged"
    skipped = "skipped"
    error = "error"


class BillingRun(Base):
    """
    One row per subscription invoice.  Ensures overage is billed exactly once.

    Business rule – overage rounding:
        Total overage minutes are rounded UP to the nearest whole minute
        (math.ceil).  E.g. 0.1 extra min → billed as 1 min × €0.25.
        Constant: OVERAGE_ROUNDING_RULE = "ceil_to_whole_minute"
    """
    __tablename__ = "billing_runs"
    __table_args__ = (
        UniqueConstraint("stripe_invoice_id", name="uq_billing_runs_stripe_invoice"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)

    stripe_invoice_id = Column(String(255), nullable=False)
    stripe_subscription_id = Column(String(255), nullable=True)

    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    minutes_included = Column(Integer, nullable=False, default=0)
    minutes_used = Column(Float, nullable=False, default=0.0)
    overage_minutes = Column(Integer, nullable=False, default=0)
    overage_amount_cents = Column(Integer, nullable=False, default=0)

    stripe_invoice_item_id = Column(String(255), nullable=True)
    stripe_idempotency_key = Column(String(255), nullable=True)

    status = Column(
        SQLEnum(BillingRunStatus),
        nullable=False,
        default=BillingRunStatus.calculated,
    )
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", backref="billing_runs")

    def __repr__(self):
        return (
            f"<BillingRun {self.id} company={self.company_id} "
            f"status={self.status} overage={self.overage_minutes}min>"
        )
