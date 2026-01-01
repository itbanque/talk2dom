import inspect
from types import SimpleNamespace

from talk2dom.api.routers import inference
from talk2dom.api.schemas import LocatorRequest


def test_locator_playground_cache_action_split(monkeypatch):
    monkeypatch.setattr(
        inference,
        "get_cached_locator",
        lambda *_args, **_kwargs: ("css selector", "#login", "click:email"),
    )

    class DummyValidator:
        def __init__(self, _html):
            pass

        def verify(self, _type, _selector):
            return True

    monkeypatch.setattr(inference, "SelectorValidator", DummyValidator)
    monkeypatch.setattr(inference, "clean_html", lambda html: html)
    monkeypatch.setattr(inference, "clean_html_keep_structure_only", lambda html: html)

    req = LocatorRequest(
        url="https://example.com", html="<div></div>", user_instruction="click"
    )
    request = SimpleNamespace(state=SimpleNamespace())
    user = SimpleNamespace(id="u1", email="u@example.com")

    func = inspect.unwrap(inference.locate_playground)
    resp = func(req=req, request=request, db=None, user=user)

    assert resp.action_type == "click"
    assert resp.action_value == "email"
    assert resp.selector_type == "css selector"
    assert resp.selector_value == "#login"
