import base64
import re
from urllib.parse import urlparse

import httpx
from lxml import etree

_BLOCKED_TAGS = {
    "script", "style", "iframe", "object", "embed",
    "foreignObject", "use",
}
_ON_ATTR = re.compile(r"^on[a-z]", re.IGNORECASE)


def sanitize_svg(raw: str) -> str:
    """Strip dangerous elements and attributes; return clean SVG or empty string."""
    if not raw.strip():
        return ""
    try:
        root = etree.fromstring(raw.encode("utf-8"))
    except etree.XMLSyntaxError:
        return ""

    to_remove = []
    for elem in root.iter():
        if not isinstance(elem.tag, str):
            continue
        local = etree.QName(elem.tag).localname
        if local in _BLOCKED_TAGS:
            to_remove.append(elem)

    for elem in to_remove:
        parent = elem.getparent()
        if parent is not None:
            parent.remove(elem)

    for elem in root.iter():
        if not isinstance(elem.tag, str):
            continue
        for attr in list(elem.attrib):
            local = etree.QName(attr).localname if "}" in attr else attr
            value = elem.attrib[attr]
            if _ON_ATTR.match(local) or "javascript:" in value.lower():
                del elem.attrib[attr]

    return etree.tostring(root, encoding="unicode", xml_declaration=False)


async def iconify_search(q: str, limit: int = 24) -> list[str]:
    """Search Iconify; return list of icon names like 'mdi:home'."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.iconify.design/search",
            params={"query": q, "limit": limit},
        )
        r.raise_for_status()
    return r.json().get("icons", [])


async def fetch_icon_svg(ref: str) -> str:
    """Fetch an Iconify SVG by 'prefix:name', sanitize, and return SVG string."""
    if ":" not in ref:
        return ""
    prefix, name = ref.split(":", 1)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"https://api.iconify.design/{prefix}/{name}.svg",
            params={"color": "currentColor"},
        )
        if r.status_code != 200:
            return ""
    return sanitize_svg(r.text)


async def resolve_favicon(url: str) -> str:
    """Fetch a site favicon; return sanitized SVG or SVG-wrapped data URI."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        for path in ("/favicon.svg", "/favicon.ico", "/favicon.png"):
            try:
                r = await client.get(base + path)
                if r.status_code != 200 or not r.content:
                    continue
                ct = r.headers.get("content-type", "")
                if "svg" in ct or path.endswith(".svg"):
                    return sanitize_svg(r.text)
                # Raster — wrap in an SVG <image> with data URI
                mime = ct.split(";")[0].strip() or "image/x-icon"
                b64 = base64.b64encode(r.content).decode()
                data_uri = f"data:{mime};base64,{b64}"
                return (
                    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
                    f'<image href="{data_uri}" width="16" height="16"/>'
                    f'</svg>'
                )
            except Exception:
                continue
    return ""
