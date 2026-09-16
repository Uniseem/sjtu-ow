"""Build tiny real font files for the font-library tests."""

from __future__ import annotations

from io import BytesIO

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


def make_font_bytes(chars, *, fs_type=0, weight=400, italic=False, name="Test Font"):
    """A minimal but valid TTF covering ``chars``."""
    glyph_names = {char: f"uni{ord(char):04X}" for char in chars}
    glyph_order = [".notdef", *glyph_names.values()]

    pen = TTGlyphPen(None)
    pen.moveTo((50, 0))
    pen.lineTo((50, 700))
    pen.lineTo((650, 700))
    pen.lineTo((650, 0))
    pen.closePath()
    square = pen.glyph()

    builder = FontBuilder(unitsPerEm=1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap({ord(char): name for char, name in glyph_names.items()})
    builder.setupGlyf({glyph: square for glyph in glyph_order})
    builder.setupHorizontalMetrics({glyph: (700, 50) for glyph in glyph_order})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable(
        {
            "familyName": name,
            "styleName": "Italic" if italic else "Regular",
            "uniqueFontIdentifier": f"{name}-test",
            "fullName": name,
            "psName": name.replace(" ", ""),
            "version": "1.0",
        }
    )
    builder.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        usWinAscent=800,
        usWinDescent=200,
        fsType=fs_type,
        usWeightClass=weight,
        fsSelection=0x0001 if italic else 0x0040,
    )
    builder.setupPost()
    buffer = BytesIO()
    builder.save(buffer)
    return buffer.getvalue()


def sample_chars(count=260):
    """ASCII plus a run of common Chinese characters."""
    chars = [chr(code) for code in range(0x41, 0x5B)]
    code = 0x4E00
    while len(chars) < count:
        chars.append(chr(code))
        code += 1
    return chars
