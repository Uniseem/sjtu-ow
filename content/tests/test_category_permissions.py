"""Round 068: 内容编辑 manage article categories (design 4.1, 14.1).

The design said so from the start; init_site never granted the snippet's
model permissions, so only superusers could touch categories. Since v7.0 the
page is the back office's 「内容 → 分类」.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse

from members.tests.test_members import _staff


@pytest.fixture
def category_list():
    return reverse("backoffice:categories")


@pytest.mark.django_db
def test_content_editors_manage_article_categories(client, category_list):
    call_command("init_site", verbosity=0)
    client.force_login(_staff("内容编辑"))

    assert client.get(category_list).status_code == 200
    add = reverse("backoffice:category_new")
    assert client.get(add).status_code == 200
    response = client.post(
        add, {"name": "新分类", "slug": "new-068", "sort_order": "5"}
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_other_admins_do_not_manage_article_categories(client, category_list):
    call_command("init_site", verbosity=0)
    client.force_login(_staff("赛事管理员"))

    assert client.get(category_list).status_code == 403
    assert client.get(reverse("backoffice:category_new")).status_code == 403
