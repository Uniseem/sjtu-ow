"""Form controls of the back office (docs/admin.md 4.2, 5)."""

from __future__ import annotations

from django import forms
from django.db.models import Q
from django.urls import reverse


class DateTimeLocal(forms.DateTimeInput):
    """The browser's own date and time picker, in Shanghai time."""

    input_type = "datetime-local"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%dT%H:%M")


class DateLocal(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


def thumbnail(image, spec: str = "max-320x200") -> str:
    """A small rendition's address, or "" when the file is gone."""
    if image is None:
        return ""
    try:
        return image.get_rendition(spec).url
    except Exception:  # noqa: BLE001 — a missing file must not break a form
        return ""


class ImagePicker(forms.Widget):
    """「选择」「清除」 and the picture chosen (b-picker). The dialog with the
    pictures this person may choose is filled by static/js/backoffice.js
    from ``backoffice:image_chooser``."""

    template_name = "backoffice/widgets/image_picker.html"

    def __init__(self, attrs=None, label=""):
        super().__init__(attrs)
        # The field's own <label> points at a hidden input, which nothing
        # reads out; the buttons carry the field's name instead (216, F7: a
        # page of pictures was N times 「选择, 按钮」).
        self.label = str(label or "")

    def get_context(self, name, value, attrs):
        from wagtail.images import get_image_model

        context = super().get_context(name, value, attrs)
        image = None
        if value not in (None, ""):
            image = get_image_model().objects.filter(pk=value).first()
        context["widget"].update(
            {
                "image": image,
                "thumb": thumbnail(image),
                "chooser_url": reverse("backoffice:image_chooser"),
                "label": self.label,
            }
        )
        return context

    def value_from_datadict(self, data, files, name):
        return data.get(name) or None


def image_field(user, *, label, required=False, help_text="", current=None):
    """A picture field limited to the pictures this person may choose, plus
    the one already there (someone else may have picked it)."""
    from wagtail.images import get_image_model

    from backoffice.access import image_policy

    Image = get_image_model()
    if user is not None and user.is_superuser:
        queryset = Image.objects.all()
    elif user is not None:
        queryset = image_policy().instances_user_has_any_permission_for(
            user, ["choose"]
        )
        if current:
            queryset = Image.objects.filter(
                Q(pk__in=queryset.values("pk")) | Q(pk=current)
            )
    else:
        queryset = Image.objects.none()
    return forms.ModelChoiceField(
        queryset=queryset,
        required=required,
        label=label,
        help_text=help_text,
        widget=ImagePicker(label=label),
    )
