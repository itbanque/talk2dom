import pytest
from unittest.mock import MagicMock, patch


# --- In-memory Redis stub for tests (no external service required) ---
class _MiniRedis:
    def __init__(self):
        self._store = {}

    def hset(self, key, mapping=None, **kwargs):
        if mapping:
            # Redis expects all values to be bytes, str, int, or float
            safe_mapping = {}
            for k, v in mapping.items():
                # Convert MagicMock or None to string or empty string for test compatibility
                if hasattr(v, "assert_called_with") or hasattr(v, "assert_not_called"):
                    safe_mapping[k] = ""
                elif v is None:
                    safe_mapping[k] = ""
                else:
                    safe_mapping[k] = v
            self._store.setdefault(key, {}).update(safe_mapping)
        return 1

    def hgetall(self, key):
        return dict(self._store.get(key, {}))

    def expire(self, key, ttl):
        # TTL is ignored in stub but kept for API compatibility
        return True

    def delete(self, key):
        return 1 if self._store.pop(key, None) is not None else 0


@pytest.fixture(autouse=True)
def _patch_redis(monkeypatch):
    # Patch talk2dom.db.cache._redis to return an in-memory stub per test
    from talk2dom.db import cache as cache_mod

    stub = _MiniRedis()
    monkeypatch.setattr(cache_mod, "_redis", lambda: stub)
    yield stub


from talk2dom.db.cache import (
    compute_locator_id,
    get_cached_locator,
    save_locator,
    locator_exists,
)


@pytest.fixture
def mock_session():
    with patch("talk2dom.db.cache.SessionLocal") as mock_session_local:
        session = MagicMock()
        mock_session_local.return_value = session
        yield session


def test_compute_locator_id_same_input_same_id():
    instruction = "Click the login button"
    html = "<button id='login'>Login</button>"
    url = "http://example.com"
    id1 = compute_locator_id(instruction, html, url)
    id2 = compute_locator_id(instruction, html, url)
    assert id1 == id2


def test_get_cached_locator_hit(mock_session):
    mock_row = MagicMock()
    mock_row.selector_type = "id"
    mock_row.selector_value = "login"
    mock_row.action = None
    mock_session.query().filter_by().first.return_value = mock_row

    selector_type, selector_value, action = get_cached_locator(
        "desc", "<html></html>", url="http://test.com"
    )
    assert selector_type == "id"
    assert selector_value == "login"


def test_get_cached_locator_miss(mock_session):
    mock_session.query().filter_by().first.return_value = None
    # Use a URL not used in the hit test, so redis is empty
    selector_type, selector_value, action = get_cached_locator(
        "desc", "<html></html>", url="http://miss.test"
    )
    assert selector_type is None
    assert selector_value is None


def test_locator_exists_true(mock_session):
    mock_session.query().filter_by().first.return_value = True
    assert locator_exists("abc123") is True


def test_locator_exists_false(mock_session):
    mock_session.query().filter_by().first.return_value = None
    assert locator_exists("not-exist") is False


def test_save_locator_new(mock_session):
    with patch("talk2dom.db.cache.locator_exists", return_value=False):
        save_locator(
            "desc",
            "<html></html>",
            "id",
            "login",
            url="http://example.com",
            project_id="test",
        )
        assert mock_session.commit.called
