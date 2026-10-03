"""The AI's read of an article on its edit page (design 5.5.1, round 119).

A submission goes to a content editor for review anyway; the AI's verdict
is shown at the top of the editor as a reference. Only people who may
review content see it, so a submitter never reads the AI's notes on their
own piece.
"""

from __future__ import annotations

from wagtail.admin.panels import Panel


def latest_verdict(page):
    """The newest review record for this page's text, or None."""
    from moderation.integrations import page_target_type
    from moderation.models import ModerationItem

    target_type = page_target_type(page)
    if not target_type or not page.pk:
        return None
    return (
        ModerationItem.objects.filter(target_type=target_type, target_id=page.pk)
        .order_by("-created_at", "-pk")
        .first()
    )


class ModerationVerdictPanel(Panel):
    class BoundPanel(Panel.BoundPanel):
        template_name = "moderation/verdict_panel.html"

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            from moderation.admin_views import can_review

            self.verdict = None
            if self.instance is not None and can_review(self.request.user):
                self.verdict = latest_verdict(self.instance)

        def is_shown(self):
            return self.verdict is not None

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)
            context["verdict"] = self.verdict
            return context
