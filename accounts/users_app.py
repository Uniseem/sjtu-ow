"""wagtail.users with the site's user screens (accounts.admin_users; design
14.2, round 115). Its own module: INSTALLED_APPS loads it before the apps are
ready, so it cannot import the forms and views it points at."""

from wagtail.users.apps import WagtailUsersAppConfig


class SiteUsersAppConfig(WagtailUsersAppConfig):
    user_viewset = "accounts.admin_users.SiteUserViewSet"
