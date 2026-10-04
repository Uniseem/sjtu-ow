"""Round 192: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/192-markdown-editor/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

M = "content/tests/test_markdown.py::"
MIG = "content/tests/test_markdown_migration.py::test_bodies_drafts_and_descriptions_survive_the_switch"
LEGAL = "content/tests/test_legal_pages.py::"
QUOTE = "content/tests/test_home_sections.py::test_a_quote_names_its_source"
MD = "content/markdown.py"
VIEWS = "content/markdown_views.py"

MUTATIONS = [
    ("HTML let through", MD, '{"html": False, "breaks": True}', '{"html": True, "breaks": True}', [M + "test_html_is_shown_as_text_and_bad_links_are_not_links"]),
    ("newlines run together", MD, '{"html": False, "breaks": True}', '{"html": False, "breaks": False}', [M + "test_one_newline_is_a_line_break"]),
    ("a first-level heading in the body", MD, '"h1": "h2", "h2": "h2"', '"h1": "h1", "h2": "h2"', [M + "test_headings_are_second_and_third_level_only"]),
    ("any image shown", MD, '    if not parsed.scheme and not parsed.netloc:\n        return src.startswith("/")', "    if True:\n        return True", [M + "test_only_this_sites_images_are_shown"]),
    ("images alone stay inline", MD, "    if images and len(images) + len(lines) == len(children):", "    if False:", [M + "test_an_image_alone_is_a_figure_with_its_caption"]),
    ("no player", MD, '    src = video_src(url) if url else ""', '    src = ""', [M + "test_a_bilibili_link_alone_is_the_player"]),
    ("any site's video a player", MD, "    if host in embeds.BILIBILI_HOSTS:", "    if True:", [M + "test_a_bilibili_link_alone_is_the_player"]),
    ("pasted addresses stay text", MD, "                _link_bare_urls(token, md)", "                pass", [M + "test_pasted_addresses_become_links_without_the_full_stop"]),
    ("the full stop joins the link", MD, "            url = match.group(0).rstrip(TRAILING)", "            url = match.group(0)", [M + "test_pasted_addresses_become_links_without_the_full_stop"]),
    ("tables do not scroll", MD, '    md.add_render_rule("table_open", _render_table_open)\n', "", [M + "test_tables_scroll_and_quotes_keep_their_source"]),
    ("quotes lose their source", MD, "        state.tokens = _attributions(out)", "        state.tokens = out", [M + "test_tables_scroll_and_quotes_keep_their_source", QUOTE]),
    ("plain text keeps entities", MD, "    text = html.unescape(strip_tags(render(source)))", "    text = strip_tags(render(source))", [M + "test_plain_text_is_what_a_reader_sees"]),
    ("words counted in the raw text", "content/article_meta.py", "    return plain_text(body), rendered.images, rendered.videos", '    return body or "", rendered.images, rendered.videos', [M + "test_word_counts_leave_out_markup_and_addresses"]),
    ("search reads the markup", "search/services.py", "{plain(plain_text(page.body))}", "{plain(page.body)}", [M + "test_search_matches_the_words_not_the_markup"]),
    ("review misses the body", "moderation/integrations.py", "        parts.append(str(body))", "        pass", [M + "test_review_gets_the_body_as_written"]),
    ("article body unrendered", "content/models.py", "anchor_headings(render(self.body))", "anchor_headings(self.body)", [M + "test_the_article_page_shows_the_markdown"]),
    ("tournament description unrendered", "tournaments/templates/tournaments/detail.html", "{{ tournament.description|markdown }}", "{{ tournament.description }}", [M + "test_event_pages_show_their_descriptions_as_markdown"]),
    ("scrim description unrendered", "scrims/templates/scrims/detail.html", "{{ scrim.description|markdown }}", "{{ scrim.description }}", [M + "test_event_pages_show_their_descriptions_as_markdown"]),
    ("page body unrendered", "content/templates/content/standard_page.html", "{{ page.body|markdown }}", "{{ page.body }}", [LEGAL + "test_the_command_publishes_both_drafts"]),
    ("letter carries markup", "scrims/notifications.py", "    description = plain_text(scrim.description)  # Markdown (v6.70)", '    description = (scrim.description or "").strip()', [M + "test_the_new_scrim_letter_carries_plain_words"]),
    ("article without the editor", "content/models.py", '        FieldPanel("body", widget=MarkdownEditor),\n        FieldPanel("tournament"),', '        FieldPanel("body"),\n        FieldPanel("tournament"),', [M + "test_every_body_and_description_gets_the_editor"]),
    ("page without the editor", "content/models.py", '        FieldPanel("body", widget=MarkdownEditor),\n    ]', '        FieldPanel("body"),\n    ]', [M + "test_every_body_and_description_gets_the_editor"]),
    ("tournament without the editor", "tournaments/wagtail_hooks.py", 'FieldPanel("description", widget=MarkdownEditor),', 'FieldPanel("description"),', [M + "test_every_body_and_description_gets_the_editor"]),
    ("scrim without the editor", "scrims/wagtail_hooks.py", 'FieldPanel("description", widget=MarkdownEditor)', 'FieldPanel("description")', [M + "test_every_body_and_description_gets_the_editor"]),
    ("Font Awesome fetched", "static/js/markdown-editor.js", "autoDownloadFontAwesome: false", "autoDownloadFontAwesome: true", [M + "test_the_editor_script_loads_nothing_from_elsewhere"]),
    ("preview by GET", VIEWS, "@require_POST\ndef preview(request):", "def preview(request):", [M + "test_the_preview_is_the_public_rendering"]),
    ("anyone uploads", VIEWS, "    if not allowed.filter(pk=collection.pk).exists():", "    if False:", [M + "test_uploads_need_the_right_to_add_images"]),
    ("the original inserted", VIEWS, '    return JsonResponse({"url": image.get_rendition(UPLOAD_RENDITION).url})', '    return JsonResponse({"url": image.file.url})', [M + "test_an_upload_lands_in_the_submission_collection"]),
    ("no file, no answer", VIEWS, "    if upload is None:", "    if False:", [M + "test_a_file_that_is_not_an_image_is_refused"]),
    ("the note to the club published", "content/management/commands/load_legal_pages.py", '    return _TITLE.sub("", _COMMENT.sub("", source), count=1).strip()', '    return _TITLE.sub("", source, count=1).strip()', [LEGAL + "test_the_draft_goes_in_as_markdown_without_the_note_and_title"]),
    ("new pages start as a list", "content/services.py", '_ensure_child(homepage, StandardPage, title, slug, body="")', "_ensure_child(homepage, StandardPage, title, slug, body=[])", [LEGAL + "test_the_command_publishes_both_drafts"]),
    ("old quotes lose the dash", "content/legacy_body.py", '                lines.append("——" + _escape(value["attribution"]))', '                lines.append(_escape(value["attribution"]))', [M + "test_old_blocks_turn_into_markdown"]),
    ("old text turns into lists", "content/legacy_body.py", '        lines = [_escape_line_start(part) for part in text.split("\\n")]', '        lines = text.split("\\n")', [M + "test_old_rich_text_turns_into_the_same_markdown_page"]),
    ("drafts left as JSON", "content/migrations/0007_markdown_body.py", '            content["body"] = from_stream(content["body"], link_for, image_for)', '            content["body"] = content["body"]', [MIG]),
    ("descriptions left as HTML", "tournaments/migrations/0012_markdown_description.py", "        tournament.description = from_html(tournament.description)", "        tournament.description = tournament.description", [MIG]),
    ("managers cannot add pictures", "content/services.py", "    for name in (GROUP_TOURNAMENT, GROUP_SCRIM):", "    for name in ():", [M + "test_managers_upload_even_outside_the_submitters"]),
    ("the renderer's classes unstyled", "assets/css/input.css", "  .c-prose__video {", "  .c-prose__videos {", [M + "test_what_the_renderer_emits_has_its_styles"]),
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
