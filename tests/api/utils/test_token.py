import importlib


def test_generate_and_confirm_email_token(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    from talk2dom.api.utils import token as token_module

    importlib.reload(token_module)

    token = token_module.generate_email_token("user@example.com")
    assert token
    assert token_module.confirm_email_token(token) == "user@example.com"


def test_confirm_email_token_returns_none_on_invalid(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    from talk2dom.api.utils import token as token_module

    importlib.reload(token_module)

    assert token_module.confirm_email_token("bad-token") is None
