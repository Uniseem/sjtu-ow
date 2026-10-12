"""Composite specimen oracle: actual frozen-template fixture outputs.

This is a component oracle, not a claim that old Django had the new appendix.
The normal styleguide comparison keeps its historical sections; the new A8
appendix is independently compared against these old-template outputs.
"""
import html
import json
from pathlib import Path


def document(root: Path, legacy_origin: str, data: dict):
    fixtures = []
    for filename in ('legacy-ui.json', 'legacy-cards.json'):
        fixtures += json.loads((root / 'web/apps/site/src/testdata' / filename).read_text())
    sections = []
    for index, case in enumerate(fixtures):
        frame = ' class="c-pagehead c-pagehead--picture"' if case['component']=='CPagehead' else ''
        sections.append(f'<section data-sample="{index}"><h2 class="mb-4">{html.escape(case["component"])} {index + 1}</h2><div{frame}>{case["html"]}</div></section>')
    # Render real-image and default-pool samples through the frozen templates,
    # using the exact seed image consumed by the Go specimen endpoint.
    from unittest.mock import patch
    from types import SimpleNamespace as NS
    from django.template.loader import render_to_string
    from wagtail.images import get_image_model
    from accounts.models import User
    from content.models import ArticlePage
    image = get_image_model().objects.get(pk=data['image'])
    extra = []
    for default in (False, True):
        person = User(pk=7, nickname='小满', is_active=True, avatar=None if default else image)
        article = ArticlePage(pk=37, content_type_id=1, title='默认封面池' if default else '真实封面', slug='weekend', cover=None if default else image)
        pool = [image] if default else []
        avatar = render_to_string('components/avatar.html', {'person':person,'size':'lg','avatar_pool':pool})
        with patch.object(ArticlePage, 'get_url', return_value='/news/weekend/'):
            card = render_to_string('components/post_card.html', {'article':article,'cover_pool':pool,'avatar_pool':[]})
        logo = '' if default else render_to_string('teams/_logo.html', {'team':NS(pk=7,name='思源',logo=image)})
        extra.append('<section data-' + ('default' if default else 'real') + '-image-sample><h2>' + ('默认图片池' if default else '真实图片') + '</h2>' + avatar + card + logo + '</section>')
    sections.extend(extra)
    return '<!doctype html><html lang="zh-Hans"><head><title>组件样张 · SJTU-OW</title><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="' + legacy_origin + '/static/css/app.css"></head><body><main id="main" class="l-container l-section"><h1>组件样张</h1><div class="flex flex-col gap-16" data-component-samples>' + ''.join(sections) + '</div></main></body></html>'
