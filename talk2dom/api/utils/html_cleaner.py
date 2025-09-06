import re
from bs4 import BeautifulSoup, Comment, NavigableString
from urllib.parse import urljoin
import lxml  # noqa: F401

from loguru import logger

_BS_PARSER = "lxml"
_TAGSPACE_RE = re.compile(r">\s+<")


def clean_html_keep_structure_only(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, _BS_PARSER)

    # 1) Remove heavy/unsafe tags in one pass
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
    for tag in soup.select(",".join(blacklist)):
        tag.decompose()

    # 2) Strip comments
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # 3) Keep only lightweight structural tags; clear attrs; drop direct text nodes
    #    This dramatically reduces DOM size while preserving hierarchy.
    allowed = {
        "html",
        "head",
        "body",
        "main",
        "section",
        "article",
        "nav",
        "header",
        "footer",
        "div",
        "span",
        "p",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
    }
    for tag in soup.find_all(True):
        if tag.name not in allowed:
            tag.unwrap()
            continue
        if tag.attrs:
            tag.attrs.clear()
        for child in list(tag.children):
            if isinstance(child, NavigableString):
                child.extract()

    # 4) Drop empty tags (no elements and no text) to shrink output further
    for t in list(soup.find_all(True)):
        if not t.contents or not t.get_text(strip=True):
            t.decompose()

    out = str(soup)
    out = _TAGSPACE_RE.sub("><", out).replace("\n", "").replace("\t", "")
    logger.debug("Keep structured html (minified: attrs/text removed, empties pruned)")
    return out.strip()


def clean_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, _BS_PARSER)

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
    for tag in soup.select(",".join(blacklist)):
        tag.decompose()

    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # Only keep a compact set of structural tags; clear attributes to reduce payload
    allowed = {
        "html",
        "head",
        "body",
        "main",
        "section",
        "article",
        "nav",
        "header",
        "footer",
        "div",
        "span",
        "p",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
        "a",
        "img",
        "button",
        "input",
        "form",
        "label",
        "select",
        "option",
    }
    for tag in soup.find_all(True):
        if tag.name not in allowed:
            tag.unwrap()
            continue
        if tag.attrs:
            # Preserve only essential safe attrs for a few tags; drop the rest
            if tag.name in {"a"}:
                tag.attrs = {k: v for k, v in tag.attrs.items() if k in {"href"}}
            elif tag.name in {"img"}:
                tag.attrs = {k: v for k, v in tag.attrs.items() if k in {"src", "alt"}}
            else:
                tag.attrs.clear()

    # Remove empty elements to shrink output
    for t in list(soup.find_all(True)):
        # keep <img> and <input> even if self-closing
        if t.name in {"img", "input"}:
            continue
        if not t.get_text(strip=True) and not any(
            child for child in t.children if getattr(child, "name", None)
        ):
            t.decompose()

    body = soup.body if soup.body is not None else soup
    cleaned = str(body)
    cleaned = (
        _TAGSPACE_RE.sub("><", cleaned)
        .replace("\n", "")
        .replace("\r", "")
        .replace("\t", "")
    )
    logger.debug(
        "Cleaned html (minified: blacklist/comments removed, attrs trimmed, empties pruned)"
    )
    return cleaned.strip()


def convert_relative_paths_to_absolute(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, _BS_PARSER)

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
