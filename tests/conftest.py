import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


import pytest


@pytest.fixture(autouse=True)
def _stub_sendgrid(monkeypatch):
    try:
        import talk2dom.api.routers.user as user_routes
    except Exception:
        return
    monkeypatch.setattr(user_routes, "send_verification_email", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(user_routes, "send_welcome_email", lambda *_args, **_kwargs: None)
