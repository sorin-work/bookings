from django.utils.text import slugify


def unique_slug(name):
    """A slug for a new business's booking page address, based on its name."""
    base = slugify(name)[:50].strip("-") or "business"
    return base
