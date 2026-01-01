from talk2dom.db import init as init_module


def test_init_db_skips_when_no_session(monkeypatch):
    monkeypatch.setattr(init_module, "SessionLocal", None)
    called = {"value": False}

    def fake_create_all(*args, **kwargs):
        called["value"] = True

    monkeypatch.setattr(init_module.Base.metadata, "create_all", fake_create_all)
    init_module.init_db()
    assert called["value"] is False


def test_init_db_calls_create_all(monkeypatch):
    monkeypatch.setattr(init_module, "SessionLocal", object())
    captured = {}

    def fake_create_all(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(init_module.Base.metadata, "create_all", fake_create_all)
    monkeypatch.setattr(init_module, "engine", "engine")

    init_module.init_db()
    assert captured["bind"] == "engine"
