from django.utils.text import slugify

from .models import Business


def unique_slug(name):
    """A slug for a new business's booking page address, based on its name."""
    base = slugify(name)[:50].strip("-") or "business"
    slug = base
    suffix = 2
    while Business.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
