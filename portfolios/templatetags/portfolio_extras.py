import bleach
import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "code",
    "pre",
    "a",
]


ALLOWED_ATTRIBUTES = {
    "a": [
        "href",
        "title",
    ],
}


ALLOWED_PROTOCOLS = [
    "http",
    "https",
    "mailto",
]


@register.filter
def render_markdown(value):
    if not value:
        return ""

    rendered_html = markdown.markdown(
        value,
        extensions=[
            "sane_lists",
            "nl2br",
        ],
        output_format="html5",
    )

    safe_html = bleach.clean(
        rendered_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )

    return mark_safe(safe_html)