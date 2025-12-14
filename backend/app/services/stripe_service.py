import stripe
from app.models import User
from app.core.config import settings
from sqlalchemy.orm import Session

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(
    user: User,
    price_id: str,
    success_url: str,
    cancel_url: str,
    db: Session
) -> str:
    """Create a Stripe Checkout session for a user."""
    # Get or create Stripe customer
    customer_id = user.stripe_customer_id
    
    if not customer_id:
        # Create new Stripe customer
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": str(user.id)}
        )
        customer_id = customer.id
        
        # Update user record
        user.stripe_customer_id = customer_id
        db.commit()
        db.refresh(user)
    
    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": 1,
        }],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": str(user.id)},
    )
    
    return session.url

