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
        html_content=f"""
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 20px; font-family: Arial, sans-serif;">
            <h1 style="color: #1e40af; text-align: center;">Welcome to Talk2Dom!</h1>
            <p>Thank you for signing up. Please click the button below to verify your email address.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{verify_url}" style="background-color: #1e40af; color: #ffffff; padding: 12px 24px; border-radius: 5px; text-decoration: none; display: inline-block;">Verify Email</a>
            </div>
            <p>If the button above doesn't work, copy and paste this link into your browser:</p>
            <p><a href="{verify_url}">{verify_url}</a></p>
            <p style="margin-top: 40px;">— The Talk2Dom Team</p>
        </div>
        """,
    )
    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)
        logger.info(
            f"Email sent to {to_email} with status code: {response.status_code}"
        )
    except Exception as e:
        logger.error(f"Email sent to {to_email} with error message: {e}")


def send_welcome_email(to_email: str):
    if not os.environ.get("SENDGRID_API_KEY"):
        logger.error("SENDGRID_API_KEY not set")
        return
    html_content = """
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 24px; font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #111827;">
            <h1 style="color: #1e40af; text-align: center; margin: 0 0 12px;">Welcome to Talk2Dom!</h1>
            <p style="margin: 0 0 16px; text-align: center;">
                Thanks for joining! Talk2Dom uses AI to find web elements fast and reliably. Explore our AI-powered web element detection service and get started today.
            </p>

            <!-- Primary CTAs -->
            <div style="text-align: center; margin: 24px 0 8px;">
                <a href="https://talk2dom.itbanque.com" style="background-color: #1e40af; color: #ffffff; padding: 12px 20px; border-radius: 6px; text-decoration: none; display: inline-block; margin: 0 6px 10px;">Go to Talk2Dom</a>
                <a href="https://talk2dom.itbanque.com/docs" style="background-color: #0ea5e9; color: #ffffff; padding: 12px 20px; border-radius: 6px; text-decoration: none; display: inline-block; margin: 0 6px 10px;">Read Docs</a>
            </div>

            <!-- Demos Section -->
            <h2 style="font-size: 18px; margin: 24px 0 8px; color: #111827; text-align: center;">Product Demos</h2>
            <p style="margin: 0 0 16px; text-align: center; color: #4b5563;">Watch quick demos to see Talk2Dom in action.</p>

            <p style="margin: 8px 0; font-weight: bold; text-align: center; color: #1e40af;">Playground Overview</p>
            <div style="margin-bottom: 16px; text-align:center;">
              <a href="https://www.youtube.com/watch?v=m-BQ-4vu-14" target="_blank" style="text-decoration:none; display:inline-block;">
                <img src="https://img.youtube.com/vi/m-BQ-4vu-14/maxresdefault.jpg" alt="Playground Overview" width="100%" style="border:0; outline:none; text-decoration:none; max-width:600px; height:auto; display:block; border-radius:8px;">
              </a>
            </div>
            <p style="margin: 8px 0; font-weight: bold; text-align: center; color: #1e40af;">Chrome Extension Walkthrough</p>
            <div style="margin-bottom: 16px; text-align:center;">
              <a href="https://www.youtube.com/watch?v=Rog8AX0A8qU" target="_blank" style="text-decoration:none; display:inline-block;">
                <img src="https://img.youtube.com/vi/Rog8AX0A8qU/maxresdefault.jpg" alt="Chrome Extension Walkthrough" width="100%" style="border:0; outline:none; text-decoration:none; max-width:600px; height:auto; display:block; border-radius:8px;">
              </a>
            </div>

            <p style="margin-top: 28px; text-align: center; color: #6b7280;">— The Talk2Dom Team</p>
        </div>
    """
    message = Mail(
        from_email="noreply@itbanque.com",
        to_emails=to_email,
        subject="Welcome to Talk2Dom!",
        html_content=html_content,
    )
    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)
        logger.info(
            f"Welcome email sent to {to_email} with status code: {response.status_code}"
        )
    except Exception as e:
        logger.error(f"Welcome email to {to_email} failed with error: {e}")
