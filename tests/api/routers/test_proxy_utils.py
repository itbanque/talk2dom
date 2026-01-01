import pytest

from talk2dom.api.routers import proxy


def test_strip_security_headers_removes_and_sets_cors():
    headers = {
        "x-frame-options": "deny",
        "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
    }
    proxy._strip_security_headers(headers)
    assert "x-frame-options" not in headers
    assert "frame-ancestors" not in headers["content-security-policy"]
    assert headers["access-control-allow-origin"] == "*"


def test_rewrite_css_skips_data_urls():
    css = "body{background:url(data:image/png;base64,xxx);}" \
          ".a{background:url('/img/a.png');}"
    out = proxy._rewrite_css(css, "https://example.com/app/")
    assert "data:image/png" in out
    assert "/api/v1/proxy/start?url=" in out


def test_rewrite_links_updates_assets_and_meta_refresh():
    html = """
    <html><head>
      <meta http-equiv="refresh" content="0;url=/next">
      <style>.a{background:url('/img/a.png');}</style>
    </head>
    <body>
      <a href="/home">Home</a>
      <img src="/img.png" />
    </body></html>
    """
    out = proxy._rewrite_links(html, "https://example.com/base/")
    assert "/api/v1/proxy/start?url=" in out
    assert "refresh" in out


def test_ensure_allowed_blocks_disallowed(monkeypatch):
    monkeypatch.setattr(proxy, "ALLOWED_HOSTS", {"example.com"})
    with pytest.raises(Exception):
        proxy._ensure_allowed("https://other.com")
