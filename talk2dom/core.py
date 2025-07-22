import time
from enum import Enum

from pydantic import BaseModel, Field

from bs4 import BeautifulSoup

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers.openai_tools import PydanticToolsParser

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

from pathlib import Path

from loguru import logger

from talk2dom.db.cache import get_cached_locator, save_locator
from talk2dom.db.init import init_db


init_db()


def load_prompt(file_path: str) -> str:
    prompt_path = Path(__file__).parent / "prompts" / file_path
    return prompt_path.read_text(encoding="utf-8").strip()


# ------------------ Pydantic Schema ------------------


class SelectorType(str, Enum):
    ID = "id"
    TAG_NAME = "tag name"
    NAME = "name"
    CLASS_NAME = "class name"
    XPATH = "xpath"
    CSS_SELECTOR = "css selector"


class Selector(BaseModel):
    selector_type: SelectorType
    selector_value: str = Field(description="The selector string")


class Validator(BaseModel):
    result: bool = Field(description="Whether the user description is true/false")
    reason: str = Field(description="The reason why the user description is true/false")


# ------------------ LLM Function Call ------------------


def call_selector_llm(
    user_instruction, html, model, model_provider, conversation_history=None
) -> Selector:
    logger.warning("Calling LLM for selector generation...")
    llm = init_chat_model(model, model_provider=model_provider)
    chain = llm.bind_tools([Selector]) | PydanticToolsParser(tools=[Selector])

    query = load_prompt("locator_prompt.txt")
    if conversation_history:
        query += "\n\n## Conversation History:"
        for user_message, assistant_message in conversation_history:
            query += f"\n\nUser: {user_message}\n\nAssistant: {assistant_message}"
    query += f"\n\n## HTML: \n{html}\n\nUser: {user_instruction}\n\nAssistant:"
    logger.debug(f"Query for LLM: {query}")
    response = chain.invoke(query)[0]
    return response


def call_validator_llm(
    user_instruction, html, css_style, model, model_provider, conversation_history=None
) -> Validator:
    logger.warning("Calling validator LLM...")
    llm = init_chat_model(model, model_provider=model_provider)
    chain = llm.bind_tools([Validator]) | PydanticToolsParser(tools=[Validator])

    query = load_prompt("validator_prompt.txt")
    if conversation_history:
        query += "\n\n## Conversation History:"
        for user_message, assistant_message in conversation_history:
            query += f"\n\nUser: {user_message}\n\nAssistant: {assistant_message}"
    query += f"\n\n## HTML: \n{html}\n\n## STYLES: \n{css_style}\n\nUser: {user_instruction}\n\nAssistant:"
    logger.debug(f"Query for LLM: {query}")
    response = chain.invoke(query)[0]
    return response


def highlight_element(driver, element, duration=2):
    style = (
        "box-shadow: 0 0 10px 3px rgba(255, 0, 0, 0.7);"
        "outline: 2px solid red;"
        "background-color: rgba(255, 230, 200, 0.3);"
        "transition: all 0.2s ease-in-out;"
    )
    original_style = element.get_attribute("style")
    driver.execute_script(f"arguments[0].setAttribute('style', '{style}')", element)
    if duration:
        time.sleep(duration)
        driver.execute_script(
            f"arguments[0].setAttribute('style', `{original_style}`)", element
        )
    logger.debug(f"Highlighted element: {element}")


def get_computed_styles(driver, element, properties=None):
    """
    Get the computed styles of a WebElement using JavaScript.
    :param driver: Selenium WebDriver
    :param element: WebElement
    :param properties: List of CSS properties to retrieve. If None, retrieves all properties.
    :return: dict of {property: value}
    """
    if properties:
        script = """
        const element = arguments[0];
        const properties = arguments[1];
        const styles = window.getComputedStyle(element);
        const result = {};
        for (let prop of properties) {
            result[prop] = styles.getPropertyValue(prop);
        }
        return result;
        """
        return driver.execute_script(script, element, properties)
    else:
        script = """
        const element = arguments[0];
        const styles = window.getComputedStyle(element);
        const result = {};
        for (let i = 0; i < styles.length; i++) {
            const name = styles[i];
            result[name] = styles.getPropertyValue(name);
        }
        return result;
        """
        return driver.execute_script(script, element)


def get_html(element):
    html = (
        element.find_element(By.TAG_NAME, "body").get_attribute("outerHTML")
        if isinstance(element, WebDriver)
        else element.get_attribute("outerHTML")
    )
    soup = BeautifulSoup(html, "lxml")

    # remove unnecessary tags
    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()

    html = soup.prettify()
    return html


# ------------------ Public API ------------------


def get_locator(
    element,
    description,
    model="gpt-4o-mini",
    model_provider="openai",
    conversation_history=None,
):
    """
    Get the locator for the element using LLM.
    :param element: The element to locate.
    :param description: The description of the element.
    :param model: The model to use for the LLM.
    :param model_provider: The model provider to use for the LLM.
    :param conversation_history: The conversation history to use for the LLM.
    :return: The locator type and value.
    """
    html = (
        element.find_element(By.TAG_NAME, "body").get_attribute("outerHTML")
        if isinstance(element, WebDriver)
        else element.get_attribute("outerHTML")
    )
    soup = BeautifulSoup(html, "lxml")

    # remove unnecessary tags
    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()

    html = soup.prettify()
    logger.debug(
        f"Generating locator, instruction: {description}, HTML: {html[500:]}..."
    )  # Log first 500 chars

    selector_type, selector_value = get_cached_locator(description, html)
    if selector_type and selector_value:
        logger.info(f"Using cached locator: {selector_type}, value: {selector_value}")
        return selector_type, selector_value

    selector = call_selector_llm(
        description, html, model, model_provider, conversation_history
    )

    if selector.selector_type not in [
        "id",
        "tag name",
        "name",
        "class name",
        "xpath",
        "css selector",
    ]:
        raise ValueError(f"Unsupported selector type: {selector.selector_type}")

    logger.info(
        f"Located by: {selector.selector_type}, selector: {selector.selector_value.strip()}"
    )
    save_locator(
        description, html, selector.selector_type, selector.selector_value.strip()
    )
    return selector.selector_type, selector.selector_value.strip()


def get_element(
    driver,
    description,
    element=None,
    model="gpt-4o-mini",
    model_provider="openai",
    duration=None,
    conversation_history=None,
):
    """
    Get the element using LLM.
    :param driver: The WebDriver instance.
    :param description: The description of the element.
    :param element: The element to locate.
    :param model: The model to use for the LLM.
    :param model_provider: The model provider to use for the LLM.
    :param duration: The duration to highlight the element.
    :param conversation_history: The conversation history to use for the LLM.
    :return: The located element.
    """
    if element is None:
        selector_type, selector_value = get_locator(
            driver, description, model, model_provider, conversation_history
        )
    else:
        selector_type, selector_value = get_locator(
            element, description, model, model_provider, conversation_history
        )
    elem = driver.find_element(
        selector_type, selector_value
    )  # Ensure the page is loaded
    highlight_element(driver, elem, duration=duration)
    return elem


def validate_element(
    driver,
    description,
    element=None,
    model="gpt-4o-mini",
    model_provider="openai",
    duration=None,
    conversation_history=None,
):
    try:
        ele = get_element(
            driver,
            description,
            element=element,
            model=model,
            model_provider=model_provider,
            duration=duration,
            conversation_history=conversation_history,
        )
        css_style = get_computed_styles(driver, ele)
    except Exception as e:
        logger.error(f"Failed to get element: {description}, error: {e}")
        css_style = {}

    html = get_html(driver)
    validator = call_validator_llm(
        description,
        html,
        css_style,
        model,
        model_provider,
        conversation_history,
    )
    return validator
