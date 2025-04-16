import time
from typing import Literal

from talk2dom import get_element


class ActionChain:
    def __init__(
        self, driver, model="gpt-4o-mini", model_provider="openai", timeout=20
    ):
        self.driver = driver
        self.model = model
        self.model_provider = model_provider
        self.timeout = timeout
        self._current_element = None

    def open(self, url, maximize=True):
        self.driver.get(url)
        if maximize:
            self.driver.maximize_window()
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
        )
        return self

    def click(self):
        if self._current_element:
            self._current_element.click()
        return self

    def type(self, text: str, mode="replace"):
        if self._current_element:
            if mode == "replace":
                self._current_element.clear()
                self._current_element.send_keys(text)
            elif mode == "append":
                self._current_element.send_keys(text)
            else:
                raise ValueError(f"Unsupported mode: {mode}")
        return self

    def wait(self, seconds: float):
        time.sleep(seconds)
        return self

    def screenshot(self, path="screenshot.png"):
        self.driver.save_screenshot(path)
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

    def close(self):
        self.driver.quit()
        return self
