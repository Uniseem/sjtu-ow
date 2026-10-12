"""Synthetic backend fixtures missing from the ordinary screenshot seed.

Run extend_seed only inside the temporary Django parity database. No production
font, identity, license, or external service is involved. fontTools and brotli
are existing project dependencies; every glyph below is drawn by this fixture.
The returned IDs are shared by the frozen Django pages and the Go importer.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path


FONT_NAME = '验收生成字体'
FONT_CSS_NAME = 'ow-parity-font'
FONT_LICENSE = 'MIT；字形仅用于本站迁移验收，由夹具生成。'


def _font_bytes(sample_text: str) -> tuple[bytes, bytes, list[int]]:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    # A compact real font, rather than a fake WOFF2 header which a browser would
    # reject. Blank space plus deterministic original geometric glyphs cover
    # the complete frozen font-library sample, including its Chinese characters.
    codepoints = sorted({ord(character) for character in sample_text} | {32})
    names = {value: ('space' if value == 32 else f'u{value:06X}') for value in codepoints}
    order = ['.notdef', *names.values()]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(names)
    glyphs = {}
    metrics = {}
    for index, name in enumerate(order):
        pen = TTGlyphPen(None)
        if name != 'space':
            left, top = 70, 700
            right = 430 + (index % 4) * 30
            pen.moveTo((left, 0))
            pen.lineTo((right, 0))
            pen.lineTo((right, top))
            pen.lineTo((left, top))
            pen.closePath()
            # Clockwise inner contour makes a hollow fixture glyph.
            pen.moveTo((left + 65, 75))
            pen.lineTo((left + 65, top - 75))
            pen.lineTo((right - 65, top - 75))
            pen.lineTo((right - 65, 75))
            pen.closePath()
        glyphs[name] = pen.glyph()
        metrics[name] = (300 if name == 'space' else 600, 0)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({
        'familyName': FONT_NAME,
        'styleName': 'Regular',
        'uniqueFontIdentifier': 'SJTU-OW-Parity-Geometric-Regular',
        'fullName': FONT_NAME + ' Regular',
        'psName': 'SJTUOWParityGeometric-Regular',
        'version': 'Version 1.0',
        'copyright': 'Original synthetic glyphs generated for SJTU-OW parity; MIT.',
    })
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                    usWinAscent=800, usWinDescent=200, usWeightClass=400, fsType=0)
    builder.setupPost()
    builder.setupMaxp()
    builder.font.recalcTimestamp = False
    builder.font['head'].created = builder.font['head'].modified = 3874608000
    original = io.BytesIO()
    builder.font.save(original)
    builder.font.flavor = 'woff2'
    compressed = io.BytesIO()
    builder.font.save(compressed)
    return original.getvalue(), compressed.getvalue(), codepoints


def extend_seed(data: dict) -> dict:
    """Create a downloadable ready face and checked review records; update data.

    Call after screens.seed/account_scenarios.extend_seed, before importing the
    temporary legacy database. Fonts stay unselected, so adding this fixture
    does not change typography on every unrelated page in the global matrix.
    """
    from accounts.models import User
    from core.models import FontFamily, FontFace
    from core.fonts.services import SAMPLE_TEXT
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils import timezone
    from moderation.models import ModerationItem, Risk, TargetType, Category
    from tournaments.models import Tournament
    from tournaments import services as tournament_services
    from scrims.models import Scrim
    from scrims import services as scrim_services

    actor = User.objects.get(email='officer@screens.test')
    member = User.objects.get(pk=data['member'])
    now = timezone.now()
    family, _ = FontFamily.objects.update_or_create(css_name=FONT_CSS_NAME, defaults={
        'name': FONT_NAME, 'source': FontFamily.Source.UPLOAD,
        'source_ref': 'parity-generated.ttf',
        'license_type': FontFamily.License.OPEN_SOURCE,
        'license_note': FONT_LICENSE, 'license_confirmed': True,
        'created_by': actor,
    })
    original, compressed, codepoints = _font_bytes(SAMPLE_TEXT)
    relative = f'fonts/{family.pk}/slices/parity-400.woff2'
    if default_storage.exists(relative):
        default_storage.delete(relative)
    stored = default_storage.save(relative, ContentFile(compressed))
    if stored != relative:
        raise RuntimeError('synthetic font storage unexpectedly renamed its slice')
    unicode_range = ','.join(f'U+{value:X}' for value in codepoints)
    face, _ = FontFace.objects.update_or_create(
        family=family, weight=400, style=FontFace.Style.NORMAL, defaults={
            'status': FontFace.Status.READY, 'progress': 100, 'error': '',
            'slices': [{'path': relative, 'unicode_range': unicode_range}],
            'slice_count': 1, 'total_bytes': len(compressed),
            'glyph_count': len(codepoints),
        })
    original_name = f'fonts/{family.pk}/original/parity-generated.ttf'
    if default_storage.exists(original_name):
        default_storage.delete(original_name)
    face.original_file.save('parity-generated.ttf', ContentFile(original), save=True)
    # Keep fixture timestamps consistent even though auto_now_add is evaluated
    # separately for each model. Do not modify application services or clocks.
    FontFamily.objects.filter(pk=family.pk).update(created_at=now)
    FontFace.objects.filter(pk=face.pk).update(created_at=now, updated_at=now)

    text = '这是一条只用于迁移验收的内容巡查快照。'
    item, _ = ModerationItem.objects.update_or_create(
        target_type=TargetType.ARTICLE, target_id=data['article'], field='body',
        text_hash=hashlib.sha256(text.encode()).hexdigest(), defaults={
            'url': '/news/screens-guide/', 'author': member,
            'excerpt': text, 'full_text': text, 'risk': Risk.MEDIUM,
            'categories': [Category.OTHER], 'reason': '验收夹具：供人工复核。',
            'quote': '内容巡查快照', 'model': 'parity-fictional-model',
            'status': ModerationItem.Status.PENDING, 'checked_at': now,
            'input_tokens': 10, 'output_tokens': 5,
        })
    motto_text = member.motto or '验收用个人宣言'
    motto, _ = ModerationItem.objects.update_or_create(
        target_type=TargetType.MOTTO, target_id=member.pk, field='motto',
        text_hash=hashlib.sha256(motto_text.encode()).hexdigest(), defaults={
            'url': '/me/', 'author': member, 'excerpt': motto_text,
            'risk': Risk.LOW, 'categories': [Category.OTHER],
            'reason': '验收夹具：检查人工处理入口。',
            'model': 'parity-fictional-model', 'checked_at': now,
            'status': ModerationItem.Status.PENDING,
        })
    ModerationItem.objects.filter(pk__in=[item.pk, motto.pk]).update(created_at=now)
    # Publish screenshots exercise the legitimate draft -> published path.
    # Keep cup/scrim published for every other page and illegal-operation gates.
    drafts = {}
    reset_fields = {'status', 'published_at', 'reminder_sent_at', 'moved_from',
                    'teams_generated_at', 'roster_changed_at', 'created_by'}
    for model, source_key, services in ((Tournament, 'cup', tournament_services),
                                        (Scrim, 'scrim', scrim_services)):
        source = model.objects.get(pk=data[source_key])
        values = {
            field.attname: getattr(source, field.attname)
            for field in model._meta.concrete_fields
            if not field.primary_key and field.name not in reset_fields
            and field.name != 'title' and not getattr(field, 'auto_now', False)
            and not getattr(field, 'auto_now_add', False)
        }
        values.update(status='draft', created_by=actor)
        for field in model._meta.concrete_fields:
            if field.name in reset_fields - {'status', 'created_by'}:
                values[field.attname] = None
        draft, _ = model.objects.update_or_create(
            title='发布验收：' + source.title, defaults=values)
        gaps = services.missing(draft)
        if gaps:
            raise RuntimeError('publish parity draft is incomplete: ' + ', '.join(gaps))
        drafts[source_key + '_draft'] = draft.pk
    identifiers = {'font': family.pk, 'font_face': face.pk,
                   'moderation': item.pk, 'moderation_motto': motto.pk, **drafts}
    data.update(identifiers)
    return identifiers


def validate_import(work: Path, data: dict) -> None:
    """Fail if the matrix's actual targets or real slice bytes were not imported."""
    import sqlite3
    from fontTools.ttLib import TTFont

    with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as database:
        font = database.execute('SELECT css_name FROM font_families WHERE id=?',
                                (data['font'],)).fetchone()
        face = database.execute('SELECT family_id,status,slices FROM font_faces WHERE id=?',
                                (data['font_face'],)).fetchone()
        if not font or font[0] != FONT_CSS_NAME or not face or face[:2] != (data['font'], 'ready'):
            raise RuntimeError('backend parity font target was not imported')
        import json
        slices = json.loads(face[2])
        if len(slices) != 1:
            raise RuntimeError('backend parity font slice count changed')
        slice_path = work / 'media' / slices[0]['path']
        payload = slice_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != slices[0]['sha256']:
            raise RuntimeError('backend parity font bytes changed')
        with TTFont(io.BytesIO(payload)) as font_file:
            if not font_file.getBestCmap():
                raise RuntimeError('backend parity font cannot be decoded')
        for table, key in (('tournaments', 'cup_draft'), ('scrims', 'scrim_draft')):
            row = database.execute(f'SELECT status FROM {table} WHERE id=?',
                                   (data[key],)).fetchone()
            if row != ('draft',):
                raise RuntimeError('publish parity draft was not imported: ' + key)
        for key in ('moderation', 'moderation_motto'):
            row = database.execute('SELECT checked_at FROM moderation_items WHERE id=?',
                                   (data[key],)).fetchone()
            if not row or not row[0]:
                raise RuntimeError('checked backend review target missing: ' + key)
    print('ADMIN-FIXTURES-OK real-font/face/slice and two checked reviews', flush=True)
