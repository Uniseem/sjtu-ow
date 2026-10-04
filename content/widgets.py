"""The Markdown editor for bodies and descriptions (design 5.2, v6.70).

EasyMDE (static/vendor/easymde/) on a plain textarea: the textarea keeps the
Markdown and is what the form posts, so without the script it is still an
ordinary text box.
"""

from __future__ import annotations

from django import forms
from django.conf import settings
from django.urls import reverse


class MarkdownEditor(forms.Textarea):
    template_name = "content/widgets/markdown_editor.html"

    def __init__(self, attrs=None):
        super().__init__(attrs={"rows": 18, **(attrs or {})})

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"].update(
            {
                "data-markdown-editor": "",
                "data-preview-url": reverse("content_markdown_preview"),
                "data-upload-url": reverse("content_markdown_image"),
                "data-max-size": str(settings.WAGTAILIMAGES_MAX_UPLOAD_SIZE),
            }
        )
        return context

    @property
    def media(self):
        return forms.Media(
            css={"all": ["vendor/easymde/easymde.min.css"]},
            js=["vendor/easymde/easymde.min.js", "js/markdown-editor.js"],
        )
