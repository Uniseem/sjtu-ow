"""Round 198 (design 5.5.3, v7.2): a review that did not come back is not a
review; the patrol does not hold the single worker; answers fit the limit."""

import io
import json
import urllib.error
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from accounts.models import User
from moderation import patrol, services
from moderation.models import ModerationItem, Risk, TargetType
from moderation.providers import (
    OpenAICompatibleProvider,
    ProviderResult,
    Verdict,
    failed_result,
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


def _short(index, text=None):
    return services.submit(
        target_type=TargetType.NICKNAME,
        target_id=index,
        field="nickname",
        text=text or f"昵称{index}",
    )


def _long(index, text):
    return services.submit(
        target_type=TargetType.ARTICLE, target_id=index, field="content", text=text
    )


def _http(code, body=b""):
    return urllib.error.HTTPError(
        "https://example.com", code, "x", {}, io.BytesIO(body)
    )


def _answer(content, finish="stop"):
    return {
        "choices": [{"finish_reason": finish, "message": {"content": content}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 600},
    }


# --- what counts as no answer (providers) ----------------------------------------


def test_a_call_that_never_comes_back_is_an_error_not_a_verdict():
    provider = OpenAICompatibleProvider(base_url="https://example.com/v1")
    with (
        patch.object(OpenAICompatibleProvider, "_post", side_effect=OSError("boom")),
        patch("moderation.providers.time.sleep"),
    ):
        result = provider.review(["x", "y"], model="m")
    assert result.error == "调用失败：boom"
    assert result.counts is False  # the network, not the content
    assert all(verdict.error for verdict in result.verdicts)


@pytest.mark.parametrize(
    ("code", "posts", "counts"),
    [
        (400, 1, True),
        (401, 1, False),
        (404, 1, False),
        (429, 3, False),
        (500, 3, False),
    ],
)
def test_only_a_plain_400_may_be_the_content(code, posts, counts):
    """A provider's own content block answers 400; a bad key, address or a
    busy service is no fault of the text."""
    provider = OpenAICompatibleProvider(base_url="https://example.com/v1")
    body = json.dumps({"error": {"message": "Content Exists Risk"}}).encode()
    with (
        patch.object(
            OpenAICompatibleProvider,
            "_post",
            side_effect=lambda _p: (_ for _ in ()).throw(_http(code, body)),
        ) as post,
        patch("moderation.providers.time.sleep"),
    ):
        result = provider.review(["x"], model="m")
    assert post.call_count == posts
    assert result.counts is counts
    assert result.error == f"调用失败：HTTP {code}：Content Exists Risk"


def test_a_cut_off_answer_is_no_answer():
    provider = OpenAICompatibleProvider()
    half = '{"results": [{"index": 0, "risk": "none", "categories": [], "reason": "正'
    result = provider.parse(_answer(half, finish="length"), ["a", "b"], "m")
    assert result.error.startswith("回答被截断") and result.counts is True
    # Even a complete-looking answer cut at the limit is not trusted.
    whole = json.dumps(
        {
            "results": [
                {
                    "index": 0,
                    "risk": "none",
                    "categories": [],
                    "reason": "",
                    "quote": "",
                }
            ]
        }
    )
    assert provider.parse(_answer(whole, finish="length"), ["a"], "m").error


def test_a_malformed_answer_is_no_answer_but_a_refusal_is_a_verdict():
    provider = OpenAICompatibleProvider()
    broken = provider.parse(_answer("不是 JSON"), ["x"], "m")
    assert broken.error.startswith("输出不符合约定结构") and broken.counts is True
    nobody = json.dumps(
        {
            "results": [
                {
                    "index": 7,
                    "risk": "none",
                    "categories": [],
                    "reason": "",
                    "quote": "",
                }
            ]
        }
    )
    assert (
        provider.parse(_answer(nobody), ["x"], "m").error == "回答里没有任何一条的结论"
    )
    refused = provider.parse(_answer("", finish="content_filter"), ["x"], "m")
    assert refused.error == "" and refused.verdicts[0].risk == Risk.UNKNOWN


def test_one_left_out_of_a_good_answer_is_to_be_tried_again():
    provider = OpenAICompatibleProvider()
    one = json.dumps(
        {
            "results": [
                {
                    "index": 0,
                    "risk": "low",
                    "categories": [],
                    "reason": "轻微",
                    "quote": "",
                }
            ]
        }
    )
    result = provider.parse(_answer(one), ["a", "b"], "m")
    assert result.error == ""
    assert result.verdicts[0].error == "" and result.verdicts[1].error


# --- not read is not read (patrol) ------------------------------------------------


@pytest.mark.django_db
def test_a_failed_review_leaves_the_item_waiting_with_its_text(ai):
    item = _long(1, "攻略正文。" * 3000)
    down = failed_result(1, "m", "调用失败：timed out", counts=False)
    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.return_value = down
        tally = patrol.review_pending()
    assert tally.stopped == patrol.FAILED and tally.reviewed == 0
    item.refresh_from_db()
    assert item.checked_at is None
    assert item.full_text == "攻略正文。" * 3000  # kept for the next try
    assert item.last_error == "调用失败：timed out" and item.failed_at is not None
    assert item.attempts == 0  # a lost connection is not the text's fault

    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.return_value = _good(1)
        assert patrol.review_pending().reviewed == 1
    item.refresh_from_db()
    assert item.checked_at is not None and item.risk == Risk.NONE


@pytest.mark.django_db
def test_failures_the_content_may_cause_give_up_at_three(ai):
    item = _short(1)
    blocked = failed_result(
        1, "m", "调用失败：HTTP 400：Content Exists Risk", counts=True
    )
    down = failed_result(1, "m", "调用失败：HTTP 503", counts=False)
    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.return_value = down
        for _ in range(5):
            patrol.review_pending()
        item.refresh_from_db()
        assert item.checked_at is None and item.attempts == 0

        get_provider.return_value.review.return_value = blocked
        patrol.review_pending()
        patrol.review_pending()
        item.refresh_from_db()
        assert item.checked_at is None and item.attempts == 2
        patrol.review_pending()
    item.refresh_from_db()
    assert item.checked_at is not None and item.attempts == 3
    assert item.risk == Risk.UNKNOWN
    assert (
        item.reason == "AI 没看成（试了 3 次）：调用失败：HTTP 400：Content Exists Risk"
    )
    assert item.status == ModerationItem.Status.PENDING  # for a person to read


@pytest.mark.django_db
def test_a_verdict_the_ai_did_not_give_is_never_reused(ai):
    given_up = _short(1, "同一句话")
    services.note_failure([given_up], "回答被截断", counts=True)
    services.note_failure([given_up], "回答被截断", counts=True)
    services.note_failure([given_up], "回答被截断", counts=True)
    given_up.refresh_from_db()
    assert given_up.checked_at is not None
    old = _short(2, "同一句话")
    services.record(
        old,
        risk=Risk.UNKNOWN,
        categories=[],
        reason="调用失败：HTTP 401",
        quote="",
        model="m",
    )
    again = _short(3, "同一句话")
    assert services.copy_recent_verdict(again) is False
    services.record(
        old, risk=Risk.LOW, categories=[], reason="轻微", quote="", model="m"
    )
    assert services.copy_recent_verdict(again) is True


@pytest.mark.django_db
def test_the_first_failure_ends_the_round(ai):
    ai.moderation_max_output_tokens = 60  # one short item per request
    ai.save()
    for index in range(3):
        _short(index + 1)
    _long(9, "正文" * 5000)
    down = failed_result(1, "m", "调用失败：HTTP 503", counts=False)
    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.return_value = down
        assert patrol.review_pending().stopped == patrol.FAILED
        assert get_provider.return_value.review.call_count == 1


@pytest.mark.django_db
def test_an_item_that_failed_goes_alone_after_new_ones(ai):
    other = _short(4)  # older, but failed more often
    other.attempts = 2
    other.failed_at = timezone.now()
    other.save()
    suspect = _short(1)
    suspect.attempts = 1
    suspect.failed_at = timezone.now()
    suspect.save()
    lost = _short(2)  # its call was lost: batched as usual
    lost.failed_at = timezone.now()
    lost.save()
    fresh = _short(3)
    assert services.pending_short_items() == [lost, fresh]
    ModerationItem.objects.filter(pk__in=[lost.pk, fresh.pk]).update(
        checked_at=timezone.now()
    )
    assert services.pending_short_items() == [suspect]

    seen = []

    def judge(texts, model=None):
        seen.append(list(texts))
        return _good(len(texts))

    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.side_effect = judge
        assert patrol.review_pending().reviewed == 2
    assert seen == [["昵称1"], ["昵称4"]]


@pytest.mark.django_db
def test_a_long_piece_that_failed_waits_behind_new_ones(ai):
    suspect = _long(1, "旧文章")
    suspect.attempts = 1
    suspect.failed_at = timezone.now()
    suspect.save()
    fresh = _long(2, "新文章")
    assert services.pending_long_items(limit=1) == [fresh]


@pytest.mark.django_db
def test_one_left_out_stays_waiting_while_the_rest_are_read(ai):
    first, second = _short(1), _short(2)
    answer = _good(2)
    answer.verdicts[1].error = "模型漏掉了这一条"
    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.side_effect = [answer, _good(1)]
        tally = patrol.review_pending()
    assert tally.stopped == "" and tally.reviewed == 2
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.checked_at is not None and first.attempts == 0
    assert second.attempts == 1 and second.checked_at is not None  # alone, then read


# --- answers that fit -----------------------------------------------------------------


@pytest.mark.django_db
def test_a_batch_is_as_large_as_the_output_limit_holds(ai):
    for tokens, size in ((600, 10), (1200, 20), (9999, 20), (119, 1), (30, 1)):
        ai.moderation_max_output_tokens = tokens
        ai.save()
        assert services.batch_size() == size
    ai.moderation_max_output_tokens = 600
    ai.save()
    for index in range(12):
        _short(index + 1)
    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.side_effect = lambda texts, model=None: _good(
            len(texts)
        )
        assert patrol.review_pending().reviewed == 12
        sizes = [
            len(call.args[0])
            for call in get_provider.return_value.review.call_args_list
        ]
    assert sizes[:2] == [10, 2]


@pytest.mark.django_db
def test_a_long_piece_goes_a_chunk_per_request_and_a_high_risk_ends_it(ai):
    paragraphs = ["第一块" * 2500, "第二块" * 2500, "第三块" * 2500]
    item = _long(1, "\n\n".join(paragraphs))
    assert len(services.split_text(item.full_text)) == 3
    answers = [_good(1), _good(1, Risk.HIGH, "代打"), _good(1)]
    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.side_effect = answers
        assert patrol.review_pending().reviewed == 1
        calls = get_provider.return_value.review.call_args_list
    assert [len(call.args[0]) for call in calls] == [1, 1]
    assert "第二块" in calls[1].args[0][0] and "第一块" not in calls[1].args[0][0]
    item.refresh_from_db()
    assert item.risk == Risk.HIGH and item.reason == "代打"
    assert item.input_tokens == 200 and item.output_tokens == 40


# --- not holding the worker ----------------------------------------------------


def _follow_ups():
    return DBTaskResult.objects.filter(
        task_path="moderation.tasks.patrol", priority=patrol.FOLLOW_UP_PRIORITY
    )


@pytest.mark.django_db
def test_a_patrol_stops_starting_requests_when_its_minute_is_up(ai):
    for index in range(30):
        _short(index + 1)
    clock = iter([0, 0, 30, 61])
    with (
        patch("moderation.patrol.time.monotonic", side_effect=lambda: next(clock)),
        patch("moderation.providers.get_provider") as get_provider,
    ):
        get_provider.return_value.review.side_effect = lambda texts, model=None: _good(
            len(texts)
        )
        tally = patrol.review_pending()
    assert tally.stopped == patrol.TIME and tally.reviewed == 20
    assert get_provider.return_value.review.call_count == 2


@pytest.mark.django_db
def test_a_long_piece_waits_for_the_next_go_too(ai):
    _long(1, "正文")
    with patch("moderation.providers.get_provider") as get_provider:
        assert patrol.review_pending(seconds=0).stopped == patrol.TIME
    assert get_provider.call_count == 0


@pytest.mark.django_db
def test_the_rest_is_queued_behind_other_work_and_the_beat_waits(ai):
    _short(1)
    mail.outbox.clear()
    with (
        patch("moderation.patrol.PATROL_SECONDS", 0),
        patch("moderation.providers.get_provider") as get_provider,
    ):
        assert patrol.run() == (0, 0)
    assert get_provider.call_count == 0
    assert _follow_ups().count() == 1
    assert patrol.enqueue_if_due() is False  # no second round meanwhile

    # Stopped for any other reason: nothing queued.
    _follow_ups().delete()
    cache.delete(patrol.PATROL_KEY)
    down = failed_result(1, "m", "调用失败：HTTP 503", counts=False)
    with patch("moderation.providers.get_provider") as get_provider:
        get_provider.return_value.review.return_value = down
        patrol.run()
    assert _follow_ups().count() == 0


@pytest.mark.django_db
def test_while_it_goes_on_the_letter_waits_until_a_finding_is_half_an_hour_old(ai):
    User.objects.create_superuser(
        email="root198@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    found = _long(1, "可疑内容")
    services.record(
        found, risk=Risk.HIGH, categories=[], reason="可疑", quote="", model="m"
    )
    _short(2)
    mail.outbox.clear()
    with patch("moderation.patrol.PATROL_SECONDS", 0):
        assert patrol.run() == (0, 0)
        ModerationItem.objects.filter(pk=found.pk).update(
            checked_at=timezone.now() - timedelta(minutes=31)
        )
        assert patrol.run() == (0, 1)
    assert mail.outbox


# --- where it shows ------------------------------------------------------------


@pytest.mark.django_db
def test_trying_says_what_to_change(ai):
    cases = [
        (
            failed_result(1, "m", "回答被截断（finish_reason=length）", counts=True),
            "最多输出 token",
        ),
        (
            failed_result(
                1, "m", "调用失败：The read operation timed out", counts=False
            ),
            "把「超时」调大",
        ),
        (
            failed_result(1, "m", "调用失败：HTTP 401：bad key", counts=False),
            "密钥不对",
        ),
    ]
    for result, hint in cases:
        with patch("moderation.providers.get_provider") as get_provider:
            get_provider.return_value.review.return_value = result
            ok, message = services.try_connection()
        assert ok is False and hint in message


@pytest.mark.django_db
def test_the_review_list_says_what_is_waiting_and_why(ai, client):
    root = User.objects.create_superuser(
        email="list198@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(root)  # saving the login puts the nickname on record
    ModerationItem.objects.all().delete()
    _short(1)
    stuck = _short(2)
    services.note_failure([stuck], "回答被截断（finish_reason=length）", counts=True)
    read = _short(3)  # read already: not waiting
    services.record(read, risk=Risk.NONE, categories=[], reason="", quote="", model="m")
    html = client.get(reverse("moderation_index")).content.decode()
    assert "还有 2 条等着看" in html
    assert "有 1 条内容上次没看成：回答被截断（finish_reason=length）" in html
    assert "最多输出 token" in html
