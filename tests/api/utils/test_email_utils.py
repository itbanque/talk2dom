from types import SimpleNamespace


def test_send_verification_email_missing_env(monkeypatch):
    from talk2dom.api.utils import email as email_utils

    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("SENDGRID_VERIFICATION_TEMPLATE_ID", raising=False)

    called = {"value": False}

    def fake_client(*args, **kwargs):
        called["value"] = True
        return None

    monkeypatch.setattr(email_utils, "SendGridAPIClient", fake_client)

    email_utils.send_verification_email("u@example.com", "http://verify")
    assert called["value"] is False


def test_send_welcome_email_missing_env(monkeypatch):
    from talk2dom.api.utils import email as email_utils

    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("SENDGRID_WELCOME_TEMPLATE_ID", raising=False)

    called = {"value": False}

    def fake_client(*args, **kwargs):
        called["value"] = True
        return None

    monkeypatch.setattr(email_utils, "SendGridAPIClient", fake_client)

    email_utils.send_welcome_email("u@example.com")
    assert called["value"] is False


def test_send_password_reset_email_missing_env(monkeypatch):
    from talk2dom.api.utils import email as email_utils

    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("SENDGRID_RESET_PASSWORD_TEMPLATE_ID", raising=False)

    called = {"value": False}

    def fake_client(*args, **kwargs):
        called["value"] = True
        return None

    monkeypatch.setattr(email_utils, "SendGridAPIClient", fake_client)

    email_utils.send_password_reset_email("u@example.com", "http://reset")
    assert called["value"] is False


def test_send_verification_email_builds_request(monkeypatch):
    from talk2dom.api.utils import email as email_utils

    monkeypatch.setenv("SENDGRID_API_KEY", "key")
    monkeypatch.setenv("SENDGRID_VERIFICATION_TEMPLATE_ID", "tmpl")

    captured = {}

    class DummyPersonalization:
        def __init__(self):
            self.tos = []
            self.dynamic_template_data = None

        def add_to(self, to):
            self.tos.append(to)

    class DummyMail:
        def __init__(self):
            self.from_email = None
            self.template_id = None
            self._personalizations = []

        def add_personalization(self, p):
            self._personalizations.append(p)

        def get(self):
            return {
                "from": self.from_email,
                "template_id": self.template_id,
                "personalizations": self._personalizations,
            }

    class DummyResponse:
        status_code = 202

    class DummySendGridClient:
        def __init__(self, *_args, **_kwargs):
            def _post(request_body):
                captured["request_body"] = request_body
                return DummyResponse()

            self.client = SimpleNamespace(
                mail=SimpleNamespace(send=SimpleNamespace(post=_post))
            )

    monkeypatch.setattr(email_utils, "Mail", DummyMail)
    monkeypatch.setattr(email_utils, "Personalization", DummyPersonalization)
    monkeypatch.setattr(email_utils, "SendGridAPIClient", DummySendGridClient)
    monkeypatch.setattr(email_utils, "From", lambda *args, **kwargs: ("from", args, kwargs))
    monkeypatch.setattr(email_utils, "To", lambda *args, **kwargs: ("to", args, kwargs))

    email_utils.send_verification_email("u@example.com", "http://verify")

    assert captured["request_body"]["template_id"] == "tmpl"
    personalization = captured["request_body"]["personalizations"][0]
    assert personalization.dynamic_template_data["verify_url"] == "http://verify"
