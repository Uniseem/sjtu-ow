"""Round 197: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/197-ai-settings/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

A = "moderation/tests/test_ai_settings.py::"
PROVIDER = A + "test_the_provider_comes_from_the_settings_row"
ENOUGH = A + "test_a_key_or_an_address_is_enough_and_nothing_else_is_read"
EXTRA = A + "test_the_extra_body_is_an_object_without_the_request_s_own_keys"
GONE = A + "test_the_environment_variables_are_gone"
KEPT = A + "test_the_key_is_saved_encrypted_never_shown_and_kept_when_blank"
BAD_EXTRA = A + "test_a_bad_extra_body_is_refused_on_the_field"
FALLBACK = A + "test_wagtails_own_settings_page_keeps_the_key_too"
TRY = A + "test_the_ai_is_tried_from_the_settings_page_and_comes_back"
SENT = A + "test_without_a_key_the_owner_is_sent_to_the_settings"
MIGRATION = A + "test_the_migration_carries_the_old_environment_in"
CHECKLIST = (
    "core/tests/test_setup_checklist.py::"
    "test_ai_says_whether_the_key_or_the_switch_is_missing"
)

MUTATIONS = [
    ("a self-hosted address alone is not enough", "moderation/services.py",
     "    return bool(site.moderation_api_key or site.moderation_base_url)",
     "    return bool(site.moderation_api_key)", [ENOUGH]),
    ("the provider without the saved key", "moderation/providers.py",
     "        api_key=site.moderation_api_key,", '        api_key="",', [PROVIDER]),
    ("the extra body not sent", "moderation/providers.py",
     "        payload.update(self.extra_body)\n", "", [PROVIDER]),
    ("the output limit ignored", "moderation/providers.py",
     '            "max_tokens": self.max_output_tokens,',
     '            "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,', [PROVIDER]),
    ("the timeout ignored", "moderation/providers.py",
     "        timeout=site.moderation_timeout or DEFAULT_TIMEOUT,",
     "        timeout=DEFAULT_TIMEOUT,", [PROVIDER]),
    ("forbidden keys allowed", "moderation/services.py",
     'EXTRA_BODY_FORBIDDEN = ("messages", "tools", "tool_choice")',
     "EXTRA_BODY_FORBIDDEN = ()", [EXTRA, BAD_EXTRA]),
    ("a list taken as the extra body", "moderation/services.py",
     "    if not isinstance(value, dict):", "    if False:", [EXTRA, BAD_EXTRA]),
    ("a blank key box clears the key", "backoffice/forms.py",
     '        return kept_secret(self, "moderation_api_key")',
     '        return self.cleaned_data.get("moderation_api_key")', [KEPT]),
    ("the secrets drawn as plain fields", "backoffice/forms.py",
     "        for name, (label, help_text) in SECRET_FIELDS.items():",
     "        for name, (label, help_text) in []:", [KEPT]),
    ("the extra body unchecked on the page", "backoffice/forms.py",
     "        return cleaned_extra_body(self)",
     '        return self.cleaned_data.get("moderation_extra_body")', [BAD_EXTRA]),
    ("wagtail's form clears the key", "core/forms.py",
     '        return kept_secret(self, "moderation_api_key")',
     '        return self.cleaned_data.get("moderation_api_key")', [FALLBACK]),
    ("the old variable read again", "sjtu_ow/settings/base.py",
     "# AI review's key, address and request options live in",
     'MODERATION_API_KEY = ""\n# AI review\'s key, address and request options live in',
     [GONE]),
    ("the migration forgets the key", "core/migrations/0021_ai_settings_in_admin.py",
     '            row.moderation_api_key = env["MODERATION_API_KEY"]\n', "",
     [MIGRATION]),
    ("the migration forgets the numbers", "core/migrations/0021_ai_settings_in_admin.py",
     "                setattr(row, field, int(value))\n", "", [MIGRATION]),
    ("trying the AI never comes back", "moderation/admin_views.py",
     "        return redirect(back)", '        return redirect("moderation_index")',
     [TRY]),
    ("trying the AI goes anywhere", "moderation/admin_views.py",
     "    if back and url_has_allowed_host_and_scheme(\n        back, allowed_hosts={request.get_host()}, require_https=request.is_secure()\n    ):",
     "    if back:", [TRY]),
    ("the owner told to edit .env", "moderation/services.py",
     "            \"在「设置 → 全站设置 → AI 审核」里填好、保存，下一次巡查就会用上。\"",
     "            \"写进 .env 后重启 web 和 worker。\"", [SENT]),
    ("the checklist points at the review list", "core/admin_setup.py",
     "        detail,\n        _settings_url(site),\n        required=False,\n    )\n\n\ndef _legal",
     "        detail,\n        reverse(\"moderation_index\"),\n        required=False,\n    )\n\n\ndef _legal",
     [CHECKLIST]),
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
