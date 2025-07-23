import pytest
from unittest.mock import MagicMock, patch

from talk2dom.db.cache import (
    compute_locator_id,
    get_cached_locator,
    save_locator,
    delete_locator,
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
    mock_session.query().filter_by().first.return_value = mock_row

    selector_type, selector_value = get_cached_locator(
        "desc", "<html></html>", url="http://test.com"
    )
    assert selector_type == "id"
    assert selector_value == "login"


def test_get_cached_locator_miss(mock_session):
    mock_session.query().filter_by().first.return_value = None
    selector_type, selector_value = get_cached_locator(
        "desc", "<html></html>", url="http://test.com"
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
        save_locator("desc", "<html></html>", "id", "login", url="http://example.com")
        assert mock_session.add.called
        assert mock_session.commit.called


def test_save_locator_duplicate(mock_session):
    with patch("talk2dom.db.cache.locator_exists", return_value=True):
        save_locator("desc", "<html></html>", "id", "login", url="http://example.com")
        assert not mock_session.add.called
        assert not mock_session.commit.called


def test_delete_locator_found(mock_session):
    mock_row = MagicMock()
    mock_session.query().filter_by().first.return_value = mock_row

    deleted = delete_locator("desc", "<html></html>", url="http://example.com")
    assert deleted is True
    assert mock_session.delete.called
    assert mock_session.commit.called


def test_delete_locator_not_found(mock_session):
    mock_session.query().filter_by().first.return_value = None
    deleted = delete_locator("desc", "<html></html>", url="http://example.com")
    assert deleted is False
