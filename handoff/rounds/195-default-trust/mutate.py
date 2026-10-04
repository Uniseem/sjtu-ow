"""Round 195: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/195-default-trust/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

A = "accounts/tests/test_avatar_upload.py::"
AT_ONCE = A + "test_an_upload_shows_at_once"
REPLACE = A + "test_a_new_upload_replaces_the_face_and_deletes_the_old_upload"
NEWEST = A + "test_the_page_lists_the_faces_in_use_newest_first"
S = "content/tests/test_submissions.py::"
PUBLISH = S + "test_members_publish_their_own_articles_straight_away"
OTHERS = S + "test_nobody_takes_down_someone_elses_article_but_editors"
RETIRE = S + "test_init_site_retires_the_review_workflow_left_from_before"
MIGRATE = "content/tests/test_trust_migrations.py::test_waiting_faces_go_up_and_reviews_end"
GUIDE = "accounts/tests/test_onboarding.py::test_submitters_get_the_guide_and_editors_do_not"

MUTATIONS = [
    ("uploads wait again", "accounts/services.py", "            status=AvatarSubmission.Status.APPROVED,\n", "", [AT_ONCE]),
    ("the face not put up", "accounts/services.py", "        _set_face(user, image.pk)\n", "", [AT_ONCE, REPLACE]),
    ("old uploads kept", "accounts/services.py", "        if old and owned:\n            _delete_images([old])\n    return submission", "    return submission", [REPLACE]),
    ("anyone takes down anyone's", "content/permissions.py", "            or self.page.owner_id == self.user.pk\n        )", "            or True\n        )", [OTHERS]),
    ("articles use Wagtail's own tester", "content/models.py", "        return OwnArticlesPermissionTester(user, self)", "        return super().permissions_for_user(user)", [OTHERS]),
    ("members may not publish", "content/services.py", '_grant_page_perms(groups[GROUP_SUBMITTER], index, ("add_page", "publish_page"))', '_grant_page_perms(groups[GROUP_SUBMITTER], index, ("add_page",))', [PUBLISH]),
    ("the workflow stays on the section", "content/services.py", "        bound.delete()\n", "        pass\n", [RETIRE]),
    ("reviews left running", "content/services.py", "        state.status = WorkflowState.STATUS_CANCELLED\n", "", [RETIRE]),
    ("init_site leaves the workflow", "core/management/commands/init_site.py", "        if retire_content_workflow():", "        if False:", [RETIRE]),
    ("oldest faces first", "moderation/avatar_admin.py", '.order_by("-created_at", "-pk")', '.order_by("created_at", "pk")', [NEWEST]),
    ("the guide still says review", "content/templates/content/admin/submission_guide.html", "点底部的「发布」就上线了", "点底部的「更多动作」，选「提交给内容审核」", [GUIDE]),
    ("the form still says review", "accounts/forms.py", "上传后马上换上。", "审核通过后才会换上。", [AT_ONCE]),
    ("migration keeps the workflow bound", "content/migrations/0008_publish_without_review.py", "    WorkflowPage.objects.filter(page_id__in=sections).delete()\n", "", [MIGRATE]),
    ("migration leaves reviews running", "content/migrations/0008_publish_without_review.py", '    states.update(status="cancelled")\n', "", [MIGRATE]),
    ("migration leaves waiting faces down", "accounts/migrations/0009_faces_go_live.py", "        user.avatar_id = submission.image_id\n", "", [MIGRATE]),
]
def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT, env=ENV, capture_output=True, text=True,
    ).returncode


def main():
    every = sorted({t for *_rest, tests in MUTATIONS for t in tests})
    assert run(every) == 0, "baseline is red"
    print("baseline green,", len(every), "tests")
    failed = []
    for label, rel, old, new, tests in MUTATIONS:
        path = ROOT / rel
        backup = path.with_suffix(path.suffix + ".mutbak")
        shutil.copy2(path, backup)
        try:
            raw = path.read_bytes().decode("utf-8")
            crlf = "\r\n" in raw
            text = raw.replace("\r\n", "\n")
            assert text.count(old) == 1, (label, text.count(old))
            text = text.replace(old, new)
            path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
