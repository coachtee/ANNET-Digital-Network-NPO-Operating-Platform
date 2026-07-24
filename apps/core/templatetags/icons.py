from functools import lru_cache

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()

_ICONS_DIR = settings.BASE_DIR / "static" / "icons"


@lru_cache(maxsize=None)
def _load_icon(name):
    path = _ICONS_DIR / f"{name}.svg"
    return path.read_text()


@register.simple_tag
def icon(name, css_class=""):
    """Inline an SVG from static/icons/<name>.svg so it inherits `color`
    via `stroke="currentColor"` — a plain <img> can't do that. Icons are a
    hand-built Lucide-style set (24x24, 2px stroke, round caps/joins), not
    the Lucide package itself (this environment can't fetch external
    packages), matching its visual language.

    Always carries the base "icon" class, which CSS sizes to 1.15em by
    default — the source SVGs have no width/height attributes (only a
    viewBox), so an unstyled <svg> falls back to the browser's 300x150
    replaced-element default and renders enormous. Callers that need a
    specific pixel size (e.g. inside a .stat-icon circle) pass css_class
    and rely on a more specific selector to override the default.
    """
    svg = _load_icon(name)
    classes = ("icon " + css_class).strip()
    svg = svg.replace("<svg ", f'<svg class="{classes}" ', 1)
    return mark_safe(svg)
