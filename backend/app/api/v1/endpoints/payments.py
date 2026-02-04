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
from app.models.company import Company, SubscriptionPlan

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

# Plan limits
PLAN_LIMITS = {
    "starter": 1,
    "business": 5,
    "enterprise": 10,
}


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
            customer = stripe.Customer.create(
                email=company.email,
                name=company.name,
                metadata={
                    "company_id": str(company.id),
                    "company_slug": company.slug
                }
            )
            company.stripe_customer_id = customer.id
            db.commit()
            customer_id = customer.id
        
        # Default URLs
        success_url = request.success_url or f"{settings.FRONTEND_URL}/dashboard/settings?payment=success"
        cancel_url = request.cancel_url or f"{settings.FRONTEND_URL}/dashboard/settings?payment=cancelled"
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card", "ideal"],  # Card and iDEAL for NL
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
                "metadata": {
                    "company_id": str(company.id),
                    "plan": request.plan
                }
            },
            allow_promotion_codes=True,
        )
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


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
        return_url = request.return_url or f"{settings.FRONTEND_URL}/dashboard/settings"
        
        portal_session = stripe.billing_portal.Session.create(
            customer=company.stripe_customer_id,
            return_url=return_url,
        )
        
        return {"portal_url": portal_session.url}
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


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
        "max_ai_workers": company.ai_worker_limit,
        "has_stripe": bool(company.stripe_customer_id),
        "stripe_subscription_id": company.stripe_subscription_id,
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
        logger.warning("Stripe webhook secret not configured")
        # In development, process without verification
        event = stripe.Event.construct_from(
            stripe.util.convert_to_stripe_object(payload.decode()),
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
    
    # Update company
    if plan and hasattr(SubscriptionPlan, plan):
        company.subscription_plan = SubscriptionPlan[plan]
        company.max_ai_workers = PLAN_LIMITS.get(plan, 1)
    
    if subscription_id:
        company.stripe_subscription_id = subscription_id
    
    company.subscription_status = "active"
    db.commit()
    
    logger.info(f"Checkout completed for company {company.name}, plan: {plan}")


async def handle_subscription_created(subscription: dict, db: Session):
    """Handle new subscription."""
    company_id = subscription.get("metadata", {}).get("company_id")
    
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
    company.subscription_status = subscription["status"]
    db.commit()
    
    logger.info(f"Subscription created for company {company.name}")


async def handle_subscription_updated(subscription: dict, db: Session):
    """Handle subscription update (plan change, status change, etc.)."""
    subscription_id = subscription["id"]
    
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    
    if not company:
        logger.warning(f"Company not found for subscription: {subscription_id}")
        return
    
    # Update status
    company.subscription_status = subscription["status"]
    
    # Check for plan change
    plan = subscription.get("metadata", {}).get("plan")
    if plan and hasattr(SubscriptionPlan, plan):
        company.subscription_plan = SubscriptionPlan[plan]
        company.max_ai_workers = PLAN_LIMITS.get(plan, 1)
    
    db.commit()
    
    logger.info(f"Subscription updated for company {company.name}, status: {subscription['status']}")


async def handle_subscription_deleted(subscription: dict, db: Session):
    """Handle subscription cancellation."""
    subscription_id = subscription["id"]
    
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    
    if not company:
        logger.warning(f"Company not found for subscription: {subscription_id}")
        return
    
    # Downgrade to starter
    company.subscription_plan = SubscriptionPlan.starter
    company.max_ai_workers = 1
    company.subscription_status = "cancelled"
    company.stripe_subscription_id = None
    
    db.commit()
    
    logger.info(f"Subscription cancelled for company {company.name}")


async def handle_invoice_paid(invoice: dict, db: Session):
    """Handle successful payment."""
    subscription_id = invoice.get("subscription")
    
    if not subscription_id:
        return
    
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    
    if company:
        company.subscription_status = "active"
        db.commit()
        logger.info(f"Invoice paid for company {company.name}")


async def handle_payment_failed(invoice: dict, db: Session):
    """Handle failed payment."""
    subscription_id = invoice.get("subscription")
    
    if not subscription_id:
        return
    
    company = db.query(Company).filter(
        Company.stripe_subscription_id == subscription_id
    ).first()
    
    if company:
        company.subscription_status = "past_due"
        db.commit()
        logger.warning(f"Payment failed for company {company.name}")
