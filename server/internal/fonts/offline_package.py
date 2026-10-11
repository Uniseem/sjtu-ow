#!/usr/bin/env python3
"""Build a D4 font ZIP offline; this tool is never called by the Go server.

Example:
  python offline_package.py --family 'My Font' --face '400:normal:font.ttf' \
      --license-file OFL.txt --allow-web-embedding --output font-package.zip

Requires the repository's existing fontTools and Brotli Python environment.
Inputs are local files only. Google Fonts download is handled by Go instead.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import zipfile

MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_PACKAGE_BYTES = 64 * 1024 * 1024
MAX_SLICE_BYTES = 8 * 1024 * 1024
MAX_SLICES = 1024
BASIC_RANGES = (
    (0x20, 0xFF), (0x100, 0x24F), (0x2000, 0x206F),
    (0x20A0, 0x20BF), (0x2190, 0x21FF), (0x2460, 0x24FF),
    (0x25A0, 0x25FF), (0x3000, 0x303F), (0xFE30, 0xFE4F),
    (0xFF00, 0xFFEF),
)
CJK_RANGES = (
    (0x2E80, 0x2FDF), (0x31C0, 0x31EF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x3FFFD),
)


class PackageError(ValueError):
    pass


def in_ranges(codepoint: int, ranges: tuple) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def common_hanzi(codepoint: int) -> bool:
    try:
        encoded = chr(codepoint).encode("gb2312")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False
    return len(encoded) == 2 and 0xB0 <= encoded[0] <= 0xD7


def chunks(items: list[int], size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def groups(codepoints: list[int]):
    basic, common, cjk, other = [], [], [], []
    for point in sorted(set(codepoints)):
        if in_ranges(point, BASIC_RANGES):
            basic.append(point)
        elif in_ranges(point, CJK_RANGES):
            (common if common_hanzi(point) else cjk).append(point)
        else:
            other.append(point)
    yield from chunks(basic, 600)
    yield from chunks(common, 200)
    yield from chunks(cjk, 600)
    yield from chunks(other, 600)


def unicode_range(points: list[int]) -> str:
    def run(first: int, last: int) -> str:
        return f"U+{first:X}" if first == last else f"U+{first:X}-{last:X}"
    if not points:
        return ""
    values = sorted(set(points))
    first = previous = values[0]
    result = []
    for value in values[1:]:
        if value != previous + 1:
            result.append(run(first, previous))
            first = value
        previous = value
    result.append(run(first, previous))
    return ",".join(result)


def parse_face(value: str) -> tuple[int, str, Path]:
    pieces = value.split(":", 2)
    if len(pieces) != 3:
        raise PackageError("字重格式应为 WEIGHT:normal|italic:PATH")
    try:
        weight = int(pieces[0])
    except ValueError as error:
        raise PackageError("字重必须为100至900的整百数") from error
    if weight < 100 or weight > 900 or weight % 100:
        raise PackageError("字重必须为100至900的整百数")
    if pieces[1] not in {"normal", "italic"}:
        raise PackageError("样式只接受normal或italic")
    path = Path(pieces[2]).expanduser()
    if not path.is_file() or path.is_symlink():
        raise PackageError(f"字体不是普通本地文件：{path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise PackageError("单个字体源文件不能超过20MB")
    return weight, pieces[1], path


def check_embedding(font) -> None:
    if "OS/2" not in font:
        return
    flags = int(font["OS/2"].fsType)
    if flags & 0x0002:
        raise PackageError("该字体标记为禁止嵌入，不能制作网页成品包")
    if flags & 0x0100:
        raise PackageError("该字体不允许分片，不能制作分片成品包")
    if flags & 0x0200:
        raise PackageError("该字体只允许位图嵌入，不能制作网页成品包")


def subset_bytes(source: bytes, points: list[int]) -> bytes:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    font = TTFont(io.BytesIO(source), recalcTimestamp=False)
    try:
        options = subset.Options()
        options.flavor = "woff2"
        options.recalc_timestamp = False
        options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]
        options.layout_features = ["*"]
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=points)
        subsetter.subset(font)
        font.flavor = "woff2"
        result = io.BytesIO()
        font.save(result)
        data = result.getvalue()
    finally:
        font.close()
    if not data.startswith(b"wOF2") or len(data) < 48:
        raise PackageError("无法生成有效WOFF2分片")
    if len(data) > MAX_SLICE_BYTES:
        raise PackageError("单个分片超过8MB")
    return data


def build(family: str, display: str, license_text: str, faces: list[tuple]):
    from fontTools.ttLib import TTFont
    manifest = {
        "version": 1,
        "family": family,
        "display_name": display or family,
        "license": license_text,
        "license_confirmed": True,
        "faces": [],
    }
    files = {}
    total = 0
    count = 0
    seen = set()
    for weight, style, path in faces:
        if (weight, style) in seen:
            raise PackageError("字重和样式不能重复")
        seen.add((weight, style))
        source = path.read_bytes()
        font = TTFont(io.BytesIO(source), recalcTimestamp=False)
        try:
            check_embedding(font)
            mapping = font.getBestCmap() or {}
            if not mapping:
                raise PackageError("字体没有Unicode字符映射")
            points = list(mapping)
        finally:
            font.close()
        face = {"weight": weight, "style": style, "slices": [], "bytes": 0}
        for index, group in enumerate(groups(points)):
            data = subset_bytes(source, group)
            count += 1
            total += len(data)
            if count > MAX_SLICES or total > MAX_PACKAGE_BYTES:
                raise PackageError("成品包超过1024分片或64MB上限")
            name = f"slices/{weight}-{style}-{index:04d}.woff2"
            files[name] = data
            face["slices"].append({
                "path": name,
                "unicode_range": unicode_range(group),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            })
            face["bytes"] += len(data)
        manifest["faces"].append(face)
    files["manifest.json"] = json.dumps(
        manifest, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    files["LICENSE.txt"] = license_text.encode("utf-8")
    return files


def write_package(output: Path, files: dict[str, bytes]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".font-package-", dir=output.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(files):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                archive.writestr(info, files[name])
        if os.path.getsize(temporary) > MAX_PACKAGE_BYTES:
            raise PackageError("成品包ZIP超过64MB")
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True)
    parser.add_argument("--display-name", default="")
    parser.add_argument("--face", action="append", required=True)
    parser.add_argument("--license-file", type=Path, required=True)
    parser.add_argument("--allow-web-embedding", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        family = arguments.family.strip()
        if not family or len(family) > 120:
            raise PackageError("家族名称必须为1至120字")
        if len(arguments.display_name) > 64:
            raise PackageError("显示名称不能超过64字")
        if not arguments.allow_web_embedding:
            raise PackageError("必须显式确认允许网页嵌入")
        license_text = arguments.license_file.read_text(encoding="utf-8").strip()
        if not license_text or len(license_text.encode("utf-8")) > 10000:
            raise PackageError("授权说明为空或超过10000字节")
        faces = [parse_face(value) for value in arguments.face]
        if len(faces) > 18:
            raise PackageError("每个成品包最多18组字重和样式")
        files = build(family, arguments.display_name, license_text, faces)
        write_package(arguments.output, files)
        print(f"已写入字体成品包：{arguments.output.resolve()}")
    except (PackageError, OSError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
