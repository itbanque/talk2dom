import os
import stripe
from fastapi import APIRouter, Request, Header, HTTPException
from loguru import logger
from talk2dom.db.models import User
from talk2dom.db.session import get_db, Session
from datetime import datetime


router = APIRouter()

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


@router.post("/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(...)):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    db: Session = next(get_db())

    # logger.info(f"Received event: {event["type"]}")

    if event["type"] == "payment_intent.succeeded":
        logger.info("Payment intent succeeded.")
        session = event["data"]["object"]
        email = session["metadata"].get("email")
        credit = session["metadata"].get("credit")

        if not email:
            logger.warning("No email provided.")
            return

        logger.info(f"Received payment intent: {credit}")
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.warning(f"No user found for email {email}")
            return
        if credit:
            user.one_time_credits += int(credit)
            db.commit()

    elif event["type"] == "invoice.payment_succeeded":
        logger.info("💰 Invoice payment succeeded.")
        invoice = event["data"]["object"]
        subscription_id = invoice["subscription"]
        subscription_details = invoice["subscription_details"]
        email = subscription_details["metadata"]["email"]
        plan = subscription_details["metadata"]["plan"]
        user_id = subscription_details["metadata"]["user_id"]
        customer_id = invoice["customer"]

        user = db.query(User).filter(User.email == email).first()
        if user:
            subscription = stripe.Subscription.retrieve(subscription_id)
            if plan == "developer":
                credits_remaining = 2000
            elif plan == "pro":
                credits_remaining = 10000
            else:
                credits_remaining = 0
                plan = "free"
            user.plan = plan
            user.stripe_customer_id = customer_id
            user.stripe_subscription_id = subscription_id
            user.subscription_credits = credits_remaining  # Reset credits
            user.subscription_end_date = datetime.utcfromtimestamp(
                subscription["items"]["data"][0]["current_period_end"]
            )
            user.subscription_status = invoice["status"]
            logger.info(f"User {user.email} upgraded to {plan}.")
            db.commit()
        else:
            logger.warning(f"No user found with subscription {subscription_id}")

    elif event["type"] == "customer.subscription.updated":
        logger.info("🔄 Customer subscription updated.")
        invoice = event["data"]["object"]
        subscription = event["data"]["object"]
        subscription_id = invoice["id"]

        user = (
            db.query(User)
            .filter(User.stripe_subscription_id == subscription_id)
            .first()
        )
        if user:
            plan = subscription["metadata"].get("plan", "free")
            subscription = stripe.Subscription.retrieve(subscription_id)
            if plan == "developer":
                credits_remaining = 2000
            elif plan == "pro":
                credits_remaining = 10000
            else:
                credits_remaining = 100  # Free fallback

            user.plan = plan
            user.subscription_credits = credits_remaining
            user.subscription_end_date = datetime.utcfromtimestamp(
                subscription["items"]["data"][0]["current_period_end"]
            )
            user.subscription_status = invoice["status"]
            db.commit()
            logger.info(f"Updated user {user.email} to plan {plan}.")

    elif event["type"] == "customer.subscription.deleted":
        logger.info("⚠️ Subscription canceled.")
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]

        user = (
            db.query(User)
            .filter(User.stripe_subscription_id == subscription_id)
            .first()
        )
        if user:
            user.plan = "free"
            user.stripe_subscription_id = None
            user.subscription_credits = 100  # Free plan credits
            user.subscription_end_date = None
            user.subscription_status = subscription["status"]
            db.commit()
            logger.info(f"User {user.email} downgraded to Free.")

    elif event["type"] == "invoice.payment_failed":
        logger.info("Received an invoice payment failed event")
        # TODO: Notify user / mark subscription inactive
        pass

    return {"status": "success"}
