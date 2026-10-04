"""The page tree's filter, kept for Wagtail's own admin under /wagtail/
(docs/admin.md 2.1): nobody but superusers and content editors sees other
people's unpublished pages there either. The back office has its own list
(backoffice.views.articles)."""

from django.db.models import Q
from wagtail import hooks
from wagtail.permission_policies.pages import PagePermissionPolicy

from content.permissions import sees_only_own_drafts


@hooks.register("construct_explorer_page_queryset")
def filter_submitter_explorer(parent_page, pages, request):
    if not sees_only_own_drafts(request.user):
        return pages
    return pages.filter(Q(live=True) | Q(owner=request.user))


_original_explorable_instances = PagePermissionPolicy.explorable_instances


def _explorable_instances_for_submitters(self, user):
    pages = _original_explorable_instances(self, user)
    if sees_only_own_drafts(user):
        return pages.filter(Q(live=True) | Q(owner=user))
    return pages


PagePermissionPolicy.explorable_instances = _explorable_instances_for_submitters
