"""Panels in the article editor (round 124)."""

from __future__ import annotations

from wagtail.admin.panels import Panel, TitleFieldPanel


class SubmissionGuidePanel(Panel):
    """「投稿须知」 at the top of the editor, for people whose articles are
    reviewed before they go out (content.permissions.submits_for_review).
    The Wagtail editor is a lot for a first-time writer: where the body is,
    how to add pictures, which button submits, what the other tabs are."""

    class BoundPanel(Panel.BoundPanel):
        template_name = "content/admin/submission_guide.html"

        def is_shown(self):
            from content.permissions import submits_for_review

            return submits_for_review(self.request.user)


class TitlePanel(TitleFieldPanel):
    """Wagtail's title panel, minus the slug syncing when there is no slug
    field to sync (round 169). Submitters' forms have no slug (round 130);
    Wagtail then still attaches its w-sync controller with an empty selector,
    and every submitter's editor logged 「Error connecting controller」."""

    class BoundPanel(TitleFieldPanel.BoundPanel):
        def get_attrs(self):
            attrs = super().get_attrs()
            if attrs.get("data-w-sync-target-value"):
                return attrs
            widget = self.bound_field.field.widget
            attrs.pop("data-w-sync-target-value", None)
            for name in ("data-controller", "data-action"):
                kept = [
                    word
                    for word in attrs.get(name, "").split()
                    if word != "w-sync" and "w-sync#" not in word
                ]
                if kept:
                    attrs[name] = " ".join(kept)
                else:
                    attrs.pop(name, None)
                    widget.attrs.pop(name, None)
            return attrs
