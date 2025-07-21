from talk2dom.core import Selector, Validator
from selenium.webdriver.common.by import By


class FakeWebElement:
    def get_attribute(self, name):
        if name == "outerHTML":
            return "<body><button>Click me</button></body>"
        raise AttributeError()


class FakeWebDriver:
    def find_element(self, by, value):
        assert by == By.TAG_NAME
        assert value == "body"
        return FakeWebElement()

    def get_attribute(self, name):
        if name == "outerHTML":
            return "<body><button>Click me</button></body>"
        raise AttributeError()


def test_selector_model():
    s = Selector(selector_type="xpath", selector_value="/html/body/div")
    assert s.selector_type == "xpath"
    assert s.selector_value.startswith("/")


def test_validator():
    v = Validator(
        result=True,
        reason="Element found",
    )
    assert v.result is True
    assert v.reason == "Element found"


def test_call_llm_with_fake_web_element(monkeypatch):
    def fake_llm(*args, **kwargs):
        return Selector(selector_type="xpath", selector_value="//button")

    from talk2dom import core

    monkeypatch.setattr(core, "call_selector_llm", fake_llm)
    result = core.call_selector_llm(
        "Click the button",
        "<html><body><button>Click me</button></body></html>",
        "gpt-4o",
        "openai",
    )
    assert result.selector_type == "xpath"


def test_validator_with_fake_web_element(monkeypatch):
    def fake_llm(*args, **kwargs):
        return Validator(result=True, reason="Element is valid")

    from talk2dom import core

    fake_element = FakeWebElement()
    monkeypatch.setattr(core, "call_validator_llm", fake_llm)
    result = core.validate_element(
        fake_element,
        "Validate the button",
        "gpt-4o",
        "openai",
    )
    assert result.result is True
    assert result.reason == "Element is valid"


def test_validator_with_fake_webdriver(monkeypatch):
    def fake_llm(*args, **kwargs):
        return Validator(result=True, reason="Element is valid")

    from talk2dom import core

    fake_driver = FakeWebDriver()
    monkeypatch.setattr(core, "call_validator_llm", fake_llm)
    result = core.validate_element(
        fake_driver,
        "Validate the button",
        "gpt-4o",
        "openai",
    )
    assert result.result is True
    assert result.reason == "Element is valid"
