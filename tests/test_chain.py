import unittest
from unittest.mock import MagicMock
from selenium.webdriver.common.by import By
from talk2dom.chain import ActionChain


class TestActionChain(unittest.TestCase):
    def setUp(self):
        self.driver = MagicMock()
        self.chain = ActionChain(driver=self.driver)

    def test_open(self):
        self.chain.open("https://example.com")
        self.driver.get.assert_called_with("https://example.com")
        self.driver.maximize_window.assert_called_once()

    def test_find_element(self):
        element = MagicMock()
        self.driver.find_element.return_value = element
        self.chain.find_element(By.ID, "test-id")
        self.assertEqual(self.chain.get_element(), element)

    def test_type_append(self):
        element = MagicMock()
        self.chain._current_element = element
        self.chain.type("hello", mode="append")
        element.send_keys.assert_called_with("hello")

    def test_type_replace(self):
        element = MagicMock()
        self.chain._current_element = element
        self.chain.type("hi", mode="replace")
        element.clear.assert_called_once()
        element.send_keys.assert_called_with("hi")

    def test_click(self):
        element = MagicMock()
        self.chain._current_element = element
        self.chain.click()
        element.click.assert_called_once()

    def test_assert_text_equals(self):
        element = MagicMock()
        element.text = " Hello "
        self.chain._current_element = element
        self.chain.assert_text_equals("Hello")

    def test_assert_text_contains(self):
        element = MagicMock()
        element.text = "Welcome Home"
        self.chain._current_element = element
        self.chain.assert_text_contains("Home")

    def test_assert_exists(self):
        self.chain._current_element = MagicMock()
        self.chain.assert_exists()

    def test_assert_visible(self):
        element = MagicMock()
        element.is_displayed.return_value = True
        self.chain._current_element = element
        self.chain.assert_visible()

    def test_extract_text(self):
        element = MagicMock()
        element.text = "  content "
        self.chain._current_element = element
        self.assertEqual(self.chain.extract_text(), "content")

    def test_extract_attribute(self):
        element = MagicMock()
        element.get_attribute.return_value = " value "
        self.chain._current_element = element
        self.assertEqual(self.chain.extract_attribute("value"), "value")

    def test_assert_page_contains(self):
        self.driver.page_source = "<html>hello world</html>"
        self.chain.driver = self.driver
        self.chain.assert_page_contains("hello")

    def test_assert_page_not_contains(self):
        self.driver.page_source = "<html>hello world</html>"
        self.chain.driver = self.driver
        self.chain.assert_page_not_contains("notfound")

    def test_wait(self):
        self.chain.wait(0.1)  # should not raise

    def test_close(self):
        self.driver.quit = MagicMock()
        self.chain.close()
        self.driver.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
