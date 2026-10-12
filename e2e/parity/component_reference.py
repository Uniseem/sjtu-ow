"""Composite specimen oracle: actual frozen-template fixture outputs.

This is a component oracle, not a claim that old Django had the new appendix.
The normal styleguide comparison keeps its historical sections; the new A8
appendix is independently compared against these old-template outputs.
"""
import html
import json
from pathlib import Path


def document(root: Path, legacy_origin: str):
    fixtures = []
    for filename in ('legacy-ui.json', 'legacy-cards.json'):
        fixtures += json.loads((root / 'web/apps/site/src/testdata' / filename).read_text())
    sections = []
    for index, case in enumerate(fixtures):
        frame = ' class="relative h-64 overflow-hidden"' if case['component']=='CPagehead' else ''
        sections.append(f'<section data-sample="{index}"><h2 class="mb-4">{html.escape(case["component"])} {index + 1}</h2><div{frame}>{case["html"]}</div></section>')
    return '<!doctype html><html lang="zh-Hans"><head><title>组件样张 · SJTU-OW</title><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="' + legacy_origin + '/static/css/app.css"></head><body><main id="main" class="l-container l-section"><h1>组件样张</h1><div class="flex flex-col gap-16" data-component-samples>' + ''.join(sections) + '</div></main></body></html>'
