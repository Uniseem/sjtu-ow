"""212, F2: what the autosave script does when a save fails.

These are substring guards over ``static/js/autosave.js`` — they pin the
rules below but cannot catch logic errors in them (210 review, F8; the
real behaviour guard would be a browser run, which CI does not do).
"""

from pathlib import Path

from django.conf import settings


def _source() -> str:
    return (Path(settings.BASE_DIR) / "static/js/autosave.js").read_text(
        encoding="utf-8"
    )


def test_a_gone_session_or_missing_permission_stops_retrying():
    source = _source()
    # 401/403/404 are permanent, and a 200 that is not JSON is the login
    # page the session-less request was redirected to.
    assert "response.status === 401" in source
    assert "response.status === 403" in source
    assert "response.status === 404" in source
    assert "refused.permanent = true" in source
    assert "failed.permanent = response.ok" in source
    # Said so, and no retry is scheduled on that path.
    assert "重新登录后再改" in source
    permanent = source.split("error.permanent", 1)[1]
    assert "setTimeout" not in permanent.split("fileChosen", 1)[0]


def test_retriable_failures_back_off_instead_of_hammering():
    source = _source()
    assert "RETRY_MAX = 60000" in source
    assert "Math.min(RETRY * Math.pow(2, self.failures - 1), RETRY_MAX)" in source
    assert "self.failures = 0" in source  # reset once a save lands


def test_a_form_holding_a_chosen_file_does_not_auto_retry():
    source = _source()
    assert "fileChosen(self.form)" in source
    assert "再改一次会重新尝试" in source
    assert "fileChosen" in source  # the helper itself


def test_a_permanent_failure_does_not_block_leaving_the_page():
    source = _source()
    # pending() feeds beforeunload; a save that can never land must not
    # trap the editor on the page.
    assert "this.failed && !this.gaveUp" in source
