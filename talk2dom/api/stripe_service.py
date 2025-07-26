import os
import stripe
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# Replace with your actual price IDs from Stripe dashboard
PRICE_IDS = {
    "free": None,  # no subscription
    "developer": os.environ.get("STRIPE_TALK2DON_DEV_PRICE"),
    "pro": os.environ.get("STRIPE_TALK2DON_PRO_PRICE"),
    "10": os.environ.get("STRIPE_TALK2DOM_10_PRICE"),
    "20": os.environ.get("STRIPE_TALK2DOM_20_PRICE"),
    "50": os.environ.get("STRIPE_TALK2DOM_50_PRICE"),
}

DOMAIN = os.environ.get("UI_DOMAIN", "http://localhost:8000")


def create_checkout_session(user_email: str, plan: str, mode="subscription"):
    if plan not in PRICE_IDS or PRICE_IDS[plan] is None:
        raise HTTPException(status_code=400, detail="Invalid or free plan")

    if mode == "subscription":
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode=mode,
            line_items=[{"price": PRICE_IDS[plan], "quantity": 1}],
            customer_email=user_email,
            success_url=f"{DOMAIN}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{DOMAIN}/billing/failure",
            metadata={
                "plan": plan,
            },
            subscription_data={"metadata": {"plan": plan}},  # e.g. "pro"
        )
        return session.url
    elif mode == "payment":
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode=mode,
            line_items=[{"price": PRICE_IDS[plan], "quantity": 1}],
            customer_email=user_email,
            success_url=f"{DOMAIN}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{DOMAIN}/billing/failure",
            metadata={
                "plan": plan,
            },
        )
        return session.url
