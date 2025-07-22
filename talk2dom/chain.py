import time
from loguru import logger
from typing import Literal

from talk2dom import get_element, highlight_element, validate_element


class ActionChain:
    def __init__(
        self, driver, model="gpt-4o-mini", model_provider="openai", timeout=20
    ):
        self.driver = driver
        self.model = model
        self.model_provider = model_provider
        self.timeout = timeout
        self._current_element = None
        self._conversation_history = []

    def open(self, url, maximize=True):
        self.driver.get(url)
        if maximize:
            self.driver.maximize_window()
        logger.info(f"Opened URL: {url}")
        return self

    def find(
        self,
        description: str,
        scope: Literal["page", "element"] = "page",
        duration=None,
    ):
        element = None
        if scope == "element":
            element = self._current_element
        self._current_element = get_element(
            self.driver,
            description,
            element=element,
            model=self.model,
            model_provider=self.model_provider,
            duration=duration,
            conversation_history=self._conversation_history,
        )
        logger.info(
            f"Find element, description: {description}, element: {self._current_element}"
        )
        self._conversation_history.append([description, self._current_element])
        return self

    def valid(self, description):
        validator = validate_element(
            driver=self.driver,
            element=None,
            description=description,
            model=self.model,
            model_provider=self.model_provider,
        )
        logger.info(
            f"Validated, description: {description}, result: {validator.result}, reason: {validator.reason}"
        )
        assert validator.result is True, validator.reason
        return self

    def find_element(self, by, value: str, duration=2):
        """
        Find an element by a specific locator strategy.
        :param by: The locator strategy (e.g., By.ID, By.XPATH).
        :param value: The value of the locator.
        :param duration: Optional duration to highlight the element.
        """
        self._current_element = self.driver.find_element(by, value)
        highlight_element(self.driver, self._current_element, duration=duration)
        self._conversation_history.append(["", self._current_element])
        return self

    def click(self):
        if self._current_element:
            self._current_element.click()
        logger.info(f"Clicked on element: {self._current_element}")
        return self

    def type(self, text: str, mode="append"):
        if self._current_element:
            if mode == "replace":
                self._current_element.clear()
                self._current_element.send_keys(text)
            elif mode == "append":
                self._current_element.send_keys(text)
            else:
                raise ValueError(f"Unsupported mode: {mode}")
        logger.info(f"Typed text: {text}, mode: {mode}")
        return self

    def wait(self, seconds: float):
        time.sleep(seconds)
        logger.info(f"Waited for {seconds} seconds")
        return self

    def screenshot(self, path="screenshot.png"):
        self.driver.save_screenshot(path)
        logger.info(f"Screenshot saved to: {path}")
        return self

    def get_element(self):
        return self._current_element

    # ----- Assertions -----
    def assert_text_equals(self, expected: str):
        assert self._current_element, "No element found for assertion"
        actual = self._current_element.text.strip()
        assert actual == expected, f"Expected text: '{expected}', but got: '{actual}'"
        return self

    def assert_text_contains(self, substring: str):
        assert self._current_element, "No element found for assertion"
        actual = self._current_element.text.strip()
        assert (
            substring in actual
        ), f"Expected to contain: '{substring}', but got: '{actual}'"
        return self

    def assert_exists(self):
        assert (
            self._current_element is not None
        ), "Expected element to exist but found none"
        return self

    def assert_visible(self):
        assert self._current_element, "No element found for visibility check"
        assert self._current_element.is_displayed(), "Element exists but is not visible"
        return self

    def assert_page_not_contains(self, text: str):
        assert (
            text not in self.driver.page_source
        ), f"Unexpected text found in page: '{text}'"
        return self

    def extract_text(self):
        if not self._current_element:
            raise AssertionError("No element selected to extract text from")
        return self._current_element.text.strip()

    def extract_attribute(self, attribute: str):
        if not self._current_element:
            raise AssertionError("No element selected to extract attribute from")
        return self._current_element.get_attribute(attribute).strip()

    def close(self):
        self.driver.quit()
        logger.info("Closed the browser")
        return self
