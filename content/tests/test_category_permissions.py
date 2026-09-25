"""Round 068: 内容编辑 manage article categories (design 4.1, 14.1).

The design said so from the start; init_site never granted the snippet's
model permissions, so only superusers could touch categories.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse

from members.tests.test_members import _staff


@pytest.fixture
def category_list():
    return reverse("wagtailsnippets_content_articlecategory:list")


@pytest.mark.django_db
def test_content_editors_manage_article_categories(client, category_list):
    call_command("init_site", verbosity=0)
    client.force_login(_staff("内容编辑"))

    assert client.get(category_list).status_code == 200
    add = reverse("wagtailsnippets_content_articlecategory:add")
    assert client.get(add).status_code == 200


@pytest.mark.django_db
def test_other_admins_do_not_manage_article_categories(client, category_list):
    call_command("init_site", verbosity=0)
    client.force_login(_staff("赛事管理员"))

    response = client.get(category_list)

    assert response.status_code == 302
    assert response.url == reverse("wagtailadmin_home")
