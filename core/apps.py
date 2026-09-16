from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "全站"

    def ready(self):
        from core.forms import SiteSettingsAdminForm
        from core.models import SiteSettings

        SiteSettings.base_form_class = SiteSettingsAdminForm
