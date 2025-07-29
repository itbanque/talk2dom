import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from loguru import logger


def send_verification_email(to_email: str, verify_url: str):
    if not os.environ.get("SENDGRID_API_KEY"):
        logger.error("SENDGRID_API_KEY not set")
        return
    message = Mail(
        from_email="noreply@itbanque.com",
        to_emails=to_email,
        subject="Welcome to Talk2Dom!",
        html_content=f"Click the link to verify your email: {verify_url}",
    )
    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)
        logger.info(
            f"Email sent to {to_email} with status code: {response.status_code}"
        )
    except Exception as e:
        logger.error(f"Email sent to {to_email} with error message: {e}")
