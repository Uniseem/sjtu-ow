"""217 复核 01（内容渲染）的复现脚本。只读业务代码，不改任何东西。

在测试机上跑：
    bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider \
        handoff/rounds/217-second-review/findings/01-repro_test.py

每条用 print 打出实际结果，断言写的是「缺陷存在」时的样子。
"""

from __future__ import annotations

import time
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone


def _try(label, func):
    try:
        out = func()
        print(f"[{label}] OK -> {out!r}"[:600])
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] RAISES {type(exc).__module__}.{type(exc).__name__}: {exc}")
        return exc


# ---------------------------------------------------------------- crashes


@pytest.mark.django_db
def test_crash_inputs():
    from content.markdown import plain_text, render

    results = {}
    for label, source in [
        ("bare-bracket", "https://[x"),
        ("bare-close-bracket", "http://a]b"),
        ("bili-link-superscript-page", "[看](https://www.bilibili.com/video/BV1xx411c7mD?p=²)"),
        ("bili-bare-superscript-page", "https://www.bilibili.com/video/BV1xx411c7mD?p=²"),
        ("b23-nonnumeric-port", "https://b23.tv:abc/x"),
        ("inline-bracket-not-alone", "看这里 https://[x 结束"),
    ]:
        results[label] = _try(label, lambda s=source: render(s))
    _try("plain_text bare-bracket", lambda: plain_text("前言\n\nhttps://[x"))
    assert isinstance(results["bare-bracket"], ValueError)
    assert isinstance(results["bili-bare-superscript-page"], ValueError)
    assert not isinstance(results["b23-nonnumeric-port"], str)


# ------------------------------------------------- scheduled publish poison


def _at(moment):
    return mock.patch("django.utils.timezone.now", return_value=moment)


@pytest.mark.django_db
def test_scheduled_revision_with_crash_body_blocks_the_queue():
    from content.models import ArticleCategory, ArticlePage
    from content.services import publish_due_pages
    from content.tests.test_content import _article, _tree, _user

    _home, news = _tree()
    author = _user("sched217@example.com")
    guide = ArticleCategory.objects.get(slug="guide")
    a = _article(news, guide, author, title="已上线A", slug="a217", body="正文")
    now = timezone.now()

    # A: live article, edited to contain the crashing line, scheduled at +1h.
    a.body = "改过的正文\n\nhttps://[x"
    a.go_live_at = now + timedelta(hours=1)
    rev_a = a.save_revision()
    _try("schedule A (live page)", lambda: rev_a.publish())

    # B: someone else's new article scheduled at +2h.
    b = ArticlePage(
        title="新文章B", slug="b217", category=guide, author=author, owner=author,
        summary="s", body="B 的正文", live=False,
    )  # fmt: skip
    news.add_child(instance=b)
    b.go_live_at = now + timedelta(hours=2)
    b.save_revision().publish()
    b.refresh_from_db()
    print("B live before:", b.live)

    with _at(now + timedelta(hours=3)):
        first = _try("publish_due_pages #1", publish_due_pages)
        second = _try("publish_due_pages #2", publish_due_pages)
    b.refresh_from_db()
    a.refresh_from_db()
    print("B live after two beats:", b.live, "| A body now:", repr(a.body))
    assert isinstance(first, ValueError) and isinstance(second, ValueError)
    assert not b.live


# ------------------------------------------------------------ TOC escaping


@pytest.mark.django_db
def test_toc_text_is_escaped_twice(client):
    from content.models import ArticleCategory
    from content.tests.test_content import _article, _tree, _user

    _home, news = _tree()
    page = _article(
        news, ArticleCategory.objects.get(slug="guide"), _user("toc217@example.com"),
        title="目录", slug="toc217",
        body='## Q&A\n\na\n\n## 他说"好"\n\nb\n\n### a<b>c\n\nc',
    )  # fmt: skip
    html = client.get(page.url).content.decode()
    start = html.index('class="c-toc__list"')
    toc = html[start : html.index("</ol>", start)]
    print("TOC HTML:", toc)
    assert "Q&amp;amp;A" in toc


# ------------------------------------------------------- b23 lookups count


@pytest.mark.django_db
def test_every_new_b23_line_is_one_lookup_and_one_row(monkeypatch):
    from wagtail.embeds.exceptions import EmbedNotFoundException
    from wagtail.embeds.models import Embed

    from content import embeds
    from content.markdown import render

    calls = []

    def follow(url):
        calls.append(url)
        raise EmbedNotFoundException("dead")

    monkeypatch.setattr(embeds, "follow_b23", follow)
    source = "\n\n".join(f"https://b23.tv/x{i}" for i in range(300))
    started = time.perf_counter()
    render(source)
    print(
        f"one render of 300 distinct b23 lines: lookups={len(calls)} "
        f"embed rows={Embed.objects.count()} in {time.perf_counter() - started:.2f}s"
    )
    render(source)
    print("second render lookups total:", len(calls))
    with _at(timezone.now() + timedelta(hours=1, minutes=1)):
        render(source)
    print("after 1h TTL lookups total:", len(calls))


# ------------------------------------------------------------- XSS sanity


def test_xss_payloads():
    from content.markdown import render

    payloads = [
        '![x" onerror="alert(1)](/media/a.png)',
        '![x](/media/a.png "t\\" onerror=\\"x")',
        "[a](javascript:alert(1))",
        "<img src=x onerror=alert(1)>",
        "> 引文\n> ——<script>alert(1)</script>",
        '[看](https://www.bilibili.com/video/BV1xx411c7mD"onload="x)',
        'https://www.bilibili.com/video/BV1xx411c7mD"onload="x',
        "https://www.bilibili.com/video/?bvid=BV1xx411c7mD&autoplay=1",
        "![a](//evil.example/x.png)",
        "![a](/\\evil.example/x.png)",
        "![a](data:image/png;base64,AAAA)",
        "https://www.bilibili.com/video/BV1xx411c7mD?p=2&x=<script>",
    ]
    for p in payloads:
        out = str(render(p))
        print(f"IN  {p!r}\nOUT {out!r}")
        low = out.lower()
        assert "<script" not in low
        assert " onerror=" not in low and " onload=" not in low
        assert 'href="javascript' not in low


# ------------------------------------------------------------- performance


def test_pathological_inputs_time():
    from content.markdown import render

    builders = {
        "open-brackets": lambda n: "[" * n,
        "image-opens": lambda n: "![" * (n // 2),
        "emphasis-mix": lambda n: "*a_" * (n // 3),
        "nested-quotes": lambda n: "> " * (n // 2) + "x",
        "nested-list": lambda n: "\n".join("  " * i + "- x" for i in range(n // 200)),
        "backticks": lambda n: "`" * n,
        "pipes-table": lambda n: "|a" * 500 + "|\n" + "|-" * 500 + "|\n"
        + ("|x" * 500 + "|\n") * (n // 1000),
        "link-refs": lambda n: "[a]" * (n // 3),
        "bare-urls": lambda n: " ".join("http://a.b/" + str(i) for i in range(n // 15)),
        "long-url": lambda n: "http://" + "a" * n,
        "attribution-quote": lambda n: "> " + "x\n> " * (n // 4) + "——y",
        "strikethrough": lambda n: "~~a" * (n // 3),
        "entities": lambda n: "&amp" * (n // 4),
    }
    for name, build in builders.items():
        for n in (20_000, 200_000):
            source = build(n)
            started = time.perf_counter()
            try:
                render(source)
                note = ""
            except Exception as exc:  # noqa: BLE001
                note = f" RAISES {type(exc).__name__}"
            took = time.perf_counter() - started
            print(f"perf {name:18} n={len(source):>7} {took:7.3f}s{note}")
            if took > 5:
                break


# --------------------------------------------------------- legacy_body


def test_legacy_conversions():
    from content.legacy_body import from_html, from_stream
    from content.markdown import render

    cases = [
        ("cjk-bold-quotes", "<p>这是<b>“重点”</b>内容，<b>（注意）</b>别忘</p>"),
        ("bold-leading-space", "<p>前<b> 加粗</b>后</p>"),
        ("code-escape", "<p>变量 <code>a_b*c</code></p>"),
        ("entity-text", "<p>&amp;copy; 写法</p>"),
        ("setext-after-br", "<p>第一行<br/>---</p>"),
        ("setext-eq-after-br", "<p>第一行<br/>===</p>"),
        ("li-heading", "<ul><li># 不是标题</li><li>1. 不是编号</li></ul>"),
        ("li-after-nested", "<ul><li>a<ul><li>b</li></ul>c</li><li>d</li></ul>"),
        ("href-space", '<p><a href="https://example.com/a b">链接</a></p>'),
        ("href-paren", '<p><a href="https://example.com/a)b">链接</a></p>'),
        ("ol-start", '<ol start="5"><li>五</li><li>六</li></ol>'),
        ("two-uls", "<ul><li>a</li></ul><ul><li>b</li></ul>"),
        ("heading-br", "<h2>上<br/>下</h2>"),
        ("bold-across-br", "<p><b>一<br/>二</b></p>"),
        ("indent-4-after-br", "<p>甲<br/>    乙</p>"),
    ]
    for label, source in cases:
        md = from_html(source)
        print(f"[{label}] HTML {source!r}\n    MD  {md!r}\n    OUT {str(render(md))!r}")
    quote = from_stream(
        [{"type": "quote", "value": {"text": "- 第一句\n# 第二句\n1. 第三", "attribution": "某人"}}]
    )
    print(f"[quote] MD {quote!r}\n    OUT {str(render(quote))!r}")
