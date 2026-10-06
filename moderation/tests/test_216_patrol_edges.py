"""Round 216: the edges of the AI patrol found in review (D5–D8).

D5: a verdict lands only on the text that was read. D6: a letter links only
the site's own addresses. D7: 附加请求参数 cannot carry the request's own
switches. D8: a reply cut off half way is a failed call, not an exception.
"""

import http.client
from unittest.mock import patch

import pytest
from django.core.cache import cache

from core.letters import _lines_html, wrap_text
from moderation import patrol, services
from moderation.models import ModerationItem, Risk, TargetType
from moderation.providers import (
    OpenAICompatibleProvider,
    ProviderResult,
    Verdict,
)
from moderation.tests.test_moderation import configure_ai


@pytest.fixture
def ai(db):
    site = configure_ai("test-key", "http://127.0.0.1:1/v1")
    site.moderation_enabled = True
    site.moderation_daily_limit = 2000
    site.save()
    cache.delete(patrol.PATROL_KEY)
    return site


def _good(count, risk=Risk.NONE, reason=""):
    return ProviderResult(
        verdicts=[Verdict(index=i, risk=risk, reason=reason) for i in range(count)],
        model="m",
        input_tokens=100,
        output_tokens=20,
    )


def _long(index, text):
    return services.submit(
        target_type=TargetType.ARTICLE, target_id=index, field="content", text=text
    )


def _record(item, risk=Risk.HIGH):
    return services.record(
        item,
        risk=risk,
        categories=["广告"],
        reason="旧文的结论",
        quote="旧",
        model="m",
    )


# --- D5: the verdict goes onto the words that were read ---------------------------


@pytest.mark.django_db
def test_216_d5_a_verdict_on_text_rewritten_meanwhile_is_not_written(ai):
    """216, D5: the row was rewritten with new text after the item was loaded;
    the verdict on the old words must not land on the new ones."""
    item = _long(1, "旧的正文")
    again = _long(1, "新的正文")
    assert again.pk == item.pk  # the same waiting row, rewritten

    assert _record(item) is False
    row = ModerationItem.objects.get(pk=item.pk)
    assert row.checked_at is None
    assert row.full_text == "新的正文"
    assert row.excerpt == "新的正文"
    assert row.risk == Risk.UNKNOWN and row.reason == ""


@pytest.mark.django_db
def test_216_d5_a_hash_changed_behind_the_item_is_not_written_either(ai):
    """216, D5: any rewrite of text_hash behind the loaded object (here by a
    plain queryset update) keeps the stale verdict off the row."""
    item = _long(2, "正文甲")
    ModerationItem.objects.filter(pk=item.pk).update(
        text_hash=services.text_hash("正文乙"), full_text="正文乙"
    )
    assert _record(item) is False
    row = ModerationItem.objects.get(pk=item.pk)
    assert row.checked_at is None and row.full_text == "正文乙"


@pytest.mark.django_db
def test_216_d5_an_unchanged_item_is_written(ai):
    """216, D5: the guard does not stop the ordinary case."""
    item = _long(3, "没改过的正文")
    assert _record(item) is True
    row = ModerationItem.objects.get(pk=item.pk)
    assert row.checked_at is not None
    assert row.risk == Risk.HIGH and row.reason == "旧文的结论"
    assert row.full_text == ""


@pytest.mark.django_db
def test_216_d5_publishing_again_during_a_long_review_leaves_the_new_text_waiting(
    ai,
):
    """216, D5 end to end: while the patrol reads a long piece, its author
    saves new text at the same place. The old verdict is dropped and the new
    text waits, whole, for the next patrol."""
    old = "旧段落。" * 3000
    new = "新写的正文，还没人读过。"
    item = _long(4, old)

    def review(texts, model=None):
        _long(4, new)  # autosave lands while the AI is reading
        return _good(len(texts), risk=Risk.HIGH, reason="旧文有问题")

    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.side_effect = review
        assert patrol.review_long(item, patrol.Round()) == ""

    row = ModerationItem.objects.get(pk=item.pk)
    assert row.checked_at is None
    assert row.full_text == new
    assert row.text_hash == services.text_hash(new)
    assert row.reason == "" and row.risk == Risk.UNKNOWN
    assert services.pending_long_items() == [row]


@pytest.mark.django_db
def test_216_d5_the_next_read_is_of_the_new_text(ai):
    """216, D5: the round goes on to read what is there now, and that verdict
    is the one written."""
    item = _long(5, "旧段落。" * 3000)
    seen = []

    def review(texts, model=None):
        seen.append(texts[0])
        if len(seen) == 1:
            _long(5, "新正文")
            return _good(1, risk=Risk.HIGH, reason="旧文有问题")
        return _good(1, risk=Risk.NONE)

    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.side_effect = review
        patrol.review_pending()

    assert seen[-1] == "新正文"
    row = ModerationItem.objects.get(pk=item.pk)
    assert row.checked_at is not None
    assert row.risk == Risk.NONE and row.reason == ""


# --- D6: a letter links only the site's own addresses -----------------------------


def test_216_d6_a_foreign_address_in_a_letter_is_not_a_link(settings):
    """216, D6: a quote from a member must not hand the superuser a
    clickable phishing link in a letter from the site."""
    settings.SITE_URL = "https://site.example"
    html = _lines_html("管理员请到 https://evil.example/admin 重置密码")
    assert "<a " not in html
    assert "https://evil.example/admin" in html


def test_216_d6_the_sites_own_address_is_a_link(settings):
    """216, D6: the site's own addresses still become links."""
    settings.SITE_URL = "https://site.example/"
    url = "https://site.example/teams/1/"
    html = _lines_html(f"去看看 {url}")
    assert f'<a href="{url}"' in html
    assert '<a href="https://site.example"' in _lines_html("https://site.example")


def test_216_d6_a_host_that_only_starts_like_the_site_is_not_a_link(settings):
    """216, D6: 「site.example.evil.com」 starts with the site's address but is
    another host."""
    settings.SITE_URL = "https://site.example"
    for url in ("https://site.example.evil.com/x", "https://site.examplex/y"):
        assert "<a " not in _lines_html(f"看 {url}"), url


@pytest.mark.django_db
def test_216_d6_the_whole_letter_links_only_the_site(settings):
    """216, D6: through wrap_text, the frame a plain-text letter gets."""
    settings.SITE_URL = "https://site.example"
    html = wrap_text(
        "引用：去 https://evil.example/admin 改密码\n\n处理：https://site.example/admin/",
        subject="巡查",
    )
    assert 'href="https://evil.example' not in html
    assert '<a href="https://site.example/admin/"' in html


# --- D7: 附加请求参数 cannot change the request itself -----------------------------


@pytest.mark.parametrize("key", ["functions", "function_call", "stream", "model"])
def test_216_d7_extra_body_refuses_the_requests_own_switches(key):
    """216, D7: the older way to hand tools, a streamed reply, another model."""
    with pytest.raises(ValueError, match=key):
        services.clean_extra_body({key: "x", "thinking": {"type": "disabled"}})


@pytest.mark.parametrize(
    "value",
    [{"thinking": {"type": "disabled"}}, {"response_format": {"type": "json_object"}}],
)
def test_216_d7_extra_body_still_takes_ordinary_switches(value):
    """216, D7: what 附加请求参数 is for still passes."""
    assert services.clean_extra_body(value) == value


def test_216_d7_a_value_stored_before_the_rule_is_not_sent():
    """216, D7: an extra body saved before the rule cannot turn the stream on,
    swap the model or hand the model tools."""
    provider = OpenAICompatibleProvider(
        base_url="https://example.com/v1",
        extra_body={
            "stream": True,
            "model": "x",
            "tools": [{"type": "function", "function": {"name": "f"}}],
            "tool_choice": "auto",
            "functions": [{"name": "f"}],
            "function_call": "auto",
            "messages": [],
            "thinking": {"type": "disabled"},
        },
    )
    payload = provider.build_payload(["文本"], model="our-model")
    assert payload["stream"] is False
    assert payload["model"] == "our-model"
    for key in ("tools", "tool_choice", "functions", "function_call"):
        assert key not in payload, key
    assert payload["messages"] and payload["messages"][0]["role"] == "system"
    assert payload["thinking"] == {"type": "disabled"}


# --- D8: a reply cut off half way ---------------------------------------------------


def test_216_d8_a_reply_cut_off_half_way_is_a_failed_call(monkeypatch):
    """216, D8: http.client.IncompleteRead is not an OSError; it used to
    escape review() and the round."""
    provider = OpenAICompatibleProvider(base_url="https://example.com/v1")
    calls = []

    def cut_off(payload):
        calls.append(payload)
        raise http.client.IncompleteRead(b"")

    monkeypatch.setattr(provider, "_post", cut_off)
    monkeypatch.setattr("moderation.providers.time.sleep", lambda _s: None)
    result = provider.review(["x", "y"], model="m")
    assert len(calls) == 3  # retried like a lost connection
    assert result.error.startswith("调用失败：")
    assert "IncompleteRead" in result.error
    assert result.counts is False
    assert all(verdict.error for verdict in result.verdicts)


@pytest.mark.django_db
def test_216_d8_a_cut_off_reply_leaves_the_item_waiting(ai, monkeypatch):
    """216, D8 through the patrol: the round ends as failed, the item waits."""
    item = _long(6, "正文")

    def cut_off(self, payload):
        raise http.client.IncompleteRead(b"half")

    monkeypatch.setattr(OpenAICompatibleProvider, "_post", cut_off)
    monkeypatch.setattr("moderation.providers.time.sleep", lambda _s: None)
    tally = patrol.review_pending()
    assert tally.stopped == patrol.FAILED
    row = ModerationItem.objects.get(pk=item.pk)
    assert row.checked_at is None and row.full_text == "正文"
    assert row.last_error.startswith("调用失败：") and row.failed_at is not None


@pytest.mark.django_db
def test_216_d5_a_dropped_verdict_is_not_counted_as_read(ai):
    """216, D5 follow-up: the round's count of pieces read only counts
    verdicts that were written; the replaced text is still waiting."""
    item = _long(5, "旧段落。" * 3000)

    def review(texts, model=None):
        _long(5, "新的正文")
        return _good(len(texts))

    tally = patrol.Round()
    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.side_effect = review
        patrol.review_long(item, tally)
    assert tally.reviewed == 0


@pytest.mark.django_db
def test_216_d5_a_failure_is_not_noted_on_text_replaced_meanwhile(ai):
    """216, D5 follow-up: a failed call notes its attempt on the text that
    failed. Text saved meanwhile starts from 0 attempts (submit resets them)
    and is not given up on because of the old text's failures."""
    item = _long(6, "旧的正文")
    ModerationItem.objects.filter(pk=item.pk).update(attempts=2)
    item.refresh_from_db()
    _long(6, "新的正文")  # rewritten: attempts back to 0

    given_up = services.note_failure([item], "超时", counts=True)

    row = ModerationItem.objects.get(pk=item.pk)
    assert given_up == 0
    assert row.attempts == 0
    assert row.failed_at is None and row.last_error == ""
    assert row.checked_at is None and row.full_text == "新的正文"
