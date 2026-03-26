"""
Payment routes: Lemon Squeezy and Razorpay checkout + webhooks.
"""
import json
from fastapi import APIRouter, Depends, Request, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas import (
    CheckoutRequest,
    LemonSqueezyCheckoutResponse,
    RazorpayOrderResponse,
    SubscriptionResponse,
)
from src.controllers.auth_controller import _get_current_user_from_header
from src.services.payment_service import (
    create_lemonsqueezy_checkout,
    create_razorpay_order,
    verify_lemonsqueezy_webhook,
    verify_razorpay_webhook,
    handle_lemonsqueezy_webhook,
    handle_razorpay_webhook,
    get_active_subscription,
)
from src.limiter import limiter
from src.config import settings

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("/checkout/lemonsqueezy", response_model=LemonSqueezyCheckoutResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def checkout_lemonsqueezy(
    request: Request,
    body: CheckoutRequest,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Create a Lemon Squeezy checkout and return the redirect URL."""
    try:
        url = create_lemonsqueezy_checkout(user.id, body.plan)
        return LemonSqueezyCheckoutResponse(checkout_url=url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/checkout/razorpay", response_model=RazorpayOrderResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def checkout_razorpay(
    request: Request,
    body: CheckoutRequest,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Create a Razorpay order and return order_id, key_id, amount, currency for frontend."""
    try:
        data = create_razorpay_order(user.id, body.plan)
        return RazorpayOrderResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/webhook/lemonsqueezy")
async def webhook_lemonsqueezy(
    request: Request,
    x_signature: str = Header(None, alias="X-Signature"),
    db: Session = Depends(get_db),
):
    """Handle Lemon Squeezy webhook events. Raw body required for signature verification."""
    body = await request.body()
    if not x_signature or not verify_lemonsqueezy_webhook(body, x_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    data = json.loads(body)
    meta = data.get("meta", {})
    event = meta.get("event_name")
    if event:
        handle_lemonsqueezy_webhook(event, data, db)
    return {"ok": True}


@router.post("/webhook/razorpay")
async def webhook_razorpay(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    db: Session = Depends(get_db),
):
    """Handle Razorpay webhook events. Raw body required for signature verification."""
    body = await request.body()
    if not x_razorpay_signature or not verify_razorpay_webhook(body, x_razorpay_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    data = json.loads(body)
    event = data.get("event")
    if event:
        handle_razorpay_webhook(event, data, db)
    return {"ok": True}


@router.get("/subscription", response_model=SubscriptionResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def get_subscription(
    request: Request,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Return the current user's active subscription if any."""
    sub = get_active_subscription(db, user.id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription")
    return SubscriptionResponse(
        plan_slug=sub.plan_slug,
        provider=sub.provider.value,
        current_period_ends_at=sub.current_period_ends_at,
    )
