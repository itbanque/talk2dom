import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To, Personalization
from datetime import datetime
from loguru import logger


def send_verification_email(to_email: str, verify_url: str):
    if not os.environ.get("SENDGRID_API_KEY"):
        logger.error("SENDGRID_API_KEY not set")
        return
    if not os.environ.get("SENDGRID_VERIFICATION_TEMPLATE_ID"):
        logger.error("SENDGRID_VERIFICATION_TEMPLATE_ID not set")
        return
    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    mail = Mail()
    mail.from_email = From("noreply@itbanque.com", "Talk2Dom")
    mail.template_id = os.environ.get("SENDGRID_VERIFICATION_TEMPLATE_ID")
    name = to_email.split("@")[0]
    year = datetime.now().year

    p = Personalization()
    p.add_to(To(to_email, name))
    p.dynamic_template_data = {
        "name": name,
        "verify_url": verify_url,
        "preheader": "Confirm your email to start using Talk2Dom.",
        "year": year,
        "expires_in_minutes": "60",
    }
    mail.add_personalization(p)
    resp = sg.client.mail.send.post(request_body=mail.get())
    logger.info(f"verification email sent to {to_email}: {resp.status_code}")


def send_welcome_email(to_email: str):
    if not os.environ.get("SENDGRID_API_KEY"):
        logger.error("SENDGRID_API_KEY not set")
        return
    if not os.environ.get("SENDGRID_WELCOME_TEMPLATE_ID"):
        logger.error("SENDGRID_WELCOME_TEMPLATE_ID not set")
        return
    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    mail = Mail()
    mail.subject = "Talk2Dom: Welcome to Talk2Dom."
    mail.from_email = From("noreply@itbanque.com", "Talk2Dom")
    mail.template_id = os.environ.get("SENDGRID_WELCOME_TEMPLATE_ID")
    name = to_email.split("@")[0]
    year = datetime.now().year

    p = Personalization()
    p.add_to(To(to_email, name))
    p.dynamic_template_data = {
        "name": name,
        "dashboard_url": "https://talk2dom.itbanque.com/projects",
        "docs_url": "https://talk2dom.itbanque.com/docs",
        "preheader": "Welcome to Talk2Dom! Explore AI-powered web element detection today.",
        "year": year,
    }
    mail.add_personalization(p)
    resp = sg.client.mail.send.post(request_body=mail.get())
    logger.info(f"welcome email sent to {to_email}: {resp.status_code}")


def send_password_reset_email(to_email, reset_url):
    if not os.environ.get("SENDGRID_API_KEY"):
        logger.error("SENDGRID_API_KEY not set")
        return
    if not os.environ.get("SENDGRID_RESET_PASSWORD_TEMPLATE_ID"):
        logger.error("SENDGRID_RESET_PASSWORD_TEMPLATE_ID not set")
        return
    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    mail = Mail()
    mail.from_email = From("noreply@itbanque.com", "Talk2Dom")
    mail.template_id = os.environ.get("SENDGRID_RESET_PASSWORD_TEMPLATE_ID")
    name = to_email.split("@")[0]
    year = datetime.now().year

    p = Personalization()
    p.add_to(To(to_email, name))
    p.dynamic_template_data = {
        "name": name,
        "reset_url": reset_url,
        "preheader": "Reset your Talk2Dom password.",
        "year": year,
    }
    mail.add_personalization(p)
    resp = sg.client.mail.send.post(request_body=mail.get())
    logger.info(f"Reset password email sent to {to_email}: {resp.status_code}")
