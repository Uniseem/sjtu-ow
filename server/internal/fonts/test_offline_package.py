"""Offline D4 tool acceptance; run with the repository's existing fontTools env.

These tests create an actual small TTF and decode the generated WOFF2. They do
not require a system font, external download, credentials, or production media.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

import offline_package as tool


class OfflinePackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def font(self, fs_type=0):
        builder = FontBuilder(1024, isTTF=True)
        builder.setupGlyphOrder([".notdef", "space", "A"])
        builder.setupCharacterMap({32: "space", 65: "A"})
        pen = TTGlyphPen(None)
        pen.moveTo((100, 0))
        pen.lineTo((500, 800))
        pen.lineTo((900, 0))
        pen.closePath()
        letter = pen.glyph()
        blank = TTGlyphPen(None).glyph()
        builder.setupGlyf({".notdef": blank, "space": blank, "A": letter})
        builder.setupHorizontalMetrics({name: (1024, 0) for name in [".notdef", "space", "A"]})
        builder.setupHorizontalHeader(ascent=800, descent=-224)
        builder.setupNameTable({
            "familyName": "D4Fixture", "styleName": "Regular",
            "uniqueFontIdentifier": "D4Fixture-Regular", "fullName": "D4Fixture Regular",
            "psName": "D4Fixture-Regular", "version": "Version 1.0",
        })
        builder.setupOS2(sTypoAscender=800, sTypoDescender=-224, usWinAscent=800, usWinDescent=224, fsType=fs_type)
        builder.setupPost()
        target = self.root / "fixture.ttf"
        builder.save(target)
        return target

    def test_generated_package_preserves_real_unicode_glyphs_and_hashes(self):
        source = self.font()
        files = tool.build("D4Fixture", "D4测试字体", "OFL fixture license", [(400, "normal", source)])
        output = self.root / "finished.zip"
        tool.write_package(output, files)
        with zipfile.ZipFile(output) as package:
            manifest = json.loads(package.read("manifest.json"))
            self.assertEqual(manifest["version"], 1)
            self.assertTrue(manifest["license_confirmed"])
            self.assertEqual(manifest["license"], "OFL fixture license")
            self.assertEqual(manifest["family"], "D4Fixture")
            seen = set()
            for face in manifest["faces"]:
                self.assertEqual(face["weight"], 400)
                self.assertEqual(face["style"], "normal")
                self.assertEqual(face["bytes"], sum(item["bytes"] for item in face["slices"]))
                for item in face["slices"]:
                    data = package.read(item["path"])
                    self.assertEqual(len(data), item["bytes"])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
                    self.assertTrue(data.startswith(b"wOF2"))
                    font = TTFont(io.BytesIO(data))
                    try:
                        seen.update(font.getBestCmap())
                    finally:
                        font.close()
            self.assertIn(65, seen)
            self.assertIn(32, seen)
            self.assertEqual(package.read("LICENSE.txt").decode(), "OFL fixture license")

    def test_package_is_deterministic_for_identical_inputs(self):
        source = self.font()
        files = tool.build("D4Fixture", "D4测试字体", "OFL fixture license", [(400, "normal", source)])
        first = self.root / "first.zip"
        second = self.root / "second.zip"
        tool.write_package(first, files)
        tool.write_package(second, files)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_embedding_restricted_font_is_rejected(self):
        source = self.font(fs_type=0x0002)
        with self.assertRaises(tool.PackageError):
            tool.build("D4Fixture", "测试", "OFL fixture license", [(400, "normal", source)])

    def test_no_subsetting_flag_is_rejected(self):
        source = self.font(fs_type=0x0100)
        with self.assertRaises(tool.PackageError):
            tool.build("D4Fixture", "测试", "OFL fixture license", [(400, "normal", source)])

    def test_duplicate_face_is_rejected(self):
        source = self.font()
        with self.assertRaises(tool.PackageError):
            tool.build("D4Fixture", "测试", "OFL fixture license", [(400, "normal", source), (400, "normal", source)])

    def test_local_file_parser_rejects_symlink_and_invalid_weight(self):
        source = self.font()
        link = self.root / "linked.ttf"
        link.symlink_to(source)
        with self.assertRaises(tool.PackageError):
            tool.parse_face(f"400:normal:{link}")
        with self.assertRaises(tool.PackageError):
            tool.parse_face(f"450:normal:{source}")
        with self.assertRaises(tool.PackageError):
            tool.parse_face(f"400:oblique:{source}")


if __name__ == "__main__":
    unittest.main()
