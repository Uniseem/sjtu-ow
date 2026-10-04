from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "全站"

    def ready(self):
        from django.urls import register_converter

        from core.converters import IdConverter

        # Before any URLconf is read: every id in an address is <id:…> (166).
        register_converter(IdConverter, "id")

        from core.forms import SiteSettingsAdminForm
        from core.models import SiteSettings
        from core.slots import register, template_slot

        SiteSettings.base_form_class = SiteSettingsAdminForm

        import core.signals  # noqa: F401

        register("account", template_slot("slots/account.html"))
        register("messages", template_slot("slots/messages.html"))
        register("footer-account", template_slot("slots/footer_account.html"))
        # Design 5.2 (v6.48): 「我的安排」 on the homepage.
        from core.agenda import my_agenda_slot

        register("my-agenda", my_agenda_slot)
