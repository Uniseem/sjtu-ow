"""Members publish their own articles (design 5.4, v6.73): the 内容审核
workflow comes off the article sections and is switched off (kept on
record), reviews in progress are cancelled so the drafts go back to their
authors, and 投稿者 gets 发布 on the sections. content.services
retire_content_workflow and assign_content_permissions do the same for
init_site."""

from django.db import migrations

WORKFLOW = "内容审核"
TASK = "内容编辑审核"
SUBMITTERS = "投稿者"


def forwards(apps, schema_editor):
    ArticleIndexPage = apps.get_model("content", "ArticleIndexPage")
    WorkflowPage = apps.get_model("wagtailcore", "WorkflowPage")
    WorkflowState = apps.get_model("wagtailcore", "WorkflowState")
    TaskState = apps.get_model("wagtailcore", "TaskState")
    Workflow = apps.get_model("wagtailcore", "Workflow")
    Task = apps.get_model("wagtailcore", "Task")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    GroupPagePermission = apps.get_model("wagtailcore", "GroupPagePermission")

    sections = list(ArticleIndexPage.objects.values_list("pk", flat=True))
    WorkflowPage.objects.filter(page_id__in=sections).delete()
    states = WorkflowState.objects.filter(status="in_progress", workflow__name=WORKFLOW)
    TaskState.objects.filter(workflow_state__in=states, status="in_progress").update(
        status="cancelled"
    )
    states.update(status="cancelled")
    Workflow.objects.filter(name=WORKFLOW).update(active=False)
    Task.objects.filter(name=TASK).update(active=False)

    group = Group.objects.filter(name=SUBMITTERS).first()
    publish = Permission.objects.filter(
        content_type__app_label="wagtailcore", codename="publish_page"
    ).first()
    if group is not None and publish is not None:
        for page_id in sections:
            GroupPagePermission.objects.get_or_create(
                group=group, page_id=page_id, permission=publish
            )


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0007_markdown_body"),
        ("wagtailcore", "0098_apitoken"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
