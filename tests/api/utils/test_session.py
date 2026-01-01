from starlette.responses import Response

from talk2dom.api.utils.session import create_session


class DummyUser:
    def __init__(self, user_id):
        self.id = user_id


def test_create_session_sets_cookie():
    response = Response()
    user = DummyUser("123")

    create_session(user, response)

    cookie = response.headers.get("set-cookie")
    assert "session=123" in cookie
    assert "HttpOnly" in cookie
    assert "Max-Age=604800" in cookie
