from talk2dom.api.utils import sentry as sentry_utils


def test_init_sentry_no_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    called = {"value": False}

    def fake_init(**kwargs):
        called["value"] = True

    monkeypatch.setattr("sentry_sdk.init", fake_init)
    sentry_utils.init_sentry()
    assert called["value"] is False


def test_init_sentry_with_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "http://example")
    captured = {}

    def fake_init(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("sentry_sdk.init", fake_init)
    sentry_utils.init_sentry()

    assert captured["dsn"] == "http://example"
    assert captured["send_default_pii"] is True
