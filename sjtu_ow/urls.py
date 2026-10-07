from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from accounts.views import login_door

urlpatterns = [
    # Wagtail's two login pages skip allauth's limit and email check (218,
    # 217 review 04-1). They are declared first so they win.
    path("wagtail/login/", login_door),
    path("_util/login/", login_door),
    # The back office (docs/admin.md, v7.0); Wagtail's own admin is the
    # superusers' fallback underneath it.
    path("admin/", include("backoffice.urls")),
    path("wagtail/", include(wagtailadmin_urls)),
    path("accounts/", include("allauth.urls")),
    path("documents/", include(wagtaildocs_urls)),
    path("", include("accounts.urls")),
    path("", include("core.urls")),
    path("", include("content.urls")),
    path("", include("teams.urls")),
    path("", include("members.urls")),
    path("", include("tournaments.urls")),
    path("", include("scrims.urls")),
    path("", include("search.urls")),
    path("", include("comments.urls")),
    path("", include(wagtail_urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "core.views.permission_denied"
handler404 = "core.views.page_not_found"
handler500 = "core.views.server_error"
