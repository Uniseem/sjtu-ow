"""The section tabs at the top of every admin page (design 14.1, v6.71).

``{% section_tabs %}…{% endsection_tabs %}`` wraps Wagtail's page furniture
in templates/wagtailadmin/base.html and puts the strip first inside its
content column. The furniture draws the sidebar first, and with it the menu
hook that works out this person's sections, so they are ready by then.
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Where the content column opens in Wagtail's wagtailadmin/base.html.
MARKER = '<div class="content">'


class SectionTabsNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        html = self.nodelist.render(context)
        request = context.get("request")
        if request is None or MARKER not in html:
            return html
        from core.admin_sections import tab_strip

        return mark_safe(html.replace(MARKER, MARKER + tab_strip(request), 1))


@register.tag
def section_tabs(parser, token):
    nodelist = parser.parse(("endsection_tabs",))
    parser.delete_first_token()
    return SectionTabsNode(nodelist)
