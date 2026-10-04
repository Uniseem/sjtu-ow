from django import template

register = template.Library()


@register.filter
def parent_crumb(crumbs):
    """The page above this one in a breadcrumb list (首页 … parent, here), for
    the head's 返回 link; None when the page sits right under the home."""
    crumbs = list(crumbs or [])
    if len(crumbs) < 3:
        return None
    parent = crumbs[-2]
    return parent if parent.get("url") else None


@register.filter
def in_list(value, names):
    return value in (names or ())
