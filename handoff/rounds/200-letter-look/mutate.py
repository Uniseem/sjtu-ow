"""Round 200: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/200-letter-look/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

L = "core/tests/test_letter_look.py::"
HEAD = L + "test_the_head_is_sjtu_red_with_the_site_mark_and_ridges"
FLAT = L + "test_nothing_is_outlined_and_the_button_is_a_red_pill"
ADDRESS = L + "test_the_address_under_the_button_reads_as_written"
ESCAPES = L + "test_only_escaped_text_is_turned_back"
INSIDE = L + "test_a_letter_carries_its_pictures_inside"
QUEUED = L + "test_queued_mail_gets_its_pictures_on_the_way_out"
TEXT_ONLY = L + "test_text_only_mail_gets_the_same_head"
FILES = L + "test_the_committed_pictures_match_what_the_code_draws"
RIDGES = L + "test_the_ridges_sit_on_red_and_run_into_the_white_card"
MARK = L + "test_the_mark_is_the_site_icon_the_other_way_round"
BROWSER = L + "test_the_specimen_page_points_the_pictures_at_static"
FRAME = "core/tests/test_letters.py::test_every_html_is_the_same_letter_in_the_frame"
SPECIMEN = "core/tests/test_letters.py::test_an_admin_sees_every_email"

MUTATIONS = [
    ("the pictures left out of the message", "core/mail.py",
     "            for cid, data in used(html.get_content()):",
     "            for cid, data in []:", [INSIDE, QUEUED]),
    ("the pictures as attachments", "core/mail.py",
     'cid=f"<{cid}>", disposition="inline"', 'cid=f"<{cid}>", disposition="attachment"',
     [INSIDE]),
    ("queued mail built without its pictures", "core/mail.py",
     "    multipart = LetterMessage(\n        subject=message.subject,",
     "    multipart = EmailMultiAlternatives(\n        subject=message.subject,",
     [QUEUED, TEXT_ONLY]),
    ("a letter built without its pictures", "core/letters.py",
     "    from core.mail import LetterMessage\n",
     "    from django.core.mail import EmailMultiAlternatives as LetterMessage\n",
     [INSIDE]),
    ("every escape turned back", "core/templatetags/ow.py",
     '_ESCAPED_TEXT = re.compile(r"(?:%[89A-Fa-f][0-9A-Fa-f])+")',
     '_ESCAPED_TEXT = re.compile(r"(?:%[0-9A-Fa-f]{2})+")', [ESCAPES]),
    ("the address left in percent signs", "templates/email/parts/button.html",
     "{{ url|readable_url }}", "{{ url }}", [ADDRESS]),
    ("the address box does not select whole", "templates/email/parts/button.html",
     "-webkit-user-select:all;user-select:all;", "", [ADDRESS]),
    ("the night head back", "templates/email/layout.html",
     'data-letter-head bgcolor="#9b3a33" style="background-color:#9b3a33;',
     'data-letter-head bgcolor="#141a24" style="background-color:#141a24;', [HEAD]),
    ("the ridges from elsewhere", "templates/email/layout.html",
     '<img src="cid:ow-horizon"', '<img src="https://example.com/horizon.png"',
     [HEAD, FRAME]),
    ("the card outlined again", "templates/email/layout.html",
     'data-letter-card style="background-color:#ffffff;border-radius:0 0 16px 16px;',
     'data-letter-card style="background-color:#ffffff;border:1px solid #e1e4e8;border-radius:0 0 16px 16px;',
     [FLAT]),
    ("a square button", "templates/email/parts/button.html",
     'style="background-color:#9b3a33;border-radius:999px;">',
     'style="background-color:#9b3a33;border-radius:6px;">', [FLAT]),
    ("the facts cut by lines", "templates/email/parts/facts.html",
     '{% if not forloop.first %}border-top:2px solid #ffffff;{% endif %}">{{ label }}',
     '{% if not forloop.first %}border-top:1px solid #e1e4e8;{% endif %}">{{ label }}',
     [FLAT]),
    ("the committed ridges out of date", "core/email_art.py",
     "FAR = (205, 157, 153, 255)", "FAR = (205, 157, 154, 255)", [FILES]),
    ("one ridge only", "core/email_art.py",
     "    pen.polygon(_ridge(2026, 0.42, 0.26, big), fill=FAR)\n", "", [RIDGES, FILES]),
    ("the mark not turned round", "core/email_art.py",
     "    return icons.draw(MARK, fill=WHITE, ink=PRIMARY)",
     "    return icons.draw(MARK)", [MARK, FILES]),
    ("the specimen page with cid: pictures", "core/styleguide.py",
     "    response = HttpResponse(for_browser(found.html))",
     "    response = HttpResponse(found.html)", [SPECIMEN]),
    ("the browser pointed nowhere", "core/email_art.py",
     '            static(f"{DIRECTORY}/{ART[match.group(1)]}")\n            if match',
     "            match.group(0)\n            if match", [BROWSER, SPECIMEN]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
    ).returncode


def _text(rel):
    return (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def check():
    bad = [
        (label, _text(rel).count(old))
        for label, rel, old, _new, _tests in MUTATIONS
        if _text(rel).count(old) != 1
    ]
    print("mutations:", len(MUTATIONS), "not applying:", bad or "none")
    return not bad


def main():
    if not check():
        sys.exit(1)
    if "--check" in sys.argv:
        return
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
            text = raw.replace("\r\n", "\n").replace(old, new)
            path.write_bytes(
                (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
            )
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/**/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")


if __name__ == "__main__":
    main()
