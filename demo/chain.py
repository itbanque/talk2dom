from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from talk2dom import ActionChain

driver = webdriver.Chrome()

(
    ActionChain(driver)
    .open("http://www.python.org")
    .find("Find the Search box")
    .type("pycon")
    .type(Keys.RETURN)
    .assert_page_not_contains("No results found.")
    .find("Find the search results")
    .wait(20)
    .close()
)
