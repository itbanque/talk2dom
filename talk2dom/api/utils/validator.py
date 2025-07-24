from bs4 import BeautifulSoup
from lxml import etree
from typing import Literal


class SelectorValidator:
    def __init__(self, html: str):
        self.html = html
        self.soup = BeautifulSoup(html, "html.parser")
        self.tree = etree.HTML(html)

    def verify(self, type_: str, selector: str) -> bool:
        try:
            type_ = type_.lower()
            if type_ == "id":
                return bool(self.soup.select(f"#{selector}"))
            elif type_ == "class name":
                return bool(self.soup.select(f".{selector}"))
            elif type_ == "name":
                return bool(self.soup.select(f"[name='{selector}']"))
            elif type_ == "tag name":
                return bool(self.soup.select(selector))
            elif type_ == "css selector":
                return bool(self.soup.select(selector))
            elif type_ == "xpath":
                return bool(self.tree.xpath(selector))
            else:
                raise ValueError(f"Unsupported selector type: {type_}")
        except Exception:
            return False
