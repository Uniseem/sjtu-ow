"""The project's own translations (round 117).

Wagtail 8's Chinese catalog misses a hundred-odd admin strings, so the
project ships its own in ``locale/zh_Hans/LC_MESSAGES/`` (``LOCALE_PATHS``
entries win over the apps' catalogs). The ``.mo`` files are compiled here
with the standard library, so nobody needs GNU gettext installed; both the
``.po`` and the ``.mo`` are committed, and a test keeps them in step.
"""

from __future__ import annotations

import ast
import struct
from pathlib import Path

MAGIC = 0x950412DE
CONTEXT_SEPARATOR = "\x04"


def _entries(text: str):
    """Yield each entry of a .po file as {keyword: string}."""
    entry: dict[str, str] = {}
    keyword = None
    for raw in text.splitlines() + [""]:
        line = raw.strip()
        if not line:
            if entry:
                yield entry
            entry, keyword = {}, None
            continue
        if line.startswith("#"):
            continue
        if line.startswith('"'):
            if keyword is None:
                raise ValueError(f"续行前没有关键字：{raw}")
            entry[keyword] += ast.literal_eval(line)
            continue
        keyword, _, rest = line.partition(" ")
        if keyword in entry:
            raise ValueError(f"一条里出现两次 {keyword}：{raw}")
        entry[keyword] = ast.literal_eval(rest.strip())


def parse_po(text: str) -> dict[str, str]:
    """The catalog as a .mo stores it: ``context\\x04msgid`` keys, plural
    keys and values joined by NUL. Untranslated entries are left out."""
    catalog: dict[str, str] = {}
    for entry in _entries(text):
        msgid = entry.get("msgid")
        if msgid is None:
            raise ValueError(f"没有 msgid 的一条：{entry}")
        if "msgid_plural" in entry:
            forms = []
            index = 0
            while f"msgstr[{index}]" in entry:
                forms.append(entry[f"msgstr[{index}]"])
                index += 1
            if not forms or not all(forms):
                continue
            key = msgid + "\x00" + entry["msgid_plural"]
            value = "\x00".join(forms)
        else:
            value = entry.get("msgstr", "")
            if not value:
                continue
            key = msgid
        if "msgctxt" in entry:
            key = entry["msgctxt"] + CONTEXT_SEPARATOR + key
        catalog[key] = value
    return catalog


def build_mo(catalog: dict[str, str]) -> bytes:
    """GNU .mo bytes for a catalog, little-endian, keys sorted, no hash
    table (Python's gettext doesn't use one), so the output is stable."""
    keys = sorted(catalog, key=lambda key: key.encode("utf-8"))
    ids = b""
    strs = b""
    spans = []
    for key in keys:
        msgid = key.encode("utf-8")
        msgstr = catalog[key].encode("utf-8")
        spans.append((len(msgid), len(ids), len(msgstr), len(strs)))
        ids += msgid + b"\x00"
        strs += msgstr + b"\x00"
    count = len(keys)
    ids_table = 7 * 4
    strs_table = ids_table + count * 8
    ids_start = strs_table + count * 8
    strs_start = ids_start + len(ids)
    header = struct.pack("<7I", MAGIC, 0, count, ids_table, strs_table, 0, 0)
    id_offsets = b"".join(
        struct.pack("<2I", length, ids_start + offset) for length, offset, _, _ in spans
    )
    str_offsets = b"".join(
        struct.pack("<2I", length, strs_start + offset)
        for _, _, length, offset in spans
    )
    return header + id_offsets + str_offsets + ids + strs


def po_files(locale_dirs) -> list[Path]:
    found = []
    for directory in locale_dirs:
        found.extend(sorted(Path(directory).glob("*/LC_MESSAGES/*.po")))
    return found


def compiled(po_path: Path) -> bytes:
    return build_mo(parse_po(po_path.read_text(encoding="utf-8")))
