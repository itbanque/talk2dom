import time
import logging
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from talk2dom import ActionChain
from talk2dom.html_utils import extract_clean_html
from talk2dom.core import Selector, load_prompt
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.openai_tools import PydanticToolsParser

from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
    InvalidElementStateException,
    InvalidSelectorException,
)
from selenium.webdriver.common.by import By


LOGGER = logging.getLogger(__name__)


class AgentStep(BaseModel):
    action: Literal["open", "click", "type", "done"] = Field(
        description="Action to perform, "
        "open -> You want to open some URL"
        "type -> You want to type some text"
        "done -> You want to stop"
    )
    selector: str | None = Field(
        description="The css selector to use locate the element, like .con-wizard",
    )
    target: str | None = Field(
        description="open -> URL, type-> string",
    )
    result: str | None = Field(
        description="if the action is done, use this field to answer user's question",
    )


def build_agent_prompt(goal: str, url: str, html: str, history: list, error: str = ""):
    prompt_template = ChatPromptTemplate.from_template(load_prompt("agent_prompt.txt"))
    return prompt_template.format_messages(
        goal=goal,
        url=url,
        html=html,
        history="\n".join([f"{s.action} → {s.target}" for s in history]),
        error=error,
    )


def inference(prompt, model, model_provider, temperature=0.8):
    llm = init_chat_model(
        model=model, model_provider=model_provider, temperature=temperature
    )
    chain = llm.bind_tools([AgentStep]) | PydanticToolsParser(tools=[AgentStep])
    # print(llm.invoke(prompt))
    agent: AgentStep = chain.invoke(prompt)
    if len(agent) == 1:
        return agent[0]


class AgentLoop:
    def __init__(self, driver, model="gpt-4o-mini", provider="openai"):
        self.driver = driver
        self.model = model
        self.provider = provider
        self.history: List[AgentStep] = []

    def run(self, goal: str, max_steps: int = 20):
        actions = ActionChain(
            self.driver, model=self.model, model_provider=self.provider
        )
        last_error = ""

        for i in range(max_steps):
            try:
                # html = extract_clean_html(self.driver)
                html = self.driver.find_element(By.TAG_NAME, "body")
                url = self.driver.current_url
                prompt = build_agent_prompt(
                    goal=goal,
                    url=url,
                    html=html,
                    history=self.history,
                    error=last_error,
                )

                LOGGER.info("🧠 Asking LLM for step %d", i + 1)
                step = inference(prompt, self.model, self.provider)
                if not step:
                    continue
                LOGGER.info("🔁 Step %d: %s → %s", i + 1, step.action, step.target)
                self.history.append(step)
                if step.action in ["done", "return"]:
                    return step.result or "✅ Task complete."

                self.execute_step(actions, step)

            except NoSuchElementException as e:
                LOGGER.warning("⚠️ Step %d failed: %s", i + 1, str(e))
                last_error = str(e)
            except ElementNotInteractableException as e:
                LOGGER.warning("⚠️ Step %d failed: %s", i + 1, str(e))
                last_error = str(e)
            except ElementClickInterceptedException as e:
                LOGGER.warning("⚠️ Step %d failed: %s", i + 1, str(e))
                last_error = str(e)
            except InvalidElementStateException as e:
                LOGGER.warning("⚠️ Step %d failed: %s", i + 1, str(e))
                last_error = str(e)
            except InvalidSelectorException as e:
                LOGGER.warning("⚠️ Step %d failed: %s", i + 1, str(e))
                last_error = str(e)
            time.sleep(2)

        return "⚠️ Max step count reached."

    def execute_step(self, actions: ActionChain, step: AgentStep):
        print(step)
        if step.action == "open":
            return actions.open(step.target)
        elif step.action == "click":
            return actions.get(By.CSS_SELECTOR, step.selector).click()
        elif step.action == "type":
            return actions.get(By.CSS_SELECTOR, step.selector).type(step.target)
        elif step.action == "assert_text":
            return actions.get(By.CSS_SELECTOR, step.selector).assert_text(step.target)
        elif step.action == "extract_text":
            return actions.get(By.CSS_SELECTOR, step.selector).extract_text()
        elif step.action == "wait":
            return actions.wait(int(step.target or 2))
        return None


from selenium import webdriver

driver = webdriver.Chrome()
A = AgentLoop(
    driver,
    model="gpt-4o",
    # model="meta-llama/llama-4-scout-17b-16e-instruct",
    # provider="groq",
)
result = A.run("Get the latest python version")
print(result)
# prompt = build_agent_prompt("get the apple stock price", "", "<body></body>", [], "")
# inference(prompt, "meta-llama/llama-4-scout-17b-16e-instruct", "groq")
