from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from talk2dom.db.models import User
from talk2dom.api.deps import get_current_user
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter()


class PaymentIntentRequest(BaseModel):
    # amount: int  # in cents
    number_of_credit: int
    currency: str = "usd"


PLAN_PRICE_MAPPING = {
    "developer": os.environ.get("STRIPE_TALK2DON_DEV_PRICE"),
    "pro": os.environ.get("STRIPE_TALK2DON_PRO_PRICE"),
}

CREDIT_PRICE_MAPPING = {
    "1000": os.environ.get("STRIPE_TALK2DOM_1000_PRICE"),
    "2200": os.environ.get("STRIPE_TALK2DOM_2200_PRICE"),
    "5500": os.environ.get("STRIPE_TALK2DOM_5500_PRICE"),
}


@router.post("/create-payment-intent")
async def create_payment_intent(
    data: PaymentIntentRequest, user: User = Depends(get_current_user)
):
    amount = CREDIT_PRICE_MAPPING[str(data.number_of_credit)]
    if not amount:
        raise HTTPException(
            status_code=400,
            detail="No credit amount provided",
        )
    intent = stripe.PaymentIntent.create(
        amount=amount,
        currency=data.currency,
        metadata={
            "user_id": str(user.id),
            "email": user.email,
            "credit": data.number_of_credit,
        },
    )
    return {"clientSecret": intent.client_secret}


@router.post("/create-subscription")
async def create_subscription(plan: str, user: "User" = Depends(get_current_user)):
    if not plan:
        raise HTTPException(status_code=400, detail="Missing plan")

    price_id = PLAN_PRICE_MAPPING.get(plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid plan")

    customer_list = stripe.Customer.list(email=user.email, limit=1).data
    if customer_list:
        customer = customer_list[0]
    else:
        customer = stripe.Customer.create(email=user.email)

    subscription = stripe.Subscription.create(
        customer=customer.id,
        items=[{"price": price_id, "quantity": 1}],
        payment_behavior="default_incomplete",
        # default_payment_method=payment_intent.payment_method,
        expand=["latest_invoice.payments"],
        metadata={"user_id": user.id, "email": user.email, "plan": plan},
    )
    payment = subscription["latest_invoice"]["payments"]["data"][0]
    payment_intent_id = payment["payment"]["payment_intent"]
    intent = stripe.PaymentIntent.retrieve(payment_intent_id)

    client_secret = intent["client_secret"]

    return {
        "clientSecret": client_secret,
        "subscriptionId": subscription.id,
        "customerId": customer.id,
    }


@router.post("/update-subscription")
async def update_subscription(plan: str, user: User = Depends(get_current_user)):
    price_id = PLAN_PRICE_MAPPING.get(plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid plan")

    subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)

    item_id = subscription["items"]["data"][0]["id"]

    updated_item = stripe.SubscriptionItem.modify(
        item_id,
        price=price_id,
        quantity=1,
        proration_behavior="create_prorations",
    )

    # Update subscription-level metadata, since SubscriptionItem.modify does not support metadata
    stripe.Subscription.modify(subscription["id"], metadata={"plan": plan})

    return {
        "message": "Subscription updated",
        "subscriptionId": subscription["id"],
        "newItemId": updated_item["id"],
        "newPriceId": price_id,
    }
