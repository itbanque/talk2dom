import stripe
from fastapi import APIRouter, Depends
from talk2dom.api.stripe_service import create_checkout_session
from talk2dom.db.models import User
from talk2dom.api.deps import get_current_user
from talk2dom.db.session import get_db, Session
from fastapi.responses import HTMLResponse


router = APIRouter()


@router.post("/create-subscription")
def start_subscription(plan: str, user: User = Depends(get_current_user)):
    if plan == "free":
        return {"message": "Free plan does not require subscription"}
    url = create_checkout_session(user.email, plan)
    return {"checkout_url": url}


@router.get("/success", response_class=HTMLResponse)
def subscription_success(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = stripe.checkout.Session.retrieve(session_id)
    customer_email = session.get("customer_email")
    subscription_id = session.get("subscription")

    # Optional: update user in DB with new subscription info
    return """
        <html>
            <head><title>Subscription Successful</title></head>
            <body>
                <h1>✅ Thank you!</h1>
                <p>Your subscription was successful.</p>
                <a href="/">Go back to homepage</a>
            </body>
        </html>
        """


@router.get("/cancel", response_class=HTMLResponse)
def subscription_cancel(user: User = Depends(get_current_user)):
    return """
        <html>
            <head><title>Subscription Canceled</title></head>
            <body>
                <h1>❌ Subscription canceled</h1>
                <p>You can restart the process anytime.</p>
                <a href="/">Return to homepage</a>
            </body>
        </html>
    """
