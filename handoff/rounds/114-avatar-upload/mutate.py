"""Round 114: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/114-avatar-upload/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_avatar_upload.py"
IMG = "accounts/images.py"
SVC = "accounts/services.py"
ADMIN = "moderation/avatar_admin.py"
NOTE = "accounts/notifications.py"


def t(name):
    return f"{T}::{name}"


MUTATIONS = [
    ("the photo is not turned upright", IMG,
     "    picture = ImageOps.exif_transpose(picture)\n", "",
     [t("test_the_camera_data_is_gone_and_the_picture_stands_up")]),
    ("the camera data is kept", IMG,
     '    picture.save(out, "WEBP", quality=88, method=6)\n',
     '    picture.save(out, "WEBP", quality=88, method=6, exif=picture.info.get("exif", b""))\n',
     [t("test_the_camera_data_is_gone_and_the_picture_stands_up")]),
    ("the picture is not squared", IMG,
     "    picture = picture.crop((left, top, left + side, top + side))\n", "",
     [t("test_a_small_picture_keeps_its_size_but_is_square")]),
    ("big pictures are not shrunk", IMG,
     "    if side > AVATAR_SIDE:\n", "    if False:\n",
     [t("test_a_photo_becomes_a_square_webp_of_at_most_512")]),
    ("faces are stored as PNG", IMG,
     '    picture.save(out, "WEBP", quality=88, method=6)\n',
     '    picture.save(out, "PNG")\n',
     [t("test_a_photo_becomes_a_square_webp_of_at_most_512")]),
    ("tiny pictures pass", IMG,
     "        if min(width, height) < AVATAR_MIN_SIDE:\n", "        if False:\n",
     [t("test_pictures_we_cannot_use_are_refused")]),
    ("huge pictures pass", IMG,
     "        if width * height > AVATAR_MAX_PIXELS:\n", "        if False:\n",
     [t("test_a_huge_picture_is_refused_before_it_is_decoded")]),
    ("any format passes", IMG,
     "        if picture.format not in AVATAR_FORMATS:\n", "        if False:\n",
     [t("test_pictures_we_cannot_use_are_refused")]),
    ("big files pass the form", "accounts/forms.py",
     "        if uploaded.size > AVATAR_MAX_BYTES:\n", "        if False:\n",
     [t("test_the_form_refuses_big_files_and_other_types")]),
    ("other types pass the form", "accounts/forms.py",
     "        if not name.endswith(AVATAR_EXTENSIONS) or (\n            content_type and content_type not in AVATAR_TYPES\n        ):\n",
     "        if False:\n",
     [t("test_the_form_refuses_big_files_and_other_types")]),
    ("an upload shows at once", SVC,
     "        submission = AvatarSubmission.objects.create(user=user, image=image)\n",
     "        submission = AvatarSubmission.objects.create(user=user, image=image)\n        _set_face(user, image.pk)\n",
     [t("test_an_upload_waits_for_review_and_changes_nothing_in_public")]),
    ("the earlier upload keeps its picture", SVC,
     "        _delete_images(old.image_id for old in earlier)\n", "",
     [t("test_a_new_upload_replaces_the_one_waiting")]),
    ("barred members still upload", SVC,
     "    if not can_use(user, Feature.AVATAR_UPLOAD):\n        raise AvatarUploadError(feature_denied_message())\n", "",
     [t("test_someone_barred_from_uploading_can_still_go_back_to_default")]),
    ("no daily limit", SVC,
     '    if over_limit(f"avatar-upload:{user.pk}", AVATAR_UPLOADS_PER_DAY, DAY_SECONDS):\n',
     "    if False:\n",
     [t("test_five_uploads_a_day")]),
    ("withdrawing keeps the picture", SVC,
     "        submission.status = AvatarSubmission.Status.WITHDRAWN\n        submission.save(update_fields=[\"status\"])\n        _delete_images([submission.image_id])\n",
     "        submission.status = AvatarSubmission.Status.WITHDRAWN\n        submission.save(update_fields=[\"status\"])\n",
     [t("test_withdrawing_deletes_the_picture")]),
    ("going back to default deletes scripted faces", SVC,
     "        owned = old in uploaded_face_ids(user)\n        _set_face(user, None)\n",
     "        owned = True\n        _set_face(user, None)\n",
     [t("test_a_face_put_there_by_script_is_not_deleted")]),
    ("approving does not put the face up", SVC,
     "        _set_face(user, submission.image_id)\n", "",
     [t("test_approving_puts_the_face_up_and_regenerates_its_pages")]),
    ("approving keeps the replaced upload", SVC,
     "        if old and owned:\n            _delete_images([old])\n    return submission\n",
     "    return submission\n",
     [t("test_approving_puts_the_face_up_and_regenerates_its_pages")]),
    ("approving deletes a scripted face", SVC,
     "        owned = old in uploaded_face_ids(user)\n        _decided(submission, AvatarSubmission.Status.APPROVED, reviewer)\n",
     "        owned = True\n        _decided(submission, AvatarSubmission.Status.APPROVED, reviewer)\n",
     [t("test_approving_keeps_a_scripted_face_it_replaces")]),
    ("a rejected picture stays", SVC,
     "        _decided(submission, AvatarSubmission.Status.REJECTED, reviewer, reason, note)\n        _delete_images([image_id])\n",
     "        _decided(submission, AvatarSubmission.Status.REJECTED, reviewer, reason, note)\n",
     [t("test_rejecting_deletes_the_picture_and_tells_the_person")]),
    ("nobody is told about a rejection", SVC,
     "        transaction.on_commit(lambda: avatar_rejected(submission))\n", "",
     [t("test_rejecting_deletes_the_picture_and_tells_the_person")]),
    ("a taken-down face stays up", SVC,
     "        _set_face(user, None)\n        _delete_images([image_id])\n        transaction.on_commit(lambda: avatar_taken_down(submission))\n",
     "        _delete_images([image_id])\n        transaction.on_commit(lambda: avatar_taken_down(submission))\n",
     [t("test_taking_down_a_face_in_use")]),
    ("no reason needed", SVC,
     "    if reason not in Category.values:\n", "    if False:\n",
     [t("test_a_decision_needs_a_reason_and_happens_once")]),
    ("a decision can happen twice", SVC,
     "    if submission is None or submission.status != status:\n",
     "    if submission is None:\n",
     [t("test_a_decision_needs_a_reason_and_happens_once")]),
    ("anyone in the admin opens the review page", ADMIN,
     "@reviewer_required\ndef avatar_review(request):\n", "def avatar_review(request):\n",
     [t("test_only_reviewers_open_the_review_page")]),
    ("anyone in the admin decides", ADMIN,
     "@reviewer_required\n@require_POST\ndef avatar_review_action(request, pk):\n",
     "@require_POST\ndef avatar_review_action(request, pk):\n",
     [t("test_only_reviewers_open_the_review_page")]),
    ("the page sends reviewers anywhere", ADMIN,
     "    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):\n",
     "    if not back:\n",
     [t("test_a_reviewer_approves_from_the_page")]),
    ("each picture fetches its thumbnail", ADMIN,
     '        .prefetch_related("image__renditions")\n', "",
     [t("test_the_review_page_costs_the_same_however_many_wait")]),
    ("each upload mails the reviewers", NOTE,
     "    if not cache.add(WAITING_KEY, 1, WAITING_DELAY_SECONDS * 2):\n", "    if False:\n",
     [t("test_reviewers_get_one_reminder_for_a_batch")]),
    ("one reminder silences the next", "accounts/tasks.py",
     "    cache.delete(WAITING_KEY)\n", "",
     [t("test_the_reminder_lets_the_next_upload_ask_again")]),
    ("deleting the account keeps the pictures", SVC,
     "        forget_uploaded_faces(user)  # design 3.8, v6.11\n", "",
     [t("test_deleting_the_account_deletes_every_uploaded_picture")]),
    ("the export leaves the uploads out", SVC,
     '        "avatar_uploads": [\n', '        "avatar_uploads_x": [\n',
     [t("test_the_export_lists_the_uploads")]),
    ("the waiting picture is not shown to its owner", "templates/me/profile.html",
     '        {% if avatar_pending and avatar_pending.image %}\n', '        {% if False %}\n',
     [t("test_an_upload_waits_for_review_and_changes_nothing_in_public")]),
    ("barred members see the file picker", "templates/me/profile.html",
     "      {% if avatar_can_upload %}\n", "      {% if True %}\n",
     [t("test_someone_barred_from_uploading_can_still_go_back_to_default")]),
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
