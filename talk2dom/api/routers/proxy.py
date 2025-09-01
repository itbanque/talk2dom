import re
from typing import Optional
from urllib.parse import urlparse, urljoin, urlencode
from talk2dom.db.models import User
from talk2dom.api.deps import (
    get_current_user,
)

import httpx
from bs4 import BeautifulSoup
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, HTTPException, Query, Depends

router = APIRouter()

ALLOWED_HOSTS: set[str] = set()  # e.g. {"example.com", "news.ycombinator.com"}

FORWARDED_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _strip_security_headers(headers: dict) -> None:
    for h in [
        "x-frame-options",
        "frame-options",
        "content-security-policy-report-only",
        "cross-origin-opener-policy",
        "cross-origin-opener-policy-report-only",
        "cross-origin-embedder-policy",
        "cross-origin-embedder-policy-report-only",
        "permissions-policy",
    ]:
        if h in headers:
            del headers[h]

    # Override CSP: remove frame-ancestors directive, keep other directives to avoid breaking site scripts
    if "content-security-policy" in headers:
        csp = headers["content-security-policy"]
        directives = [d.strip() for d in csp.split(";") if d.strip()]
        directives = [
            d for d in directives if not d.lower().startswith("frame-ancestors")
        ]
        if directives:
            headers["content-security-policy"] = "; ".join(directives)
        else:
            del headers["content-security-policy"]

    headers.setdefault("access-control-allow-origin", "*")


def _rewrite_css(
    css_text: str, base_url: str, proxy_prefix: str = "/api/v1/proxy/start"
) -> str:
    """Rewrite url(...) inside CSS to route through the proxy. Skips data:, javascript:, mailto:."""

    def repl(m):
        raw = m.group(1).strip().strip("'\"")
        if not raw or raw.startswith(("data:", "javascript:", "mailto:")):
            return m.group(0)
        abs_url = urljoin(base_url, raw)
        proxied = f"{proxy_prefix}?{urlencode({'url': abs_url})}"
        return f"url('{proxied}')"

    return re.sub(r"url\(([^)]+)\)", repl, css_text, flags=re.IGNORECASE)


def _rewrite_links(
    html: str, base_url: str, proxy_prefix: str = "/api/v1/proxy/start"
) -> str:
    """
    Rewrite href/src links in the page to go through this proxy:
      <a href="foo"> -> <a href="/proxy?url=<absolute(foo)>">
    Only effective for text/html.
    """
    soup = BeautifulSoup(html, "html.parser")

    def to_proxy(u: Optional[str]) -> Optional[str]:
        if (
            not u
            or u.startswith("data:")
            or u.startswith("javascript:")
            or u.startswith("mailto:")
        ):
            return u
        abs_url = urljoin(base_url, u)
        return f"{proxy_prefix}?{urlencode({'url': abs_url})}"

    for tag, attr in [
        ("a", "href"),
        ("link", "href"),
        ("script", "src"),
        ("img", "src"),
        ("iframe", "src"),
        ("source", "src"),
        ("video", "src"),
        ("audio", "src"),
        ("form", "action"),
    ]:
        for el in soup.find_all(tag):
            if el.has_attr(attr):
                el[attr] = to_proxy(el[attr])

    # Also rewrite inline <style> content
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            style_tag.string = _rewrite_css(style_tag.string, base_url, proxy_prefix)

    # Rewrite <meta http-equiv="refresh" content="0;url=...">
    for meta_refresh in soup.find_all(
        "meta", attrs={"http-equiv": re.compile("^refresh$", re.I)}
    ):
        content_val = meta_refresh.get("content")
        if content_val and "url=" in content_val.lower():
            # split on ';' and find url= part
            parts = [p.strip() for p in content_val.split(";") if p.strip()]
            new_parts = []
            for p in parts:
                if p.lower().startswith("url="):
                    raw = p[4:].strip().strip("'\"")
                    proxied = to_proxy(raw)
                    new_parts.append(f"url={proxied}")
                else:
                    new_parts.append(p)
            meta_refresh["content"] = "; ".join(new_parts)

    # Remove possible <meta http-equiv="Content-Security-Policy" ...>
    for meta in soup.find_all(
        "meta", attrs={"http-equiv": re.compile("^Content-Security-Policy$", re.I)}
    ):
        meta.decompose()

    return str(soup)


def _ensure_allowed(url: str):
    if not ALLOWED_HOSTS:
        return
    host = urlparse(url).netloc.split(":")[0].lower()
    if host not in ALLOWED_HOSTS:
        raise HTTPException(
            status_code=403, detail=f"Host '{host}' is not allowed by this proxy"
        )


@router.api_route(
    "/start", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
)
async def proxy(
    request: Request,
    url: str = Query(
        ..., description="The absolute URL to proxy, e.g. https://example.com"
    ),
    rewrite: bool = Query(
        True, description="Whether to rewrite links in the page to continue proxying"
    ),
    user: User = Depends(get_current_user),
):
    """
    A general proxy endpoint supporting all HTTP methods. Specify the upstream URL via the query parameter `url`.
    - For text/html: remove headers blocking embedding and inline meta CSP, and optionally rewrite links.
    - For other Content-Types: pass through bytes directly.
    """
    parsed = urlparse(url)
    if not (parsed.scheme in {"http", "https"} and parsed.netloc):
        raise HTTPException(status_code=400, detail="Invalid URL")

    _ensure_allowed(url)

    # Build absolute proxy prefix (scheme + host + path) for rewriting
    try:
        proxy_prefix_abs = str(
            request.url_for("proxy")
        )  # e.g., http://localhost:8000/api/v1/proxy/start
    except Exception:
        proxy_prefix_abs = "/api/v1/proxy/start"

    # Forward common request headers
    fwd_headers = {
        "User-Agent": request.headers.get("user-agent", FORWARDED_UA) or FORWARDED_UA,
        "Accept": request.headers.get("accept", "*/*"),
        "Accept-Language": request.headers.get("accept-language", "en-US,en;q=0.9"),
        "Referer": request.headers.get("referer", ""),
        # If needed, also forward original request Cookie
        **(
            {"Cookie": request.headers["cookie"]} if "cookie" in request.headers else {}
        ),
    }

    # Read request body (useful for POST/PUT/PATCH)
    body = await request.body()

    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=timeout, http2=True
    ) as client:
        try:
            upstream = await client.request(
                method=request.method,
                url=url,
                headers=fwd_headers,
                content=body if body else None,
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502, detail=f"Upstream request failed: {e}"
            ) from e

    # Copy upstream response headers and remove headers that affect our response
    resp_headers = dict(upstream.headers)
    for h in ["transfer-encoding", "content-length", "connection", "content-encoding"]:
        if h in resp_headers:
            del resp_headers[h]

    _strip_security_headers(resp_headers)

    # If upstream is a redirect, rewrite Location to keep navigation inside the proxy
    if "location" in resp_headers:
        try:
            target = resp_headers["location"]
            abs_loc = urljoin(url, target)
            resp_headers["location"] = (
                f"{proxy_prefix_abs}?{urlencode({'url': abs_loc})}"
            )
        except Exception:
            # leave as-is on any parsing error
            pass

    content_type = upstream.headers.get("content-type", "")

    # CSS: rewrite url(...) and return as text/css
    if content_type.startswith("text/css"):
        css = upstream.text
        css = _rewrite_css(css, base_url=url, proxy_prefix=proxy_prefix_abs)
        return Response(
            content=css, headers=resp_headers, media_type="text/css; charset=utf-8"
        )

    # HTML: do inline processing and rewriting
    if content_type.startswith("text/html"):
        html = upstream.text

        # Remove inline <meta http-equiv="Content-Security-Policy">
        html = re.sub(
            r'<meta[^>]+http-equiv=["\']Content-Security-Policy["\'][^>]*>',
            "",
            html,
            flags=re.IGNORECASE,
        )
        # Try to remove frame-ancestors from meta content (conservative handling)
        html = re.sub(
            r"(frame-ancestors\s+[^;>]+;?)",
            "",
            html,
            flags=re.IGNORECASE,
        )

        if rewrite:
            html = _rewrite_links(html, base_url=url, proxy_prefix=proxy_prefix_abs)

        return Response(
            content=html, headers=resp_headers, media_type="text/html; charset=utf-8"
        )

    # Non-HTML: passthrough bytes as-is (images/videos/fonts/JSON etc.)
    return StreamingResponse(
        iter([upstream.content]),
        headers=resp_headers,
        media_type=content_type or "application/octet-stream",
    )
