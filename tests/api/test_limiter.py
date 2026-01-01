from starlette.requests import Request

from talk2dom.api.limiter import get_api_key_for_limit


def make_request(headers=None):
    scope = {"type": "http", "headers": []}
    if headers:
        scope["headers"] = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request(scope)


def test_get_api_key_for_limit_with_bearer():
    request = make_request({"Authorization": "Bearer abc123"})
    assert get_api_key_for_limit(request) == "abc123"


def test_get_api_key_for_limit_fallback():
    request = make_request({})
    assert get_api_key_for_limit(request) == "anonymous"
