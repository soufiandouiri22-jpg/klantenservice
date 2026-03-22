"""
klantenservice.ai - Stripe Payments Endpoints
"""
import stripe
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.company import Company, SubscriptionPlan, BillingInterval

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Price IDs mapping (monthly and yearly)
PLAN_PRICES = {
    "starter_monthly": settings.STRIPE_PRICE_STARTER_MONTHLY,
    "starter_yearly": settings.STRIPE_PRICE_STARTER_YEARLY,
    "business_monthly": settings.STRIPE_PRICE_BUSINESS_MONTHLY,
    "business_yearly": settings.STRIPE_PRICE_BUSINESS_YEARLY,
    "enterprise_monthly": settings.STRIPE_PRICE_ENTERPRISE_MONTHLY,
    "enterprise_yearly": settings.STRIPE_PRICE_ENTERPRISE_YEARLY,
}

# Plan limits (AI workers per plan)
PLAN_LIMITS = {
    "starter": 1,
    "business": 5,
    "enterprise": 7,
}

# Belminuten per plan per maand
PLAN_MINUTES = {
    "starter": 500,
    "business": 2000,
    "enterprise": None,  # Onbeperkt
}

# Overage pricing (EUR per extra minute beyond plan limit)
OVERAGE_PRICE_PER_MINUTE = 0.25


class CheckoutRequest(BaseModel):
    plan: str  # starter, business, enterprise
    interval: str = "monthly"  # monthly or yearly
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class PortalRequest(BaseModel):
    return_url: Optional[str] = None


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a Stripe Checkout session for subscription.
    """
    company = current_user.company
    
    if not company:
        raise HTTPException(status_code=400, detail="User has no company")
    
    # Validate plan and interval
    if request.plan not in ["starter", "business", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    if request.interval not in ["monthly", "yearly"]:
        raise HTTPException(status_code=400, detail="Invalid interval")
    
    price_key = f"{request.plan}_{request.interval}"
    price_id = PLAN_PRICES.get(price_key)
    if not price_id:
        raise HTTPException(
            status_code=400, 
            detail=f"Price ID not configured for: {price_key}"
        )
    
    try:
        # Create or get Stripe customer
        if company.stripe_customer_id:
            customer_id = company.stripe_customer_id
        else:
            customer_kwargs: dict = {
                "email": company.email,
                "name": company.name,
                "metadata": {
                    "company_id": str(company.id),
                    "company_slug": company.slug,
                },
            }
            stripe_address = _build_stripe_address(company)
            if stripe_address:
                customer_kwargs["address"] = stripe_address

            customer = stripe.Customer.create(**customer_kwargs)
            company.stripe_customer_id = customer.id
            db.commit()
            customer_id = customer.id
        
        # Sync BTW-nummer to Stripe if available
        if company.btw_number:
            _sync_tax_id_to_stripe(customer_id, company.btw_number)
        
        # Validate redirect URLs to prevent open redirect
        default_success = f"{settings.FRONTEND_URL}/dashboard/settings?payment=success"
        default_cancel = f"{settings.FRONTEND_URL}/dashboard/settings?payment=cancelled"
        success_url = request.success_url if request.success_url and request.success_url.startswith(settings.FRONTEND_URL) else default_success
        cancel_url = request.cancel_url if request.cancel_url and request.cancel_url.startswith(settings.FRONTEND_URL) else default_cancel
        
        # Create checkout session
        # Add 14-day trial for starter and business plans — but only if they haven't used their trial yet
        trial_days = None
        if request.plan in ["starter", "business"] and not company.trial_used:
            trial_days = 14
        
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card", "ideal"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "company_id": str(company.id),
                "plan": request.plan
            },
            subscription_data={
                "trial_period_days": trial_days,
                "metadata": {
                    "company_id": str(company.id),
                    "plan": request.plan
                }
            },
            allow_promotion_codes=True,
            automatic_tax={"enabled": True},
            tax_id_collection={"enabled": True},
            customer_update={"address": "auto", "name": "auto"},
        )
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout: {e}")
        raise HTTPException(status_code=400, detail="Er is een betaalfout opgetreden. Probeer het opnieuw.")


@router.post("/create-portal-session")
async def create_portal_session(
    request: PortalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a Stripe Customer Portal session for managing subscription.
    """
    company = current_user.company
    
    if not company or not company.stripe_customer_id:
        raise HTTPException(
            status_code=400, 
            detail="No active subscription found"
        )
    
    try:
        default_return = f"{settings.FRONTEND_URL}/dashboard/settings"
        return_url = request.return_url if request.return_url and request.return_url.startswith(settings.FRONTEND_URL) else default_return
        
        portal_session = stripe.billing_portal.Session.create(
            customer=company.stripe_customer_id,
            return_url=return_url,
        )
        
        return {"portal_url": portal_session.url}
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(status_code=400, detail="Er is een betaalfout opgetreden. Probeer het opnieuw.")


@router.get("/subscription")
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current subscription status from Stripe.
    """
    company = current_user.company
    
    if not company:
        raise HTTPException(status_code=400, detail="User has no company")
    
    result = {
        "plan": company.subscription_plan.value,
        "status": company.subscription_status,
        "billing_interval": company.billing_interval.value if company.billing_interval else "monthly",
        "max_ai_workers": company.ai_worker_limit,
        "has_stripe": bool(company.stripe_customer_id),
        "stripe_subscription_id": company.stripe_subscription_id,
        "ends_at": company.subscription_ends_at.isoformat() if company.subscription_ends_at else None,
        "trial_used": company.trial_used or False,
    }
    
    # Get more details from Stripe if available
    if company.stripe_subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(company.stripe_subscription_id)
            result["stripe_status"] = subscription.status
            result["current_period_end"] = subscription.current_period_end
            result["cancel_at_period_end"] = subscription.cancel_at_period_end
        except stripe.error.StripeError as e:
            logger.warning(f"Could not fetch Stripe subscription: {e}")
    
    return result


@router.get("/usage")
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get call minutes usage for the current (open) billing period.
    Period start derived from billing_runs chain (see billing_helpers).
    Overage rounded UP to whole minutes (business rule: ceil_to_whole_minute).
    """
    from app.services.billing_helpers import (
        get_current_billing_period_start,
        calculate_minutes_used,
        round_overage_minutes,
    )

    company = current_user.company
    if not company:
        raise HTTPException(status_code=400, detail="User has no company")

    period_start = get_current_billing_period_start(db, company)
    minutes_used = calculate_minutes_used(db, company.id, period_start)
    minutes_used_display = round(minutes_used, 1)

    plan = company.subscription_plan.value
    minutes_limit = PLAN_MINUTES.get(plan)

    overage_minutes = 0
    overage_cost = 0.0
    if minutes_limit and minutes_used > minutes_limit:
        overage_minutes = round_overage_minutes(minutes_used - minutes_limit)
        overage_cost = round(overage_minutes * OVERAGE_PRICE_PER_MINUTE, 2)

    return {
        "minutes_used": minutes_used_display,
        "minutes_limit": minutes_limit,
        "plan": plan,
        "is_unlimited": minutes_limit is None,
        "percentage": round((minutes_used / minutes_limit) * 100, 1) if minutes_limit else 0,
        "period_start": period_start.isoformat(),
        "overage_minutes": overage_minutes,
        "overage_cost": overage_cost,
        "overage_price_per_minute": OVERAGE_PRICE_PER_MINUTE,
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db)
):
    """
    Handle Stripe webhooks for subscription events.
    """
    payload = await request.body()
    
    if not settings.STRIPE_WEBHOOK_SECRET:
        if settings.APP_ENV == "production":
            logger.error("STRIPE_WEBHOOK_SECRET not configured in production — rejecting webhook")
            raise HTTPException(status_code=500, detail="Webhook misconfigured")
        logger.warning("Stripe webhook secret not configured — DEV MODE")
        import json
        event = stripe.Event.construct_from(
            json.loads(payload.decode()),
            stripe.api_key
        )
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    event_type = event["type"]
    data = event["data"]["object"]
    
    logger.info(f"Received Stripe webhook: {event_type}")
    
    if event_type == "checkout.session.completed":
        await handle_checkout_completed(data, db)
    
    elif event_type == "customer.subscription.created":
        await handle_subscription_created(data, db)
    
    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(data, db)
    
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data, db)
    
    elif event_type == "invoice.paid":
        await handle_invoice_paid(data, db)
    
    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(data, db)
    
    elif event_type == "invoice.created":
        await handle_invoice_created(data, db)
    
    elif event_type == "customer.tax_id.created":
        await handle_tax_id_created(data, db)
    
    return {"status": "success"}


async def handle_checkout_completed(session: dict, db: Session):
    """Handle successful checkout."""
    company_id = session.get("metadata", {}).get("company_id")
    plan = session.get("metadata", {}).get("plan")
    subscription_id = session.get("subscription")
    
    if not company_id:
        logger.warning("No company_id in checkout session metadata")
        return
    
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        logger.warning(f"Company not found: {company_id}")
        return
    
    # Update company plan
    if plan and hasattr(SubscriptionPlan, plan):
        company.subscription_plan = SubscriptionPlan[plan]
        company.max_ai_workers = PLAN_LIMITS.get(plan, 1)
    
    if subscription_id:
        company.stripe_subscription_id = subscription_id
        
        # Get subscription status and billing interval from Stripe
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            company.subscription_status = subscription.status  # "trialing" or "active"
            
            # Determine billing interval from Stripe subscription
            if subscription.get("items", {}).get("data"):
                price = subscription["items"]["data"][0].get("price", {})
                stripe_interval = price.get("recurring", {}).get("interval", "month")
                company.billing_interval = (
                    BillingInterval.yearly if stripe_interval == "year"
                    else BillingInterval.monthly
                )
            
            # Mark trial as used when they start trialing
            if subscription.status == "trialing":
                company.trial_used = True
                
            # Use Stripe's start_date as billing period anchor (avoids drift vs utcnow)
            from datetime import datetime
            company.subscription_started_at = datetime.utcfromtimestamp(subscription.start_date)

            logger.info(f"Subscription status from Stripe: {subscription.status}, interval: {company.billing_interval.value}")
        except stripe.error.StripeError as e:
            logger.warning(f"Could not fetch subscription status: {e}")
            company.subscription_status = "active"
            from datetime import datetime
            company.subscription_started_at = datetime.utcnow()
    else:
        company.subscription_status = "active"
        from datetime import datetime
        company.subscription_started_at = datetime.utcnow()

    # Sync address from Stripe customer back to company (entered during checkout)
    try:
        stripe_customer = stripe.Customer.retrieve(session.get("customer"))
        stripe_addr = stripe_customer.get("address") or {}
        if stripe_addr.get("line1") and not company.address:
            company.address = stripe_addr["line1"]
        if stripe_addr.get("city") and not company.city:
            company.city = stripe_addr["city"]
        if stripe_addr.get("postal_code") and not company.postal_code:
            company.postal_code = stripe_addr["postal_code"]
    except stripe.error.StripeError as e:
        logger.warning(f"Could not sync address from Stripe: {e}")
    
    db.commit()
    
    logger.info(f"Checkout completed for company {company.name}, plan: {plan}, interval: {company.billing_interval.value}, status: {company.subscription_status}")


async def handle_subscription_created(subscription: dict, db: Session):
    """Handle new subscription."""
    company_id = subscription.get("metadata", {}).get("company_id")
    plan = subscription.get("metadata", {}).get("plan")
    
    if not company_id:
        # Try to find by customer ID
        customer_id = subscription.get("customer")
        company = db.query(Company).filter(
            Company.stripe_customer_id == customer_id
        ).first()
    else:
        company = db.query(Company).filter(Company.id == company_id).first()
    
    if not company:
        logger.warning("Company not found for subscription")
        return
    
    company.stripe_subscription_id = subscription["id"]
    company.subscription_status = subscription["status"]  # "trialing" or "active"
    
    # Update plan if provided in metadata
    if plan and hasattr(SubscriptionPlan, plan):
        company.subscription_plan = SubscriptionPlan[plan]
        company.max_ai_workers = PLAN_LIMITS.get(plan, 1)
    
    # Store billing interval from Stripe subscription
    if subscription.get("items", {}).get("data"):
        price = subscription["items"]["data"][0].get("price", {})
        stripe_interval = price.get("recurring", {}).get("interval", "month")
        company.billing_interval = (
            BillingInterval.yearly if stripe_interval == "year"
            else BillingInterval.monthly
        )
    
    db.commit()
    
    logger.info(f"Subscription created for company {company.name}, status: {subscription['status']}, interval: {company.billing_interval.value}")


async def handle_subscription_updated(subscription: dict, db: Session):
    """Handle subscription update (plan change, status change, etc.)."""
    subscription_id = subscription["id"]
    
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    
    if not company:
        customer_id = subscription.get("customer")
        if customer_id:
            company = db.query(Company).filter(
                Company.stripe_customer_id == customer_id
            ).first()
            if company:
                company.stripe_subscription_id = subscription_id
    
    if not company:
        logger.warning(f"Company not found for subscription: {subscription_id}")
        return
    
    # Update status
    company.subscription_status = subscription["status"]
    
    # Track cancel_at_period_end (grace period for paying customers)
    # When a paying customer cancels, Stripe sets cancel_at_period_end=True
    # but keeps the subscription active until the period ends.
    # When the period ends, Stripe fires subscription.deleted.
    if subscription.get("cancel_at_period_end") and subscription.get("current_period_end"):
        from datetime import datetime
        company.subscription_ends_at = datetime.utcfromtimestamp(
            subscription["current_period_end"]
        )
        logger.info(
            f"Subscription will cancel at period end for {company.name}, "
            f"ends_at: {company.subscription_ends_at}"
        )
    elif not subscription.get("cancel_at_period_end"):
        # Customer re-activated (un-canceled), clear the end date
        company.subscription_ends_at = None
    
    # Check for plan change
    plan = subscription.get("metadata", {}).get("plan")
    if plan and hasattr(SubscriptionPlan, plan):
        company.subscription_plan = SubscriptionPlan[plan]
        company.max_ai_workers = PLAN_LIMITS.get(plan, 1)
    
    # Update billing interval if changed
    if subscription.get("items", {}).get("data"):
        price = subscription["items"]["data"][0].get("price", {})
        stripe_interval = price.get("recurring", {}).get("interval", "month")
        company.billing_interval = (
            BillingInterval.yearly if stripe_interval == "year"
            else BillingInterval.monthly
        )
    
    db.commit()
    
    logger.info(f"Subscription updated for company {company.name}, status: {subscription['status']}, interval: {company.billing_interval.value}")


async def handle_subscription_deleted(subscription: dict, db: Session):
    """
    Handle subscription deletion (final cancellation).
    
    This fires when:
    - A trial is canceled (immediate)
    - A paid subscription reaches the end of its billing period after cancel_at_period_end
    - You manually delete a subscription from Stripe dashboard
    
    In all cases, the subscription is now truly over — block access.
    """
    subscription_id = subscription["id"]
    
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    
    if not company:
        logger.warning(f"Company not found for subscription: {subscription_id}")
        return
    
    # Set status to canceled — they lose access immediately
    # Keep stripe_subscription_id so future webhooks can still find this company
    company.subscription_status = "canceled"
    company.subscription_ends_at = None
    
    db.commit()
    
    logger.info(f"Subscription deleted/cancelled for company {company.name}")


async def handle_invoice_paid(invoice: dict, db: Session):
    """Handle successful payment."""
    subscription_id = invoice.get("subscription")
    
    if not subscription_id:
        return
    
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    
    if not company:
        customer_id = invoice.get("customer")
        if customer_id:
            company = db.query(Company).filter(
                Company.stripe_customer_id == customer_id
            ).first()
            if company:
                company.stripe_subscription_id = subscription_id
    
    if company:
        if company.subscription_status != "trialing":
            company.subscription_status = "active"
        db.commit()
        logger.info(f"Invoice paid for company {company.name} (status: {company.subscription_status})")


async def handle_payment_failed(invoice: dict, db: Session):
    """Handle failed payment."""
    subscription_id = invoice.get("subscription")
    
    if not subscription_id:
        return
    
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    
    if not company:
        customer_id = invoice.get("customer")
        if customer_id:
            company = db.query(Company).filter(
                Company.stripe_customer_id == customer_id
            ).first()
            if company:
                company.stripe_subscription_id = subscription_id
    
    if company:
        company.subscription_status = "past_due"
        db.commit()
        logger.warning(f"Payment failed for company {company.name}")


async def handle_invoice_created(invoice: dict, db: Session):
    """
    Add overage line item when Stripe creates the next invoice.

    Stripe fires invoice.created ~1 hour before finalizing.
    Only processes renewal invoices (billing_reason == "subscription_cycle").
    Uses the billing_runs table for idempotency (UNIQUE on stripe_invoice_id).

    Period derivation (no date arithmetic):
        period_end   = invoice subscription-line period.start  (new period start = old period end)
        period_start = previous billing_runs.period_end  OR  subscription.start_date (first cycle)
    """
    from datetime import datetime
    from sqlalchemy import desc
    from sqlalchemy.exc import IntegrityError
    from app.models.billing_run import BillingRun, BillingRunStatus
    from app.services.billing_helpers import (
        calculate_minutes_used,
        round_overage_minutes,
    )

    subscription_id = invoice.get("subscription")
    customer_id = invoice.get("customer")
    invoice_id = invoice.get("id")
    billing_reason = invoice.get("billing_reason")

    if not subscription_id or not customer_id:
        return

    if billing_reason != "subscription_cycle":
        logger.info(f"[OVERAGE] Skipping non-renewal invoice {invoice_id} (reason={billing_reason})")
        return

    # --- Idempotency check ---
    existing_run = db.query(BillingRun).filter(
        BillingRun.stripe_invoice_id == invoice_id
    ).first()

    if existing_run and existing_run.status in (
        BillingRunStatus.charged,
        BillingRunStatus.skipped,
    ):
        logger.info(f"[OVERAGE] Already processed invoice {invoice_id} (status={existing_run.status.value})")
        return

    # --- Find company ---
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    if not company:
        company = db.query(Company).filter(
            Company.stripe_customer_id == customer_id
        ).first()
    if not company:
        logger.warning(f"[OVERAGE] Company not found for invoice {invoice_id}")
        return

    plan = company.subscription_plan.value
    limit = PLAN_MINUTES.get(plan)
    if limit is None:
        return

    # --- Derive billing period from Stripe data (no date math) ---
    sub_line = next(
        (ln for ln in invoice.get("lines", {}).get("data", [])
         if ln.get("type") == "subscription"),
        None,
    )
    if sub_line:
        overage_period_end = datetime.utcfromtimestamp(sub_line["period"]["start"])
    else:
        sub = stripe.Subscription.retrieve(subscription_id)
        overage_period_end = datetime.utcfromtimestamp(sub.current_period_start)

    last_run = (
        db.query(BillingRun.period_end)
        .filter(
            BillingRun.company_id == company.id,
            BillingRun.status.in_([BillingRunStatus.charged, BillingRunStatus.skipped]),
        )
        .order_by(desc(BillingRun.period_end))
        .first()
    )
    if last_run:
        overage_period_start = last_run[0]
    elif company.subscription_started_at:
        overage_period_start = company.subscription_started_at
    else:
        sub = stripe.Subscription.retrieve(subscription_id)
        overage_period_start = datetime.utcfromtimestamp(sub.start_date)

    # --- Calculate overage ---
    minutes_used = calculate_minutes_used(
        db, company.id, overage_period_start, overage_period_end,
    )
    raw_overage = minutes_used - limit
    overage_minutes = round_overage_minutes(raw_overage)
    amount_cents = overage_minutes * int(round(OVERAGE_PRICE_PER_MINUTE * 100))

    # --- Create or update billing_run row ---
    billing_run = existing_run  # may be a previous error run
    if not billing_run:
        billing_run = BillingRun(
            company_id=company.id,
            stripe_invoice_id=invoice_id,
            stripe_subscription_id=subscription_id,
            period_start=overage_period_start,
            period_end=overage_period_end,
            minutes_included=limit,
            minutes_used=round(minutes_used, 2),
            overage_minutes=overage_minutes,
            overage_amount_cents=amount_cents,
        )
        db.add(billing_run)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            logger.info(f"[OVERAGE] Duplicate billing_run for invoice {invoice_id} (concurrent webhook), skipping")
            return
    else:
        billing_run.period_start = overage_period_start
        billing_run.period_end = overage_period_end
        billing_run.minutes_included = limit
        billing_run.minutes_used = round(minutes_used, 2)
        billing_run.overage_minutes = overage_minutes
        billing_run.overage_amount_cents = amount_cents
        billing_run.error_message = None

    idempotency_key = f"overage-{billing_run.id}"
    billing_run.stripe_idempotency_key = idempotency_key

    if overage_minutes <= 0:
        billing_run.status = BillingRunStatus.skipped
        db.commit()
        logger.info(
            f"[OVERAGE] No overage for {company.name} "
            f"({minutes_used:.1f}/{limit} min, period {overage_period_start.date()}→{overage_period_end.date()})"
        )
        return

    billing_run.status = BillingRunStatus.calculated
    db.commit()

    # --- Create Stripe InvoiceItem (idempotent via key) ---
    try:
        item = stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice_id,
            amount=amount_cents,
            currency="eur",
            description=f"{overage_minutes} extra belminuten à €{OVERAGE_PRICE_PER_MINUTE:.2f}/min",
            idempotency_key=idempotency_key,
        )
        billing_run.stripe_invoice_item_id = item.id
        billing_run.status = BillingRunStatus.charged
        db.commit()
        logger.info(
            f"[OVERAGE] Charged €{amount_cents/100:.2f} for {company.name} "
            f"({overage_minutes} min over, period {overage_period_start.date()}→{overage_period_end.date()})"
        )
    except stripe.error.InvalidRequestError as e:
        if "invoice" in str(e).lower() and ("finalized" in str(e).lower() or "not open" in str(e).lower()):
            logger.warning(
                f"[OVERAGE] Invoice {invoice_id} already finalized for {company.name}, "
                f"creating standalone InvoiceItem for next invoice"
            )
            try:
                fallback_key = f"overage-fallback-{billing_run.id}"
                item = stripe.InvoiceItem.create(
                    customer=customer_id,
                    amount=amount_cents,
                    currency="eur",
                    description=(
                        f"{overage_minutes} extra belminuten à €{OVERAGE_PRICE_PER_MINUTE:.2f}/min "
                        f"(periode {overage_period_start.date()}→{overage_period_end.date()})"
                    ),
                    idempotency_key=fallback_key,
                )
                billing_run.stripe_invoice_item_id = item.id
                billing_run.status = BillingRunStatus.charged
                billing_run.error_message = "Attached to next invoice (original was finalized)"
                db.commit()
                logger.info(
                    f"[OVERAGE] Standalone InvoiceItem created for {company.name} "
                    f"(€{amount_cents/100:.2f}, will appear on next invoice)"
                )
            except stripe.error.StripeError as fallback_err:
                billing_run.status = BillingRunStatus.error
                billing_run.error_message = f"Finalized + fallback failed: {fallback_err}"
                db.commit()
                logger.error(f"[OVERAGE] Fallback InvoiceItem also failed for {company.name}: {fallback_err}")
        else:
            billing_run.status = BillingRunStatus.error
            billing_run.error_message = str(e)
            db.commit()
            logger.error(f"[OVERAGE] Failed InvoiceItem for {company.name} (invoice={invoice_id}): {e}")
    except stripe.error.StripeError as e:
        billing_run.status = BillingRunStatus.error
        billing_run.error_message = str(e)
        db.commit()
        logger.error(
            f"[OVERAGE] Failed InvoiceItem for {company.name} "
            f"(invoice={invoice_id}): {e}"
        )


def _build_stripe_address(company) -> dict | None:
    """Build a Stripe address dict from company fields. Returns None if no data."""
    if not company.address and not company.city and not company.postal_code:
        return None
    addr: dict = {"country": "NL"}
    if company.address:
        addr["line1"] = company.address
    if company.city:
        addr["city"] = company.city
    if company.postal_code:
        addr["postal_code"] = company.postal_code
    return addr


def _sync_address_to_stripe(customer_id: str, company):
    """Push the company address to Stripe customer."""
    stripe_address = _build_stripe_address(company)
    if not stripe_address:
        return
    try:
        stripe.Customer.modify(customer_id, address=stripe_address)
        logger.info(f"Synced address to Stripe customer {customer_id}")
    except stripe.error.StripeError as e:
        logger.warning(f"Failed to sync address to Stripe: {e}")


def _sync_tax_id_to_stripe(customer_id: str, btw_number: str):
    """Add a tax ID to the Stripe Customer if not already present."""
    try:
        existing = stripe.Customer.list_tax_ids(customer_id, limit=10)
        for tid in existing.get("data", []):
            if tid.get("value") == btw_number:
                return
        stripe.Customer.create_tax_id(customer_id, type="eu_vat", value=btw_number)
        logger.info(f"Synced tax ID {btw_number} to Stripe customer {customer_id}")
    except stripe.error.StripeError as e:
        logger.warning(f"Failed to sync tax ID to Stripe: {e}")


async def handle_tax_id_created(tax_id_data: dict, db: Session):
    """Sync BTW-nummer from Stripe back to the database."""
    customer_id = tax_id_data.get("customer")
    value = tax_id_data.get("value")
    tax_type = tax_id_data.get("type")

    if not customer_id or not value:
        return

    if tax_type != "eu_vat":
        return

    company = db.query(Company).filter(
        Company.stripe_customer_id == customer_id
    ).first()

    if company and company.btw_number != value:
        company.btw_number = value
        db.commit()
        logger.info(f"Synced tax ID {value} from Stripe to company {company.name}")
