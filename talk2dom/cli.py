from pydantic import BaseModel, Field
from typing import Literal, List

from selenium import webdriver
from talk2dom import ActionChain
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.openai_tools import PydanticToolsParser


def create_prompt_messages():
    system_message = (
        "You are a browser automation assistant. Your job is to convert natural language instructions "
        "into a sequence of structured browser actions.\n\n"
        "Each action must be one of:\n"
        "- open: open a URL\n"
        "- click: click a visible element\n"
        "- type: type into an input field\n"
        "- wait: wait for a specified duration\n"
        "- assert_text: check that text appears on the page\n"
        "- extract_text: get the visible text of an element\n\n"
        "Each step should include:\n"
        "- action (string)\n"
        "- target (string): description of element or URL\n"
        "- value (optional string): for type, assert_text and wait\n\n"
        "Example input:\n"
        "Open Google and search for 'talk2dom'\n\n"
        "Example output:\n"
        "[\n"
        '  {{"action": "open", "target": "https://www.google.com"}},\n'
        '  {{"action": "type", "target": "Search input box", "value": "talk2dom"}},\n'
        '  {{"action": "click", "target": "Search button"}},\n'
        '  {{"action": "wait", "value": "5"}},\n'
        '  {{"action": "extract_text", "target": "Price section"}}\n'
        "]"
    )
    return [("system", system_message), ("human", "{instruction}")]


class BrowserStep(BaseModel):
    action: Literal["open", "click", "type", "assert_text", "wait", "extract_text"] = (
        Field(..., description="Action to perform")
    )
    target: str | None = Field(
        None, description="What to act on or navigate to, must be natual language"
    )
    value: str | None = Field(
        None,
        description="Input number in seconds or text, required for type/assert_text/wait actions",
    )


class BrowserActions(BaseModel):
    steps: List[BrowserStep] = Field(..., description="Ordered list of browser actions")


PROMPT = ChatPromptTemplate.from_messages(create_prompt_messages())


def run_steps(actions, steps, close=True):
    try:
        for step in steps:
            print(f"▶️ Executing: {step.action.upper()} on '{step.target}'")
            if step.action == "open":
                actions.open(step.target)
            elif step.action == "click":
                actions.find(step.target).click()
            elif step.action == "type":
                actions.find(step.target).click().type(step.value)
            elif step.action == "assert_text":
                actions.find(step.target).assert_text_contains(step.value)
            elif step.action == "wait":
                print(f"⏱️ Waiting for {step.value} seconds...")
                actions.wait(int(step.value))
            elif step.action == "extract_text":
                text = actions.find(step.target).extract_text()
                print(f"📋 Extracted text: {text}")
    except KeyboardInterrupt:
        print("❌ Instruction interrupted by user.")
        exit(2)
    except Exception as error:
        print(f"❌ Error occurred: {error} at step: {step}")
        print("⚠️ Please check the instruction and try again.")
        print("💡 Note: GPT-4o has shown the best performance in testing.")
        print(
            "   If you're using another model and encountering issues, try switching to GPT-4o."
        )
        print(
            "   You’re also welcome to open a ticket: https://github.com/itbanque/talk2dom/issues"
        )
        exit(1)
    finally:
        if close:
            print("🧹 Closing browser.")
            actions.close()


def _chrome_opts(headless=False):
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return opts


def default_mode(args):
    print("💬 Starting talk2dom CLI Mode...")
    driver = webdriver.Chrome(options=_chrome_opts(args.headless))
    actions = ActionChain(driver, model=args.model, model_provider=args.provider)
    print(f"💻 Using model: {args.model} (provider: {args.provider})")
    llm = init_chat_model(model=args.model, model_provider=args.provider, temperature=0)
    chain = (
        PROMPT
        | llm.bind_tools([BrowserActions])
        | PydanticToolsParser(tools=[BrowserActions])
    )
    ba: BrowserActions = chain.invoke({"instruction": args.instruction})[0]
    steps = ba.steps

    run_steps(
        actions=actions,
        steps=steps,
    )
    print("✅ All steps completed successfully.")


def chat_mode(args):
    print("💬 Starting talk2dom Chat Mode (with context)...")
    print("Type browser commands. Type 'exit' to quit.\n")

    driver = webdriver.Chrome(options=_chrome_opts(args.headless))
    actions = ActionChain(driver, model=args.model, model_provider=args.provider)
    print(f"💻 Using model: {args.model} (provider: {args.provider})")
    llm = init_chat_model(model=args.model, model_provider=args.provider, temperature=0)
    chain = (
        PROMPT
        | llm.bind_tools([BrowserActions])
        | PydanticToolsParser(tools=[BrowserActions])
    )

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in {"exit", "quit"}:
                break
            ba: BrowserActions = chain.invoke({"instruction": user_input})[0]
            steps = ba.steps
            run_steps(
                actions=actions,
                steps=steps,
                close=False,
            )
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    print("✅ All steps completed successfully.")
    print("🧹 Chat session ended.")
    driver.quit()
    exit(0)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run a natural language browser instruction."
    )
    parser.add_argument(
        "instruction", type=str, nargs="?", help="Natural language command to run"
    )
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model to use")
    parser.add_argument("--provider", default="openai", help="Model provider")
    parser.add_argument(
        "--playground", action="store_true", help="Enter interactive playground mode"
    )
    parser.add_argument(
        "--chat", action="store_true", help="Start interactive chat mode with context"
    )
    args = parser.parse_args()
    if not args.chat and not args.instruction:
        parser.error(
            "The following arguments are required: instruction (unless using --chat)"
        )
    if args.chat:
        chat_mode(args)

    default_mode(args)
