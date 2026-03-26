"""
Payment service: Lemon Squeezy and Razorpay checkout creation and webhook handling.
"""
import hmac
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

import httpx
import razorpay
from sqlalchemy.orm import Session

from src.config import settings
from src.models import User, Subscription, PaymentProvider, SubscriptionStatus


# ─── Lemon Squeezy ───────────────────────────────────────────────────────────

LEMON_SQUEEZY_API = "https://api.lemonsqueezy.com/v1"


def create_lemonsqueezy_checkout(user_id: int, plan_slug: str) -> str:
    """Create a Lemon Squeezy checkout and return the checkout URL."""
    if not settings.LEMON_SQUEEZY_API_KEY or not settings.LEMON_SQUEEZY_STORE_ID:
        raise ValueError("Lemon Squeezy is not configured")

    variant_id = (
        settings.LEMON_SQUEEZY_VARIANT_PRO
        if plan_slug == "pro"
        else settings.LEMON_SQUEEZY_VARIANT_STUDIO
    )
    if not variant_id:
        raise ValueError(f"No Lemon Squeezy variant configured for plan: {plan_slug}")

    success_url = f"{settings.FRONTEND_URL}/pricing?success=lemonsqueezy"
    cancel_url = f"{settings.FRONTEND_URL}/pricing?cancelled=1"

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "product_options": {
                    "redirect_url": success_url,
                },
                "checkout_data": {
                    "custom": {
                        "user_id": str(user_id),
                        "plan": plan_slug,
                    },
                },
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": settings.LEMON_SQUEEZY_STORE_ID}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }

    with httpx.Client() as client:
        r = client.post(
            f"{LEMON_SQUEEZY_API}/checkouts",
            json=payload,
            headers={
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
                "Authorization": f"Bearer {settings.LEMON_SQUEEZY_API_KEY}",
            },
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()

    attrs = data.get("data", {}).get("attributes", {})
    url = attrs.get("url")
    if not url:
        raise ValueError("Lemon Squeezy did not return a checkout URL")
    return url


def verify_lemonsqueezy_webhook(payload: bytes, signature: str) -> bool:
    """Verify Lemon Squeezy webhook using HMAC-SHA256 on raw body."""
    if not settings.LEMON_SQUEEZY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        settings.LEMON_SQUEEZY_WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _get_user_id_from_lemonsqueezy_order(order_id: str) -> Optional[int]:
    """Fetch order from Lemon Squeezy and return user_id from custom_data."""
    if not settings.LEMON_SQUEEZY_API_KEY:
        return None
    try:
        with httpx.Client() as client:
            r = client.get(
                f"{LEMON_SQUEEZY_API}/orders/{order_id}",
                headers={
                    "Accept": "application/vnd.api+json",
                    "Authorization": f"Bearer {settings.LEMON_SQUEEZY_API_KEY}",
                },
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None

    attrs = data.get("data", {}).get("attributes", {})
    meta = attrs.get("meta", {})
    custom_data = meta.get("custom_data") or attrs.get("custom_data") or {}
    if isinstance(custom_data, dict):
        uid = custom_data.get("user_id")
    else:
        uid = getattr(custom_data, "user_id", None)
    if uid is not None:
        return int(uid) if isinstance(uid, str) else uid
    return None


def handle_lemonsqueezy_webhook(event: str, data: dict, db: Session) -> None:
    """Process Lemon Squeezy webhook event and update Subscription / User.is_premium."""
    payload_data = data.get("data", {}) if isinstance(data, dict) else {}
    attrs = payload_data.get("attributes", {})
    external_id = payload_data.get("id") or attrs.get("id")
    if not external_id:
        return

    if event in ("subscription_created", "subscription_updated", "subscription_resumed", "subscription_payment_success"):
        order_id = attrs.get("first_order_id") or attrs.get("order_id")
        user_id = None
        if order_id:
            user_id = _get_user_id_from_lemonsqueezy_order(str(order_id))
        if not user_id:
            for inc in data.get("included", []) or []:
                if inc.get("type") == "orders" and str(inc.get("id")) == str(order_id):
                    meta = inc.get("attributes", {}).get("meta", {}) or inc.get("meta", {})
                    custom = meta.get("custom_data") or meta.get("custom_data") or {}
                    if isinstance(custom, dict):
                        user_id = custom.get("user_id")
                    break
            if user_id is not None:
                user_id = int(user_id) if isinstance(user_id, str) else user_id

        if user_id:
            status_str = (attrs.get("status") or "active").lower()
            ends_at = attrs.get("ends_at")
            period_ends = None
            if ends_at:
                try:
                    period_ends = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                except Exception:
                    pass

            plan_slug = "pro"
            variant_id = str(attrs.get("variant_id", ""))
            if settings.LEMON_SQUEEZY_VARIANT_STUDIO and variant_id == str(settings.LEMON_SQUEEZY_VARIANT_STUDIO):
                plan_slug = "studio"

            sub = db.query(Subscription).filter(
                Subscription.provider == PaymentProvider.LEMON_SQUEEZY,
                Subscription.external_id == str(external_id),
            ).first()
            if not sub:
                sub = Subscription(
                    user_id=user_id,
                    provider=PaymentProvider.LEMON_SQUEEZY,
                    external_id=str(external_id),
                    plan_slug=plan_slug,
                    status=SubscriptionStatus.ACTIVE if status_str in ("active", "on_trial") else SubscriptionStatus.PAST_DUE if status_str == "past_due" else SubscriptionStatus.ACTIVE,
                    current_period_ends_at=period_ends,
                )
                db.add(sub)
            else:
                sub.plan_slug = plan_slug
                sub.current_period_ends_at = period_ends
                sub.status = SubscriptionStatus.ACTIVE if status_str in ("active", "on_trial") else SubscriptionStatus.PAST_DUE if status_str == "past_due" else sub.status

            db.flush()
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.is_premium = True
            db.commit()

    elif event in ("subscription_cancelled", "subscription_expired"):
        sub = db.query(Subscription).filter(
            Subscription.provider == PaymentProvider.LEMON_SQUEEZY,
            Subscription.external_id == str(external_id),
        ).first()
        if sub:
            sub.status = SubscriptionStatus.CANCELLED if event == "subscription_cancelled" else SubscriptionStatus.EXPIRED
            user_id = sub.user_id
            db.commit()
            still_active = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            ).first()
            user = db.query(User).filter(User.id == user_id).first()
            if user and not still_active:
                user.is_premium = False
                db.commit()


# ─── Razorpay ───────────────────────────────────────────────────────────────

_razorpay_client: Optional[razorpay.Client] = None


def _get_razorpay_client() -> razorpay.Client:
    global _razorpay_client
    if _razorpay_client is None:
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise ValueError("Razorpay is not configured")
        _razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    return _razorpay_client


def create_razorpay_order(user_id: int, plan_slug: str) -> dict:
    """Create a Razorpay order and return order_id, key_id, amount, currency for frontend."""
    client = _get_razorpay_client()
    amount = (
        settings.RAZORPAY_PLAN_PRO_AMOUNT
        if plan_slug == "pro"
        else settings.RAZORPAY_PLAN_STUDIO_AMOUNT
    )
    receipt = f"user_{user_id}_plan_{plan_slug}"
    notes = {"user_id": str(user_id), "plan": plan_slug}
    order = client.order.create(
        data={
            "amount": amount,
            "currency": settings.RAZORPAY_CURRENCY,
            "receipt": receipt,
            "notes": notes,
        }
    )
    return {
        "order_id": order["id"],
        "key_id": settings.RAZORPAY_KEY_ID,
        "amount": order["amount"],
        "currency": order["currency"],
    }


def verify_razorpay_payment(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature after frontend checkout."""
    client = _get_razorpay_client()
    try:
        client.utility.verify_payment_signature(order_id, payment_id, signature)
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def verify_razorpay_webhook(payload: bytes, signature: str) -> bool:
    """Verify Razorpay webhook signature."""
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    try:
        client = _get_razorpay_client()
        client.utility.verify_webhook_signature(
            payload.decode("utf-8") if isinstance(payload, bytes) else payload,
            signature,
            settings.RAZORPAY_WEBHOOK_SECRET,
        )
        return True
    except Exception:
        return False


def handle_razorpay_webhook(event: str, payload: dict, db: Session) -> None:
    """Process Razorpay webhook and update Subscription / User.is_premium."""
    if event == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", payload.get("payload", {}).get("payment", {}))
        if not payment:
            payment = payload.get("payment", {}).get("entity", payload.get("payment", {}))
        order_id = payment.get("order_id")
        payment_id = payment.get("id")
        notes = payment.get("notes", {})
        if not notes:
            try:
                client = _get_razorpay_client()
                order = client.order.fetch(order_id)
                notes = order.get("notes", {})
            except Exception:
                pass
        user_id_str = notes.get("user_id")
        plan_slug = notes.get("plan", "pro")
        if not user_id_str:
            return
        user_id = int(user_id_str)

        external_id = payment_id or order_id
        sub = db.query(Subscription).filter(
            Subscription.provider == PaymentProvider.RAZORPAY,
            Subscription.external_id == str(external_id),
        ).first()
        if not sub:
            sub = Subscription(
                user_id=user_id,
                provider=PaymentProvider.RAZORPAY,
                external_id=str(external_id),
                plan_slug=plan_slug,
                status=SubscriptionStatus.ACTIVE,
                current_period_ends_at=None,
            )
            db.add(sub)
        db.flush()
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_premium = True
        db.commit()

    elif event in ("subscription.cancelled", "subscription.completed", "subscription.expired"):
        sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", payload.get("payload", {}).get("subscription", {}))
        if not sub_entity:
            sub_entity = payload.get("subscription", {}).get("entity", payload.get("subscription", {}))
        external_id = sub_entity.get("id")
        if not external_id:
            return
        sub = db.query(Subscription).filter(
            Subscription.provider == PaymentProvider.RAZORPAY,
            Subscription.external_id == str(external_id),
        ).first()
        if sub:
            sub.status = SubscriptionStatus.CANCELLED if "cancelled" in event else SubscriptionStatus.EXPIRED
            user_id = sub.user_id
            db.commit()
            still_active = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            ).first()
            user = db.query(User).filter(User.id == user_id).first()
            if user and not still_active:
                user.is_premium = False
                db.commit()


def get_active_subscription(db: Session, user_id: int) -> Optional[Subscription]:
    """Return the user's active subscription if any."""
    return (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .first()
    )
