import os
import stripe
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# Replace with your actual price IDs from Stripe dashboard
PRICE_IDS = {
    "free": None,  # no subscription
    "developer": os.environ.get("TALK2DON_DEV_PRICE"),
    "pro": os.environ.get("TALK2DON_PRO_PRICE"),
}

DOMAIN = os.environ.get("TALK2DON_DOMAIN", "http://localhost:8000")


def create_checkout_session(user_email: str, plan: str):
    if plan not in PRICE_IDS or PRICE_IDS[plan] is None:
        raise HTTPException(status_code=400, detail="Invalid or free plan")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{"price": PRICE_IDS[plan], "quantity": 1}],
        customer_email=user_email,
        success_url=f"{DOMAIN}/api/v1/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{DOMAIN}/api/v1/subscription/cancel",
        metadata={
            "plan": plan,
        },
        subscription_data={"metadata": {"plan": plan}},  # e.g. "pro"
    )
    return session.url
