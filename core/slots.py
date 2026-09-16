"""Registry of personalised page slots (design 13.13.3).

A slot name may carry an argument after a colon, e.g. ``team-join:88``. Apps
register their own slots in ``AppConfig.ready()`` so the fragment endpoint does
not need to know about them.
"""

from __future__ import annotations

from django.template.loader import render_to_string

REGISTRY: dict = {}
MAX_SLOTS = 12


def register(name: str, renderer) -> None:
    REGISTRY[name] = renderer


def template_slot(template: str, extra: dict | None = None):
    """Simplest renderer: one template, no argument."""

    def render(request, argument):
        context = {"oob": True}
        context.update(extra or {})
        return render_to_string(template, context, request=request)

    return render


def parse(raw: str) -> tuple[str, str]:
    name, _, argument = (raw or "").strip().partition(":")
    return name, argument


def render_requested(request, raw_names) -> str:
    """Render every known slot the page asked for; ignore the rest."""
    parts = []
    for raw in list(raw_names)[:MAX_SLOTS]:
        name, argument = parse(raw)
        renderer = REGISTRY.get(name)
        if renderer is None:
            continue
        html = renderer(request, argument)
        if html:
            parts.append(html)
    return "".join(parts)
