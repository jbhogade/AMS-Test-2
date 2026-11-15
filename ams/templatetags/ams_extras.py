"""Template filters for badges, currency, display IDs."""

from django import template
from django.utils.safestring import mark_safe
from ..ids import print_asset_id, base_display_id

register = template.Library()


@register.filter
def inr(value):
    """Indian Rupee formatting, en-IN grouping (12,34,567.89)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-"
    s = f"{v:,.2f}"
    # convert 1,234,567.89 -> 12,34,567.89
    whole, _, frac = s.partition(".")
    digits = whole.replace(",", "")
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    out = f"{whole}.{frac}" if frac else whole
    return f"\u20b9{out}"


def _badge(text, cls):
    return mark_safe(f'<span class="badge {cls}">{text}</span>')


@register.filter
def asset_badge(status):
    colors = {
        "In Store": "badge-blue",
        "Assigned": "badge-green",
        "In Repair": "badge-amber",
        "Transfer": "badge-blue",
        "Not Working": "badge-red",
        "Retired / Scrapped": "badge-red",
        "Replaced": "badge-grey",
        "Issued": "badge-green",
        "Blocked": "badge-red",
        "Retired": "badge-grey",
        "Active": "badge-green",
        "Inactive": "badge-red",
        "Low Stock": "badge-red",
        "OK": "badge-green",
    }
    return _badge(status, colors.get(status, "badge-grey"))


@register.filter
def role_badge(role):
    if role in ("Supreme Root", "Super Root"):
        return _badge(role, "badge-red")
    if role == "Admin":
        return _badge(role, "badge-amber")
    return _badge(role, "badge-grey")


@register.filter
def pid(asset):
    """Full print/display ID for an asset or mobile."""
    return print_asset_id(asset)


@register.filter
def bid(asset):
    return base_display_id(asset)


@register.filter
def emp_id_label(emp):
    if not emp:
        return "-"
    return emp.emp_id or emp.ams_id


@register.filter
def dmy(d):
    if not d:
        return "-"
    return d.strftime("%d-%m-%Y")


@register.filter
def dmyhm(dt):
    if not dt:
        return "-"
    return dt.strftime("%d-%m-%Y %H:%M")


@register.filter
def get_item(dict_obj, key):
    if isinstance(dict_obj, dict):
        v = dict_obj.get(key, "")
        return "" if v is None else v
    return ""


@register.filter
def get_label(page_labels, key):
    """page_labels is the PAGE_REGISTRY dict key -> (label, section)."""
    if isinstance(page_labels, dict):
        item = page_labels.get(key)
        if item:
            return item[0] if isinstance(item, (tuple, list)) else item
    return key


@register.filter
def split(value, sep=","):
    return str(value).split(sep)
