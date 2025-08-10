import pytest
from bs4 import BeautifulSoup

# Try common import paths; adjust to your project layout if needed.

from talk2dom.api.utils.html_cleaner import (
    clean_html_keep_structure_only,
    clean_html,
    convert_relative_paths_to_absolute,
)

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Test</title>
  <link rel="stylesheet" href="/assets/main.css" />
  <style>.x { color: red; }</style>
  <script>console.log('hi');</script>
</head>
<body id="bodyId" class="bodyClass">
  <!-- top comment -->
  <div id="wrapper" class="wrap">
    <header data-x="1">Header <span style="font-weight:bold">Title</span></header>
    <nav>
      <a id="home" href="/home">Home</a>
      <a id="about" href="about.html">About</a>
      <a id="abs" href="https://example.com/abs">Abs</a>
    </nav>
    <main>
      <img src="images/logo.png" alt="logo"/>
      <iframe src="/frame.html"></iframe>
      <svg></svg>
      <object data="foo"></object>
      <embed src="bar" />
      <section class="content">Visible text <em>here</em>.</section>
      <!-- inner comment -->
    </main>
    <script src="/js/app.js"></script>
  </div>
  <noscript>noscript content</noscript>
</body>
</html>
""".strip()


def _parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_clean_html_keep_structure_only_removes_text_attrs_and_blacklist():
    out = clean_html_keep_structure_only(SAMPLE_HTML)

    # Should be a compact string without newlines/tabs
    assert "\n" not in out and "\t" not in out

    soup = _parse(out)

    # Blacklisted tags should be gone entirely
    for tag in [
        "script",
        "style",
        "meta",
        "link",
        "noscript",
        "iframe",
        "svg",
        "object",
        "embed",
    ]:
        assert soup.find(tag) is None, f"{tag} should be removed"

    # All attributes should be stripped
    for t in soup.find_all(True):
        assert not t.attrs, f"Attributes not stripped for <{t.name}>: {t.attrs}"

    # All text nodes should be removed (structure only)
    assert not soup.find_all(
        string=True
    ), "Text nodes should be removed in structure-only clean"

    # But structural tags like div/header/nav/main/section remain
    for tag in ["html", "head", "body", "div", "header", "nav", "main", "section"]:
        assert soup.find(tag) is not None, f"<{tag}> structure should remain"


def test_clean_html_removes_blacklist_and_comments_and_returns_body_only():
    out = clean_html(SAMPLE_HTML)

    # Should return only a <body>...</body> snippet
    assert out.startswith("<body") and out.endswith(
        "</body>"
    ), "clean_html should return soup.body as string"

    # No blacklisted tags or comments should remain
    assert "<script" not in out and "<style" not in out and "<iframe" not in out
    assert "<!--" not in out and "-->" not in out

    # Visible text that was inside non-blacklisted tags should remain
    assert "Visible text" in out and "here" in out


def test_convert_relative_paths_to_absolute_for_assets_and_links():
    html = """
    <html><head>
      <link rel="stylesheet" href="styles.css" />
      <script src="/js/app.js"></script>
    </head>
    <body>
      <img src="images/logo.png"/>
      <a id="leading" href="/docs">Docs</a>
      <a id="relative" href="page.html">RelativePage</a>
      <a id="absolute" href="https://example.org/x">Abs</a>
    </body></html>
    """
    base = "https://example.com/base/"

    out = convert_relative_paths_to_absolute(html, base)
    soup = _parse(out)

    # link href is always absolutized
    assert soup.find("link")["href"] == "https://example.com/base/styles.css"

    # script src is always absolutized
    assert soup.find("script")["src"] == "https://example.com/js/app.js"

    # img src is always absolutized
    assert soup.find("img")["src"] == "https://example.com/base/images/logo.png"

    # <a href> starting with '/' is absolutized by implementation
    assert soup.find("a", id="leading")["href"] == "https://example.com/docs"

    # relative anchor without leading slash remains unchanged by current logic
    assert soup.find("a", id="relative")["href"] == "page.html"

    # absolute anchor remains unchanged
    assert soup.find("a", id="absolute")["href"] == "https://example.org/x"
