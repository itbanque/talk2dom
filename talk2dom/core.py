import logging
from pydantic import BaseModel, Field

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers.openai_tools import PydanticToolsParser

from selenium.webdriver.remote.webdriver import WebDriver

from pathlib import Path


LOGGER = logging.getLogger(__name__)


def load_prompt(file_path: str) -> str:
    prompt_path = Path(__file__).parent / "prompts" / file_path
    return prompt_path.read_text(encoding="utf-8").strip()


# ------------------ Pydantic Schema ------------------


class Selector(BaseModel):
    selector_type: str = Field(
        description="Either 'id', 'tag name', 'name', 'class name', 'xpath' or 'css selector'"
    )
    selector_value: str = Field(description="The selector string")


tools = [Selector]


# ------------------ LLM Function Call ------------------


def call_llm(user_instruction, html, model, model_provider) -> Selector:
    llm = init_chat_model(model, model_provider=model_provider)
    chain = llm.bind_tools(tools) | PydanticToolsParser(tools=tools)

    query = (
        load_prompt("locator_prompt.txt") + "\n\n" + user_instruction + "\n\n" + html
    )
    response = chain.invoke(query)[0]
    return response


# ------------------ Public API ------------------


def get_locator(driver, description, model="gpt-4o-mini", model_provider="openai"):
    html = (
        driver.page_source
        if isinstance(driver, WebDriver)
        else driver.get_attribute("outerHTML")
    )
    selector = call_llm(description, html, model, model_provider)

    if selector.selector_type not in [
        "id",
        "tag name",
        "name",
        "class name",
        "xpath",
        "css selector",
    ]:
        raise ValueError(f"Unsupported selector type: {selector.selector_type}")

    LOGGER.info(
        "Located by: %s, selector: %s", selector.selector_type, selector.selector_value
    )
    return selector.selector_type, selector.selector_value.strip()
