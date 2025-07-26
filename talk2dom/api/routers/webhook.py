import os
import stripe
from fastapi import APIRouter, Request, Header, HTTPException
from loguru import logger
from talk2dom.db.models import User
from talk2dom.db.session import get_db, Session
from decimal import Decimal, InvalidOperation
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    db: Session = next(get_db())

    # logger.debug(event)

    if event["type"] == "checkout.session.completed":
        logger.info("✅ Checkout session completed.")
        session = event["data"]["object"]
        customer_id = session["customer"]
        subscription_id = session["subscription"]
        email = session.get("customer_email")
        plan = session["metadata"]["plan"]

        if not email:
            logger.error("Missing customer_email in session")
            raise HTTPException(status_code=400, detail="Missing email")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.warning(f"No user found for email {email}")
        else:
            if subscription_id:
                user.stripe_customer_id = customer_id
                user.stripe_subscription_id = subscription_id
                db.commit()
            else:
                if plan == "10":
                    user.one_time_credits += 1000
                elif plan == "20":
                    user.one_time_credits += 2100
                elif plan == "50":
                    user.one_time_credits += 5500
                db.commit()
            logger.info(f"User {user.email} upgraded to {plan}.")

    elif event["type"] == "invoice.payment_succeeded":
        logger.info("💰 Invoice payment succeeded.")
        invoice = event["data"]["object"]
        subscription_id = invoice["subscription"]

        user = (
            db.query(User)
            .filter(User.stripe_subscription_id == subscription_id)
            .first()
        )
        if user:
            subscription = stripe.Subscription.retrieve(subscription_id)
            logger.info(f"Invoice payment succeeded for subscription {subscription}.")
            plan = subscription["metadata"].get("plan")
            if plan == "developer":
                credits_remaining = 2000
            elif plan == "pro":
                credits_remaining = 10000
            else:
                credits_remaining = 0
                plan = "free"
            user.plan = plan
            user.subscription_credits = credits_remaining  # Reset credits
            user.subscription_end_date = datetime.utcfromtimestamp(
                subscription["items"]["data"][0]["current_period_end"]
            )
            user.subscription_status = invoice["status"]
            logger.info(f"Credits reset for user {user.email} to {credits_remaining}.")
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
