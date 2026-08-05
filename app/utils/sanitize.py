import re

import bleach
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "sub", "sup",
    "ul", "ol", "li", "blockquote", "pre", "code",
    "h2", "h3", "h4",
    "a", "img", "span", "div",
}
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
    "*": ["style"],
}
ALLOWED_STYLES = [
    "font-size", "font-family", "color", "background-color",
    "text-align", "font-weight", "font-style", "text-decoration",
]
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]
ANCHOR_RE = re.compile(r"<a\b[^>]*>")
_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)


def sanitize_html(value):
    """净化用户富文本：剥离脚本与事件属性，仅保留安全标签、属性与样式。"""
    if not value:
        return ""
    cleaned = bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
    )
    return ANCHOR_RE.sub(_harden_anchor, cleaned)


def _harden_anchor(match):
    tag = match.group(0)
    if "target=" not in tag:
        tag = tag[:-1] + ' target="_blank" rel="noopener noreferrer">'
    elif "rel=" not in tag:
        tag = tag.replace('target="_blank"', 'target="_blank" rel="noopener noreferrer"')
    return tag
