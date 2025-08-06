from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin


def clean_html_keep_structure_only(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")

    blacklist = [
        "script",
        "style",
        "meta",
        "link",
        "noscript",
        "iframe",
        "svg",
        "object",
        "embed",
    ]
    for tag in soup(blacklist):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for tag in soup.find_all():
        tag.attrs = {}

    for element in soup.find_all(string=True):
        if element.parent.name not in ["script", "style"]:
            element.extract()

    return str(soup).replace("\n", "").replace("\t", "").strip()


def clean_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")

    # 定义不需要的标签
    blacklist = [
        "script",
        "style",
        "meta",
        "link",
        "noscript",
        "iframe",
        "svg",
        "object",
        "embed",
    ]

    for tag in soup(blacklist):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    cleaned = str(soup.body).replace("\n", "").replace("\r", "").replace("\t", "")
    return cleaned.strip()


def convert_relative_paths_to_absolute(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all("link", href=True):
        tag["href"] = urljoin(base_url, tag["href"])

    for tag in soup.find_all("script", src=True):
        tag["src"] = urljoin(base_url, tag["src"])

    for tag in soup.find_all("img", src=True):
        tag["src"] = urljoin(base_url, tag["src"])

    for tag in soup.find_all("a", href=True):
        if tag["href"].startswith("/"):
            tag["href"] = urljoin(base_url, tag["href"])

    return str(soup)