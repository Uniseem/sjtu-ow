"""Wagtail's image upload form, with every new file sent through
``core.uploads.clean_image`` (219).

Wagtail's form is what the back office upload, the Markdown editor's picture
button and ``/wagtail/images/`` all use, so the one base class set in
``WAGTAILIMAGES_IMAGE_FORM_BASE`` covers all three."""

from django import forms
from django.core.files.uploadedfile import UploadedFile
from wagtail.images.forms import BaseImageForm

from core.uploads import TOO_MANY, UploadError, clean_image, over_daily_limit


class SafeImageForm(BaseImageForm):
    def __init__(self, *args, **kwargs):
        # The parent takes ``user`` out and keeps only what it chooses from it.
        self.uploader = kwargs.get("user")
        super().__init__(*args, **kwargs)

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        # Editing a picture without choosing a new file hands back the stored
        # one, which was cleaned when it came in.
        if not isinstance(uploaded, UploadedFile):
            return uploaded
        try:
            cleaned = clean_image(uploaded)
        except UploadError as error:
            raise forms.ValidationError(str(error)) from error
        if self.uploader is not None and over_daily_limit(self.uploader):
            raise forms.ValidationError(TOO_MANY)
        return cleaned
