"""Replaceable moderation provider (design 5.5.3).

Default: DeepSeek over its OpenAI-compatible API. The model gets **no tools**,
which is how "the AI is read-only" is guaranteed technically: it can only read
the text we send and answer with the fixed JSON structure.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from django.conf import settings

from moderation.models import Risk
from moderation.prompts import RESULT_SCHEMA, SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_OUTPUT_TOKENS = 600
MAX_ATTEMPTS = 3
RETRY_DELAYS = (1, 3)


class ProviderError(Exception):
    """The provider could not be reached or answered with something unusable."""


@dataclass
class Verdict:
    index: int
    risk: str = Risk.UNKNOWN
    categories: list = field(default_factory=list)
    reason: str = ""
    quote: str = ""


@dataclass
class ProviderResult:
    verdicts: list
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


def unknown_result(count: int, model: str, reason: str) -> ProviderResult:
    """Everything that is not a clean answer becomes 「无法判定」 (design 5.5.3)."""
    return ProviderResult(
        verdicts=[
            Verdict(index=index, risk=Risk.UNKNOWN, reason=reason)
            for index in range(count)
        ],
        model=model,
    )


class OpenAICompatibleProvider:
    """Chat-completions with JSON-schema output; works for DeepSeek and friends."""

    def __init__(self, *, base_url="", api_key="", timeout=DEFAULT_TIMEOUT):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def build_payload(self, texts, model: str) -> dict:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(texts)},
            ],
            "temperature": 0,
            "max_tokens": getattr(
                settings, "MODERATION_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS
            ),
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
        payload.update(getattr(settings, "MODERATION_EXTRA_BODY", {}) or {})
        # Never send tools: a model with tools would no longer be read-only.
        payload.pop("tools", None)
        payload.pop("tool_choice", None)
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
        for attempt in range(MAX_ATTEMPTS):
            try:
                data = self._post(payload)
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code < 500 and exc.code != 429:
                    break  # bad request or bad key: retrying will not help
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)
            except json.JSONDecodeError as exc:
                last_error = f"响应不是 JSON：{exc}"
            else:
                return self.parse(data, texts, model)
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
        logger.warning("审核调用失败：%s", last_error)
        return unknown_result(len(texts), model, f"调用失败：{last_error}")

    def parse(self, data: dict, texts, model: str) -> ProviderResult:
        usage = data.get("usage") or {}
        used_model = data.get("model") or model
        choices = data.get("choices") or []
        finish = (choices[0].get("finish_reason") if choices else "") or ""
        content = ""
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""
        if not content.strip():
            # Refusal or empty answer: not an error, just "cannot tell".
            result = unknown_result(
                len(texts), used_model, f"模型未给出结论（{finish}）"
            )
        else:
            try:
                parsed = json.loads(content)
                results = parsed["results"]
                verdicts = [self._verdict(item) for item in results]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                result = unknown_result(
                    len(texts), used_model, f"输出不符合约定结构：{exc}"
                )
            else:
                by_index = {item.index: item for item in verdicts}
                result = ProviderResult(
                    verdicts=[
                        by_index.get(
                            index,
                            Verdict(
                                index=index,
                                risk=Risk.UNKNOWN,
                                reason="模型漏掉了这一条",
                            ),
                        )
                        for index in range(len(texts))
                    ],
                    model=used_model,
                )
        result.input_tokens = int(usage.get("prompt_tokens") or 0)
        result.output_tokens = int(usage.get("completion_tokens") or 0)
        return result

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
    """The provider used for this call; swapping it is a settings change."""
    return OpenAICompatibleProvider(
        base_url=getattr(settings, "MODERATION_BASE_URL", ""),
        api_key=getattr(settings, "MODERATION_API_KEY", ""),
        timeout=getattr(settings, "MODERATION_TIMEOUT", DEFAULT_TIMEOUT),
    )
