from django.shortcuts import render
from django.views.decorators.http import require_GET

from members.services import showcase


@require_GET
def members_index(request):
    """Public member showcase (design 6.3)."""
    return render(request, "members/index.html", showcase())
