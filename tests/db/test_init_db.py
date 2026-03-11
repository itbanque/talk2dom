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
    seeded = {"value": False}

    def fake_create_all(*args, **kwargs):
        captured.update(kwargs)

    def fake_seed_local_data():
        seeded["value"] = True

    monkeypatch.setattr(init_module.Base.metadata, "create_all", fake_create_all)
    monkeypatch.setattr(init_module, "engine", "engine")
    monkeypatch.setattr(init_module, "seed_local_data", fake_seed_local_data)

    init_module.init_db()
    assert captured["bind"] == "engine"
    assert seeded["value"] is True


def test_seed_local_data_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("LOCAL_SEED_ENABLED", "false")
    called = {"value": False}

    def fake_session_local():
        called["value"] = True
        return None

    monkeypatch.setattr(init_module, "SessionLocal", fake_session_local)
    init_module.seed_local_data()
    assert called["value"] is False
