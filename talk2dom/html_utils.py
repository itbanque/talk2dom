from bs4 import BeautifulSoup
from selenium.webdriver.remote.webdriver import WebDriver


def get_visible_body_html(driver: WebDriver) -> str:
    script = """
    const clone = document.body.cloneNode(true);
    const treeWalker = document.createTreeWalker(clone, NodeFilter.SHOW_ELEMENT);
    let currentNode;
    while ((currentNode = treeWalker.nextNode())) {
        const style = window.getComputedStyle(currentNode);
        if (
            style.display === 'none' ||
            style.visibility === 'hidden' ||
            currentNode.getAttribute('aria-hidden') === 'true'
        ) {
            currentNode.remove();
        }
    }
    return clone.outerHTML;
    """
    return driver.execute_script(script)


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "meta", "link", "noscript", "input"]):
        if tag.name == "input" and tag.get("type") != "hidden":
            continue
        tag.decompose()
    return str(soup)


def trim_html_depth(html: str, max_depth: int = 5) -> str:
    soup = BeautifulSoup(html, "html.parser")

    def trim(node, depth):
        if depth > max_depth:
            node.decompose()
            return
        for child in list(node.children):
            if hasattr(child, "children"):
                trim(child, depth + 1)

    trim(soup.body, 1)
    return str(soup.body)


def extract_clean_html(driver: WebDriver) -> str:
    html = get_visible_body_html(driver)
    html = clean_html(html)
    html = trim_html_depth(html)
    return html
