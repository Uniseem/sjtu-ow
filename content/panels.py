"""Panels in the article editor (round 124)."""

from __future__ import annotations

from wagtail.admin.panels import Panel


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
