from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, SubscriptionStatus
from app.routers.auth import get_current_user_dependency
from app.core.config import settings
from app.services.stripe_service import create_checkout_session
from pydantic import BaseModel
import stripe

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
def create_checkout(
    request: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for subscription."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )
    
    try:
        checkout_url = create_checkout_session(
            user=current_user,
            price_id=request.price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            db=db
        )
        return CheckoutSessionResponse(checkout_url=checkout_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret not configured",
        )
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )
    
    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        
        # Find user by customer ID
        user = db.query(User).filter(
            User.stripe_customer_id == customer_id
        ).first()
        
        if user:
            user.subscription_status = SubscriptionStatus.ACTIVE
            user.stripe_subscription_id = subscription_id
            db.commit()
    
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        subscription_id = subscription.get("id")
        
        # Find user by subscription ID
        user = db.query(User).filter(
            User.stripe_subscription_id == subscription_id
        ).first()
        
        if user:
            user.subscription_status = SubscriptionStatus.CANCELED
            db.commit()
    
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        subscription_id = subscription.get("id")
        status_str = subscription.get("status")
        
        user = db.query(User).filter(
            User.stripe_subscription_id == subscription_id
        ).first()
        
        if user:
            if status_str == "active":
                user.subscription_status = SubscriptionStatus.ACTIVE
            elif status_str in ["canceled", "unpaid", "past_due"]:
                user.subscription_status = SubscriptionStatus.CANCELED
            db.commit()
    
    return {"status": "success"}

