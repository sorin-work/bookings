from django import template
from django.urls import reverse
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(takes_context=True)
def nav_link(context, url_name, label, exact=False):
    """A sidebar link that is marked as current for its own page and the pages below it."""
    url = reverse(url_name)
    request = context.get("request")
    path = request.path if request else ""
    current = path == url if exact else path.startswith(url)
    css = "nav-link is-current" if current else "nav-link"
    return format_html('<a class="{}" href="{}">{}</a>', css, url, label)
