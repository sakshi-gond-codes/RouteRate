from decimal import Decimal

from django import template
from django.utils.http import urlencode

register = template.Library()

CHANGE_BADGES = {
    "new": ("New", "bg-primary-subtle text-primary-emphasis"),
    "increase": ("Increase", "bg-danger-subtle text-danger-emphasis"),
    "decrease": ("Decrease", "bg-success-subtle text-success-emphasis"),
    "unchanged": ("Unchanged", "text-bg-light text-secondary border"),
    "removed": ("Removed", "bg-secondary-subtle text-secondary-emphasis"),
}

STATUS_BADGES = {
    "uploaded": "text-bg-light border text-secondary",
    "validated": "bg-warning-subtle text-warning-emphasis",
    "active": "bg-success-subtle text-success-emphasis",
    "discarded": "bg-secondary-subtle text-secondary-emphasis",
    "failed": "bg-danger-subtle text-danger-emphasis",
}


@register.filter
def rate(value, decimals=4):
    """Format a per-minute rate: 0.012345 -> 0.0123"""
    if value is None or value == "":
        return "—"
    try:
        return f"{Decimal(value):.{int(decimals)}f}"
    except Exception:
        return value


@register.filter
def pct(value, decimals=1):
    if value is None or value == "":
        return "—"
    return f"{float(value):.{int(decimals)}f}%"


@register.simple_tag
def change_badge(change):
    from django.utils.html import format_html

    label, css = CHANGE_BADGES.get(change or "", (change or "—", "text-bg-light border"))
    return format_html('<span class="badge rounded-pill {}">{}</span>', css, label)


@register.simple_tag
def status_badge(status, label=None):
    from django.utils.html import format_html

    css = STATUS_BADGES.get(status, "text-bg-light border")
    return format_html('<span class="badge rounded-pill {}">{}</span>', css, label or status.title())


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    """Keep current GET filters while changing one (used by pagination and export links)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    return "?" + urlencode(sorted(params.lists()), doseq=True) if params else "?"


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None
