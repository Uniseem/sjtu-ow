"""The two data migrations of round 195 (design 5.4, details 2.3, v6.73),
run on real rows: a face still waiting for review goes up; the 内容审核
workflow comes off the news section, its review in progress is cancelled,
and 投稿者 may publish."""

from io import BytesIO

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from PIL import Image as PILImage

BEFORE = [
    ("accounts", "0008_user_accepts_announcements"),
    ("content", "0007_markdown_body"),
]
AFTER = [("accounts", "0009_faces_go_live"), ("content", "0008_publish_without_review")]


def _migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)


@pytest.mark.django_db(transaction=True)
def test_waiting_faces_go_up_and_reviews_end(settings, tmp_path):
    from wagtail.models import (
        GroupApprovalTask,
        GroupPagePermission,
        Workflow,
        WorkflowPage,
        WorkflowState,
        WorkflowTask,
    )

    from accounts.images import create_face_image
    from accounts.models import AvatarSubmission
    from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
    from members.tests.test_members import person

    settings.MEDIA_ROOT = tmp_path
    call_command("init_site", verbosity=0)
    news = ArticleIndexPage.objects.get(slug="news")
    member = person("迁移头像")
    buffer = BytesIO()
    PILImage.new("RGB", (300, 300), (20, 30, 40)).save(buffer, "PNG")
    image = create_face_image(
        SimpleUploadedFile("f.png", buffer.getvalue(), content_type="image/png"),
        user=member,
    )
    waiting = AvatarSubmission.objects.create(user=member, image=image)  # pending

    submitters = Group.objects.get(name="投稿者")
    GroupPagePermission.objects.filter(
        group=submitters, page=news, permission__codename="publish_page"
    ).delete()
    workflow = Workflow.objects.create(name="内容审核", active=True)
    task = GroupApprovalTask.objects.create(name="内容编辑审核", active=True)
    WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
    WorkflowPage.objects.create(page=news, workflow=workflow)
    page = ArticlePage(
        title="审核中195",
        slug="in-review-195",
        category=ArticleCategory.objects.get(slug="guide"),
        author=member,
        owner=member,
        body="正文",
    )
    news.add_child(instance=page)
    page.save_revision(user=member)
    workflow.start(page, member)
    try:
        _migrate(BEFORE)
        _migrate(AFTER)
    finally:
        call_command("migrate", verbosity=0)

    waiting.refresh_from_db()
    member.refresh_from_db()
    assert waiting.status == AvatarSubmission.Status.APPROVED
    assert member.avatar_id == image.pk
    assert not WorkflowPage.objects.filter(page=news).exists()
    assert not WorkflowState.objects.filter(status="in_progress").exists()
    assert not Workflow.objects.get(pk=workflow.pk).active
    assert not GroupApprovalTask.objects.get(pk=task.pk).active
    assert GroupPagePermission.objects.filter(
        group=submitters, page=news, permission__codename="publish_page"
    ).exists()
