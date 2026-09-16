"""Admin forms for the font library and typography settings (design 13.12)."""

from __future__ import annotations

from django import forms

from core.fonts import processing
from core.fonts.services import MAX_ENABLED_VARIANTS
from core.models import FontFace, FontFamily, TypographyRule

WEIGHT_CHOICES = FontFace.WEIGHT_CHOICES
AUTO_CHOICE = [("", "自动识别")]
GOOGLE_WEIGHTS = [(weight, label) for weight, label in WEIGHT_CHOICES]

LICENSE_CONFIRM_LABEL = "确认这个字体允许嵌入网站使用"


class LicenseFieldsMixin(forms.Form):
    license_type = forms.ChoiceField(
        label="授权类型",
        choices=FontFamily.License.choices,
    )
    license_note = forms.CharField(
        label="授权说明",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="比如购买凭证编号、开源协议名称。",
    )
    license_confirmed = forms.BooleanField(label=LICENSE_CONFIRM_LABEL)


class FontFileFieldsMixin(forms.Form):
    """Validates an uploaded font file and keeps the parsed result."""

    weight = forms.ChoiceField(
        label="字重",
        choices=AUTO_CHOICE + WEIGHT_CHOICES,
        required=False,
    )
    style = forms.ChoiceField(
        label="样式",
        choices=AUTO_CHOICE + list(FontFace.Style.choices),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_data = None

    def _validate_font_bytes(self, data: bytes) -> bytes:
        try:
            processing.inspect_font(data)
        except processing.FontError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return data


class FontUploadForm(FontFileFieldsMixin, LicenseFieldsMixin, forms.Form):
    field_order = [
        "name",
        "file",
        "weight",
        "style",
        "license_type",
        "license_note",
        "license_confirmed",
    ]

    name = forms.CharField(label="字体名称", max_length=64)
    file = forms.FileField(
        label="字体文件",
        help_text="支持 TTF、OTF、WOFF、WOFF2，单个文件不超过 30MB。",
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > processing.MAX_FONT_BYTES:
            raise forms.ValidationError(
                f"文件 {uploaded.size / 1024 / 1024:.1f}MB，超过 30MB 上限。"
            )
        data = uploaded.read()
        self.font_data = self._validate_font_bytes(data)
        return uploaded


class FontUrlForm(FontFileFieldsMixin, LicenseFieldsMixin, forms.Form):
    field_order = [
        "name",
        "url",
        "weight",
        "style",
        "license_type",
        "license_note",
        "license_confirmed",
    ]

    name = forms.CharField(label="字体名称", max_length=64)
    url = forms.URLField(
        label="字体文件地址",
        assume_scheme="https",
        help_text="必须是 https 直链，比如开源字体在 GitHub 上的发布地址。",
    )


class GoogleFontForm(forms.Form):
    family_name = forms.CharField(
        label="Google Fonts 字体名称",
        max_length=64,
        help_text="填写 Google Fonts 上的名称，比如 Noto Serif SC。",
    )
    name = forms.CharField(
        label="站内显示名称",
        max_length=64,
        required=False,
        help_text="留空则使用上面的名称。",
    )
    weights = forms.MultipleChoiceField(
        label="需要的字重",
        choices=GOOGLE_WEIGHTS,
        widget=forms.CheckboxSelectMultiple,
        initial=[400, 700],
    )
    license_confirmed = forms.BooleanField(label=LICENSE_CONFIRM_LABEL)


class FontFaceAddForm(FontFileFieldsMixin, forms.Form):
    """Add another weight to an existing font."""

    field_order = ["file", "url", "weight", "style"]

    file = forms.FileField(label="字体文件", required=False)
    url = forms.URLField(label="或填写下载地址", required=False, assume_scheme="https")

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        if not uploaded:
            return uploaded
        if uploaded.size > processing.MAX_FONT_BYTES:
            raise forms.ValidationError(
                f"文件 {uploaded.size / 1024 / 1024:.1f}MB，超过 30MB 上限。"
            )
        self.font_data = self._validate_font_bytes(uploaded.read())
        return uploaded

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("file") and not cleaned.get("url"):
            raise forms.ValidationError("请上传字体文件或填写下载地址。")
        return cleaned


class TypographyRuleForm(forms.ModelForm):
    class Meta:
        model = TypographyRule
        fields = [
            "mode",
            "family",
            "weight",
            "size_rem",
            "line_height",
            "letter_spacing_em",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["family"].queryset = FontFamily.objects.filter(
            faces__status=FontFace.Status.READY
        ).distinct()
        self.fields["family"].required = False
        self.fields["family"].empty_label = "（未选择）"
        if self.instance.region == TypographyRule.Region.BODY:
            self.fields["mode"].choices = [
                choice
                for choice in TypographyRule.Mode.choices
                if choice[0] != TypographyRule.Mode.INHERIT
            ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("mode") != TypographyRule.Mode.CUSTOM:
            cleaned["family"] = None
        return cleaned


TypographyFormSet = forms.modelformset_factory(
    TypographyRule,
    form=TypographyRuleForm,
    extra=0,
    can_delete=False,
)


def synthetic_weight_warnings(rules) -> list[str]:
    """Warn when a "跟随正文" region asks for a weight the body font lacks.

    The browser would fake it (synthetic bold), so the admin should either add
    that weight to the font or pick one that exists.
    """
    rules = list(rules)
    body = next(
        (rule for rule in rules if rule.region == TypographyRule.Region.BODY), None
    )
    if body is None or body.mode != TypographyRule.Mode.CUSTOM or not body.family_id:
        return []
    available = set(
        FontFace.objects.filter(
            family_id=body.family_id,
            style=FontFace.Style.NORMAL,
            status=FontFace.Status.READY,
        ).values_list("weight", flat=True)
    )
    messages = []
    for rule in rules:
        if rule.mode != TypographyRule.Mode.INHERIT:
            continue
        if rule.weight not in available:
            messages.append(
                f"「{rule.get_region_display()}」要用 {rule.weight} 字重，"
                f"但正文字体「{body.family.name}」只有 "
                f"{'、'.join(str(weight) for weight in sorted(available))} 字重，"
                "浏览器会用假粗体显示。建议补上这个字重，或把该区域改成已有字重。"
            )
    return messages


def variant_warning(rules) -> str:
    """Design 13.12.5: warn when more than six font/weight pairs are enabled."""
    from core.fonts.services import enabled_variants

    variants = enabled_variants(list(rules))
    if len(variants) > MAX_ENABLED_VARIANTS:
        return (
            f"当前启用了 {len(variants)} 组「字体 × 字重」，"
            f"超过建议的 {MAX_ENABLED_VARIANTS} 组，页面加载会变慢。"
        )
    return ""
