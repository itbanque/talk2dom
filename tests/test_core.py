import pytest
from unittest.mock import MagicMock, patch
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from talk2dom.core import (
    validate_element,
    get_computed_styles,
    highlight_element,
    call_selector_llm,
    call_validator_llm,
)


@pytest.fixture
def mock_driver():
    driver = MagicMock(spec=WebDriver)
    element = MagicMock(spec=WebElement)
    element.get_attribute.return_value = (
        "<html><body><div id='main'>Content</div></body></html>"
    )
    driver.find_element.return_value = element
    driver.current_url = "http://example.com"
    return driver


@patch("talk2dom.core.get_element")
@patch("talk2dom.core.call_validator_llm")
@patch("talk2dom.core.get_computed_styles")
@patch("talk2dom.core.get_html")
def test_validate_element_success(
    mock_html, mock_styles, mock_validator, mock_get_element, mock_driver
):
    fake_element = MagicMock(spec=WebElement)
    mock_get_element.return_value = fake_element
    mock_styles.return_value = {"color": "blue"}
    mock_html.return_value = "<div>Fake</div>"
    mock_validator.return_value.result = True
    mock_validator.return_value.reason = "Element looks correct"

    result = validate_element(mock_driver, "Check blue text")
    assert result.result is True
    assert result.reason == "Element looks correct"


def test_get_computed_styles_with_props():
    driver = MagicMock()
    element = MagicMock()
    driver.execute_script.return_value = {"color": "red"}
    styles = get_computed_styles(driver, element, ["color"])
    assert styles == {"color": "red"}
    driver.execute_script.assert_called_once()


def test_get_computed_styles_all():
    driver = MagicMock()
    element = MagicMock()
    driver.execute_script.return_value = {"font-size": "12px"}
    styles = get_computed_styles(driver, element)
    assert styles == {"font-size": "12px"}


def test_highlight_element():
    driver = MagicMock()
    element = MagicMock()
    element.get_attribute.return_value = ""
    highlight_element(driver, element, duration=0)
    assert driver.execute_script.call_count == 1


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
    mock_result = MagicMock(result=True, reason="Looks good")
    fake_chain.invoke.return_value = [mock_result]
    mock_model.return_value.bind_tools.return_value.__or__.return_value = fake_chain

    res = call_validator_llm(
        "desc", "<div></div>", {"color": "blue"}, "model", "provider"
    )
    assert res.result is True
    assert res.reason == "Looks good"
