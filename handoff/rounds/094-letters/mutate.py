"""Round 094: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/094-letters/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_letters.py"

MUTATIONS = [
    ("another closing", "core/letters.py",
     'CLOSING = "祝好！"', 'CLOSING = "此致"',
     [f"{T}::test_every_email_reads_as_a_letter[entered]"]),
    ("nobody greeted by name", "core/letters.py",
     '    return f"{name}，你好：" if name else "你好："',
     '    return "你好："',
     [f"{T}::test_someone_we_do_not_know_is_greeted_without_a_name"]),
    ("a bare address stays nameless", "core/letters.py",
     '            User.objects.filter(email__in=bare).values_list("email", "nickname")',
     '            User.objects.none().values_list("email", "nickname")',
     [f"{T}::test_send_writes_one_letter_per_person_each_by_name"]),
    ("a subject without its team", "teams/notifications.py",
     '        subject=f"新的入队申请：{team.name}",',
     '        subject="新的入队申请",',
     [f"{T}::test_each_subject_says_what_and_about_what[apply]"]),
    ("a subject without its tournament", "tournaments/notifications_registration.py",
     '        subject=f"你已被报名参加：{title}",',
     '        subject="你已被报名参加赛事",',
     [f"{T}::test_each_subject_says_what_and_about_what[entered]"]),
    ("the text forgets why", "core/letters.py",
     '    parts.append(f"——\\n{letter.reason}{NO_REPLY}\\n{site_url(\'/\')}")',
     '    parts.append(f"——\\n{NO_REPLY}\\n{site_url(\'/\')}")',
     [f"{T}::test_every_email_reads_as_a_letter[entered]"]),
    ("the HTML forgets why", "templates/email/letter.html",
     "{% block reason %}{{ letter.reason }}{% endblock %}",
     "{% block reason %}{% endblock %}",
     [f"{T}::test_every_html_is_the_same_letter_in_the_frame[entered]"]),
    ("no date under the signature", "core/letters.py",
     '        "date": dated(),', '        "date": "",',
     [f"{T}::test_every_html_is_the_same_letter_in_the_frame[entered]"]),
    ("dark mode may invert it", "templates/email/layout.html",
     '<meta name="color-scheme" content="light">\n', "",
     [f"{T}::test_every_html_is_the_same_letter_in_the_frame[verify]"]),
    ("details before the facts", "templates/email/letter.html",
     '<p style="margin:0 0 16px;">{{ letter.lead }}</p>\n',
     '<p style="margin:0 0 16px;">{{ letter.lead }}</p>\n'
     '{% for paragraph in letter.paragraphs %}<p>{{ paragraph }}</p>{% endfor %}\n',
     [f"{T}::test_the_facts_come_before_the_details_and_the_button_after"]),
    ("a small code", "templates/email/parts/code.html",
     "font-size:32px;", "font-size:15px;",
     [f"{T}::test_a_code_is_shown_large_on_its_own"]),
    ("the reset code comes nameless", "accounts/adapter.py",
     "            user = User.objects.filter(email__iexact=email).first()\n",
     "            user = None\n",
     [f"{T}::test_a_password_reset_code_arrives_as_a_letter"]),
    ("the reset code in plain paragraphs", "templates/account/email/password_reset_code_message.html",
     '{% include "email/parts/code.html" %}', "<p>{{ code }}</p>",
     [f"{T}::test_a_password_reset_code_arrives_as_a_letter"]),
    ("Wagtail greets in its own words", "templates/wagtailadmin/notifications/base.txt",
     "{{ user.nickname|default:user.get_username }}，你好：",
     "Hello {{ user.get_username }},",
     [f"{T}::test_wagtail_notifications_greet_and_close_like_ours"]),
    ("text-only mail says goodbye twice", "core/letters.py",
     '    body, _rule, foot = text.strip().partition("\\n——\\n")',
     '    body, _rule, foot = text.strip(), "", ""',
     [f"{T}::test_text_only_mail_is_framed_once_with_its_own_footer"]),
    ("anyone sees the specimens", "core/styleguide.py",
     '    _admins_only(request)\n    return render(request, "core/styleguide_emails.html"',
     '    return render(request, "core/styleguide_emails.html"',
     [f"{T}::test_the_email_specimens_are_for_admins_only"]),
    ("the specimen under the site's policy", "core/styleguide.py",
     "    response._csp_config = EMAIL_CSP\n", "",
     [f"{T}::test_an_admin_sees_every_email"]),
    ("every template may style inline", "core/tests/test_templates.py",
     '    relative = path.relative_to(settings.BASE_DIR).as_posix()\n    return relative.startswith("templates/email/") or (',
     '    relative = path.relative_to(settings.BASE_DIR).as_posix()\n    return True or relative.startswith("templates/email/") or (',
     ["core/tests/test_templates.py::test_only_emails_may_style_inline"]),
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
            for cache in ROOT.glob(rel.rsplit("/", 1)[0] + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
