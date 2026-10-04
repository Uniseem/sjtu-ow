"""The back office's top bar and tabs, for its own pages only."""

from backoffice.nav import Navigation


def navigation(request):
    place = getattr(request, "backoffice_place", None)
    if place is None:
        return {}
    return {"bo": Navigation(request.user, place)}
