import pytest

from bs4 import BeautifulSoup  # only to sanity-check when needed

from talk2dom.api.utils.validator import SelectorValidator


HTML = (
    """
    <html><head><title>T</title></head>
    <body>
      <div id="wrapper">
        <button id="login" class="btn primary" name="login-btn">Log in</button>
        <input type="text" name="email" />
        <a id="home" href="/home">Home</a>
        <span class="tag">x</span>
      </div>
    </body></html>
    """
).strip()


def make_validator(html: str = HTML) -> SelectorValidator:
    return SelectorValidator(html)


# -----------------------------
# ID
# -----------------------------
@pytest.mark.parametrize(
    "type_, selector, expected",
    [
        ("ID", "login", True),  # case-insensitive type
        ("id", "missing", False),  # not found
    ],
)
def test_verify_id(type_, selector, expected):
    v = make_validator()
    assert v.verify(type_, selector) is expected


# -----------------------------
# CLASS NAME
# -----------------------------
@pytest.mark.parametrize(
    "selector, expected",
    [
        ("btn", True),
        ("primary", True),
        ("does-not-exist", False),
    ],
)
def test_verify_class_name(selector, expected):
    v = make_validator()
    assert v.verify("Class Name", selector) is expected


# -----------------------------
# NAME
# -----------------------------
@pytest.mark.parametrize(
    "selector, expected",
    [
        ("email", True),
        ("login-btn", True),
        ("not-a-name", False),
    ],
)
def test_verify_name(selector, expected):
    v = make_validator()
    assert v.verify("name", selector) is expected


# -----------------------------
# TAG NAME
# -----------------------------
@pytest.mark.parametrize(
    "selector, expected",
    [
        ("button", True),
        ("input", True),
        ("unknown", False),
    ],
)
def test_verify_tag_name(selector, expected):
    v = make_validator()
    assert v.verify("tag name", selector) is expected


# -----------------------------
# CSS SELECTOR
# -----------------------------
@pytest.mark.parametrize(
    "selector, expected",
    [
        ("div#wrapper .btn.primary", True),  # valid, found
        ("div .nope", False),  # valid, not found
        ("div[", False),  # INVALID CSS -> should be caught and return False
    ],
)
def test_verify_css_selector(selector, expected):
    v = make_validator()
    assert v.verify("css selector", selector) is expected


# -----------------------------
# XPATH
# -----------------------------
@pytest.mark.parametrize(
    "selector, expected",
    [
        ("//div[@id='wrapper']", True),  # valid, found
        ("//div[@id='missing']", False),  # valid, not found
        ("//div[@id='wrapper'", False),  # INVALID XPath -> caught and False
    ],
)
def test_verify_xpath(selector, expected):
    v = make_validator()
    assert v.verify("xpath", selector) is expected


# -----------------------------
# Unsupported type -> returns False (exception handled inside)
# -----------------------------
@pytest.mark.parametrize("type_", ["link text", "partial link text", "aria role"])
def test_verify_unsupported_type_returns_false(type_):
    v = make_validator()
    assert v.verify(type_, "anything") is False
