"""Round 117: tidy what Wagtail's own migrations leave in the admin.

- The stock 「Moderators approval」 workflow sits on the root page, and its
  only task asks the stock Moderators group that init_site deletes, so a page
  outside the article sections submitted for moderation waited for nobody.
  Switched off when its tasks have no approvers left (a fresh install still
  has the group at this point; init_site retires it after deleting the group,
  ``content.services.retire_wagtail_stock_workflow``).
- The root page and the root collection were called 「Root」 in an otherwise
  Chinese admin (breadcrumbs, the collection picker).
"""

from django.db import migrations

STOCK = "Moderators approval"
ROOT_TITLE = "根目录"


def forwards(apps, schema_editor):
    Workflow = apps.get_model("wagtailcore", "Workflow")
    WorkflowTask = apps.get_model("wagtailcore", "WorkflowTask")
    WorkflowPage = apps.get_model("wagtailcore", "WorkflowPage")
    WorkflowContentType = apps.get_model("wagtailcore", "WorkflowContentType")
    WorkflowState = apps.get_model("wagtailcore", "WorkflowState")
    TaskState = apps.get_model("wagtailcore", "TaskState")
    Task = apps.get_model("wagtailcore", "Task")
    GroupApprovalTask = apps.get_model("wagtailcore", "GroupApprovalTask")
    Page = apps.get_model("wagtailcore", "Page")
    Collection = apps.get_model("wagtailcore", "Collection")

    for workflow in Workflow.objects.filter(name=STOCK, active=True):
        task_ids = list(
            WorkflowTask.objects.filter(workflow=workflow).values_list(
                "task_id", flat=True
            )
        )
        if GroupApprovalTask.objects.filter(
            pk__in=task_ids, groups__isnull=False
        ).exists():
            continue
        states = WorkflowState.objects.filter(workflow=workflow, status="in_progress")
        TaskState.objects.filter(
            workflow_state__in=states, status="in_progress"
        ).update(status="cancelled")
        states.update(status="cancelled")
        WorkflowPage.objects.filter(workflow=workflow).delete()
        WorkflowContentType.objects.filter(workflow=workflow).delete()
        workflow.active = False
        workflow.save(update_fields=["active"])
        Task.objects.filter(pk__in=task_ids, name=STOCK).update(active=False)

    Page.objects.filter(depth=1, title="Root").update(
        title=ROOT_TITLE, draft_title=ROOT_TITLE
    )
    Collection.objects.filter(depth=1, name="Root").update(name=ROOT_TITLE)


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0005_delete_homepagecarouselitem"),
        ("wagtailcore", "0098_apitoken"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
