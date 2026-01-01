from unittest.mock import MagicMock, patch


from talk2dom.core import (
    call_selector_llm,
    call_validator_llm,
    retry,
    load_prompt,
    highlight_element,
    get_computed_styles,
)


@patch("talk2dom.core.init_chat_model")
@patch("talk2dom.core.load_prompt", return_value="prompt")
def test_call_selector_llm(mock_prompt, mock_model):
    fake_chain = MagicMock()
    fake_chain.invoke.return_value = [
        MagicMock(selector_type="id", selector_value="main")
    ]
    mock_model.return_value.bind_tools.return_value.__or__.return_value = fake_chain

    result = call_selector_llm("click", "<div></div>", "model", "provider")
    assert result.selector_type == "id"
    assert result.selector_value == "main"


@patch("talk2dom.core.init_chat_model")
@patch("talk2dom.core.load_prompt", return_value="prompt")
def test_call_validator_llm(mock_prompt, mock_model):
    fake_chain = MagicMock()
    fake_chain.invoke.return_value = [MagicMock(result=True, reason="ok")]
    mock_model.return_value.bind_tools.return_value.__or__.return_value = fake_chain

    result = call_validator_llm("click", "<div></div>", "body{}", "model", "provider")
    assert result.result is True
    assert result.reason == "ok"


def test_retry_decorator_retries_and_succeeds():
    calls = {"count": 0}

    @retry(exceptions=(ValueError,), max_attempts=3, delay=0, backoff=1)
    def flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise ValueError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 2


def test_retry_decorator_raises_after_max_attempts():
    calls = {"count": 0}

    @retry(exceptions=(ValueError,), max_attempts=2, delay=0, backoff=1)
    def always_fail():
        calls["count"] += 1
        raise ValueError("nope")

    try:
        always_fail()
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")
    assert calls["count"] == 2


def test_load_prompt_reads_prompt_file():
    prompt = load_prompt("locator_prompt.txt")
    assert "Your job is to identify the correct DOM element" in prompt


def test_highlight_element_sets_and_restores_style(monkeypatch):
    calls = []

    class DummyElement:
        def get_attribute(self, name):
            assert name == "style"
            return "color: red;"

    class DummyDriver:
        def execute_script(self, script, element):
            calls.append(script)

    monkeypatch.setattr("talk2dom.core.time.sleep", lambda _: None)

    highlight_element(DummyDriver(), DummyElement(), duration=1)
    assert "setAttribute('style'" in calls[0]
    assert "setAttribute('style'" in calls[1]


def test_get_computed_styles_with_properties():
    class DummyDriver:
        def execute_script(self, script, element, properties=None):
            return {"color": "red", "display": "block"}

    result = get_computed_styles(DummyDriver(), object(), ["color", "display"])
    assert result == {"color": "red", "display": "block"}


def test_get_computed_styles_all_properties():
    class DummyDriver:
        def execute_script(self, script, element):
            return {"color": "red"}

    result = get_computed_styles(DummyDriver(), object())
    assert result == {"color": "red"}
