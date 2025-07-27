from itsdangerous import URLSafeTimedSerializer
import os

SECRET_KEY = os.getenv("SECRET_KEY", None)
SECURITY_SALT = "email-confirmation"

serializer = URLSafeTimedSerializer(SECRET_KEY)

def generate_email_token(email: str) -> str:
    return serializer.dumps(email, salt=SECURITY_SALT)

def confirm_email_token(token: str, expiration=3600):
    try:
        email = serializer.loads(token, salt=SECURITY_SALT, max_age=expiration)
    except Exception:
        return None
    return email