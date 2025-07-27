import smtplib
from email.message import EmailMessage
import os

def send_verification_email(to_email: str, verify_url: str):
    msg = EmailMessage()
    msg["Subject"] = "Verify your email"
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = to_email
    msg.set_content(f"Click the link to verify your email: {verify_url}")

    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], 465) as smtp:
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        smtp.send_message(msg)