import os
import time
import functools
from pathlib import Path

from enum import Enum
from pydantic import BaseModel, Field

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers.openai_tools import PydanticToolsParser

from playwright.sync_api import sync_playwright

from loguru import logger

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

langfuse = Langfuse(
    public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
    host=os.environ.get("LANGFUSE_HOST"),
)

langfuse_handler = CallbackHandler()


def retry(
    exceptions: tuple = (Exception,),
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    logger_enabled: bool = True,
):
    """
    Retry decorator with exponential backoff.

    Args:
        exceptions: Tuple of exception classes to catch.
        max_attempts: Maximum number of retry attempts.
        delay: Initial delay between retries (in seconds).
        backoff: Multiplier applied to delay after each failure.
        logger_enabled: Whether to log retry attempts.

    Usage:
        @retry(max_attempts=5, delay=2)
        def unstable_operation():
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        raise
                    if logger_enabled:
                        logger.warning(
                            f"[Retry] Attempt {attempt} failed: {e}. Retrying in {current_delay:.1f}s..."
                        )
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1

        return wrapper

    return decorator


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
    NOT_FOUND = "not found"


class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    NOT_FOUND = ""


class Selector(BaseModel):
    selector_type: SelectorType
    selector_value: str = Field(description="The selector string")
    action_type: ActionType = Field(
        description="The action type, only include: click, type, and empty"
    )
    action_value: str = Field(description="The action value, the str you want to type")


class Validator(BaseModel):
    result: bool = Field(description="Whether the user description is true/false")
    reason: str = Field(description="The reason why the user description is true/false")


# ------------------ LLM Function Call ------------------


def call_selector_llm(
    user_instruction,
    html,
    model,
    model_provider,
    conversation_history=None,
    metadata={},
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
    logger.debug(f"Query for LLM: {query[0:100]}")
    try:
        response = chain.invoke(
            query, config={"callbacks": [langfuse_handler], "metadata": metadata}
        )[0]
        return response
    except Exception as e:
        logger.error(f"Query failed: {e}")


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
    logger.debug(f"Query for LLM: {query[500:]}")
    try:
        response = chain.invoke(query)[0]
        return response
    except Exception as e:
        logger.error(f"Query failed: {e}")


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


def get_page_content(url: str, view="desktop"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        if view == "mobile":
            page.set_viewport_size({"width": 375, "height": 812})
        else:
            page.set_viewport_size({"width": 1280, "height": 720})
        page.goto(url)
        content = page.content()
        browser.close()
    return content


# ------------------ Public API ------------------
