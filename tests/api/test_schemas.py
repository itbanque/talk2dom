import pytest
from pydantic import ValidationError

from talk2dom.api import schemas


def test_locator_request_defaults():
    req = schemas.LocatorRequest(url="http://example.com", user_instruction="click")
    assert req.view == schemas.ViewMode.desktop


def test_invite_request_requires_email():
    with pytest.raises(ValidationError):
        schemas.InviteRequest(email="not-an-email")
