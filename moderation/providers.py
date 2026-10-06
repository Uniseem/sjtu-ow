"""Replaceable moderation provider (design 5.5.3).

Default: DeepSeek over its OpenAI-compatible API. The model gets **no tools**,
which is how "the AI is read-only" is guaranteed technically: it can only read
the text we send and answer with the fixed JSON structure.
"""

from __future__ import annotations

import http.client
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from moderation.models import Risk
from moderation.prompts import RESULT_SCHEMA, SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_OUTPUT_TOKENS = 600
MAX_ATTEMPTS = 3
RETRY_DELAYS = (1, 3)
# What the reason of a call that never came back starts with (the hints in
# 「试一下」 and records from before v7.2 rely on it).
FAILED_CALL = "调用失败："
TRUNCATED = "回答被截断"


class ProviderError(Exception):
    """The provider could not be reached or answered with something unusable."""


@dataclass
class Verdict:
    index: int
    risk: str = Risk.UNKNOWN
    categories: list = field(default_factory=list)
    reason: str = ""
    quote: str = ""
    # Set when the answer left this one out: not a verdict, try it again.
    error: str = ""


@dataclass
class ProviderResult:
    verdicts: list
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    # Design 5.5.3 (v7.2): set when the request did not come back with a
    # usable answer; nothing in it counts as reviewed.
    error: str = ""
    # Whether the failure may come from the content sent (HTTP 400, a cut-off
    # or malformed answer) rather than the network, the service or the
    # settings; only those count towards giving up on an item.
    counts: bool = False


def unknown_result(count: int, model: str, reason: str) -> ProviderResult:
    """A clean 「无法判定」 for every text: the model would not say (design
    5.5.3: a refusal goes to a person, it is not an error)."""
    return ProviderResult(
        verdicts=[
            Verdict(index=index, risk=Risk.UNKNOWN, reason=reason)
            for index in range(count)
        ],
        model=model,
    )


def failed_result(count: int, model: str, error: str, *, counts: bool):
    """No usable answer (design 5.5.3, v7.2): the verdicts are placeholders
    and the result carries why."""
    result = unknown_result(count, model, error)
    for verdict in result.verdicts:
        verdict.error = error
    result.error = error
    result.counts = counts
    return result


def http_error(exc: urllib.error.HTTPError) -> str:
    """「HTTP 400：what the service said」, so the owner sees the provider's
    own words (a content block, an unknown parameter)."""
    try:
        raw = exc.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - the status alone still says enough
        raw = ""
    try:
        detail = json.loads(raw).get("error")
        said = detail.get("message", "") if isinstance(detail, dict) else detail
    except (ValueError, AttributeError):
        said = raw
    said = " ".join(str(said or "").split())[:160]
    return f"HTTP {exc.code}：{said}" if said else f"HTTP {exc.code}"


class OpenAICompatibleProvider:
    """Chat-completions with JSON-schema output; works for DeepSeek and friends."""

    def __init__(
        self,
        *,
        base_url="",
        api_key="",
        timeout=DEFAULT_TIMEOUT,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        extra_body=None,
    ):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.extra_body = dict(extra_body or {})

    def build_payload(self, texts, model: str) -> dict:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(texts)},
            ],
            "temperature": 0,
            "max_tokens": self.max_output_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "moderation_result",
                    "strict": True,
                    "schema": RESULT_SCHEMA,
                },
            },
        }
        # Provider-specific switches (for example turning thinking off) without
        # touching this file; the exact key differs per provider.
        from moderation.services import EXTRA_BODY_FORBIDDEN

        # What 全站设置 refuses is also never taken from a value stored
        # before the rule (216, D7): no tools (read-only), no stream, the
        # model and messages are ours.
        payload.update(
            {
                key: value
                for key, value in self.extra_body.items()
                if key not in EXTRA_BODY_FORBIDDEN
            }
        )
        return payload

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def review(self, texts, model: str) -> ProviderResult:
        payload = self.build_payload(texts, model)
        last_error = ""
        counts = False
        for attempt in range(MAX_ATTEMPTS):
            try:
                data = self._post(payload)
            except urllib.error.HTTPError as exc:
                last_error = http_error(exc)
                if exc.code < 500 and exc.code != 429:
                    # Bad request or bad key: retrying will not help. Only a
                    # plain 400 may be about this content (a provider's own
                    # content block); 401/403/404 are the settings.
                    counts = exc.code == 400
                    break
            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
                # A reply cut off half way (IncompleteRead, BadStatusLine) is a
                # failed call like any other (216, D8); it used to escape the
                # round, with no note of the failure and no follow-up.
                http.client.HTTPException,
            ) as exc:
                last_error = str(exc) or type(exc).__name__
            except json.JSONDecodeError as exc:
                last_error = f"响应不是 JSON：{exc}"
            else:
                return self.parse(data, texts, model)
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
        logger.warning("审核调用失败：%s", last_error)
        return failed_result(
            len(texts), model, f"{FAILED_CALL}{last_error}", counts=counts
        )

    def parse(self, data: dict, texts, model: str) -> ProviderResult:
        usage = data.get("usage") or {}
        used_model = data.get("model") or model
        choices = data.get("choices") or []
        finish = (choices[0].get("finish_reason") if choices else "") or ""
        content = ""
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""
        if finish == "length":
            # Cut off at the output limit (thinking left on, or too many
            # items for 最多输出): half an answer is no answer (v7.2).
            result = failed_result(
                len(texts),
                used_model,
                f"{TRUNCATED}（finish_reason=length）",
                counts=True,
            )
        elif not content.strip():
            # Refusal or empty answer: not an error, just "cannot tell".
            result = unknown_result(
                len(texts), used_model, f"模型未给出结论（{finish}）"
            )
        else:
            result = self._answer(content, len(texts), used_model)
        result.input_tokens = int(usage.get("prompt_tokens") or 0)
        result.output_tokens = int(usage.get("completion_tokens") or 0)
        return result

    def _answer(self, content: str, count: int, model: str) -> ProviderResult:
        """The verdicts in a complete answer; one the answer leaves out is to
        be tried again, and an answer about none of them is no answer."""
        try:
            parsed = json.loads(content)
            results = parsed["results"]
            verdicts = [self._verdict(item) for item in results]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return failed_result(
                count, model, f"输出不符合约定结构：{exc}", counts=True
            )
        by_index = {item.index: item for item in verdicts}
        if not by_index.keys() & set(range(count)):
            return failed_result(count, model, "回答里没有任何一条的结论", counts=True)
        missed = "模型漏掉了这一条"
        return ProviderResult(
            verdicts=[
                by_index.get(
                    index,
                    Verdict(
                        index=index, risk=Risk.UNKNOWN, reason=missed, error=missed
                    ),
                )
                for index in range(count)
            ],
            model=model,
        )

    @staticmethod
    def _verdict(item: dict) -> Verdict:
        risk = str(item.get("risk") or Risk.UNKNOWN)
        if risk not in Risk.values:
            risk = Risk.UNKNOWN
        categories = [str(name) for name in item.get("categories") or []]
        return Verdict(
            index=int(item["index"]),
            risk=risk,
            categories=categories,
            reason=str(item.get("reason") or "")[:2000],
            quote=str(item.get("quote") or "")[:2000],
        )


def get_provider():
    """The provider used for this call, from 全站设置 → AI 审核 (design 5.5.3,
    v7.1); read each time, so a change applies from the next patrol on."""
    from core.models import SiteSettings

    site = SiteSettings.load()
    return OpenAICompatibleProvider(
        base_url=site.moderation_base_url,
        api_key=site.moderation_api_key,
        timeout=site.moderation_timeout or DEFAULT_TIMEOUT,
        max_output_tokens=site.moderation_max_output_tokens
        or DEFAULT_MAX_OUTPUT_TOKENS,
        extra_body=site.moderation_extra_body,
    )
