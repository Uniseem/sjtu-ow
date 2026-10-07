# ruff: noqa: E501
"""Round 219 mutation check: every guard this round adds must turn red when
broken. Baseline first (083's lesson): if the baseline is red, stop.

Run on the test machine:
  bash scripts/remote-check.sh run uv run python handoff/rounds/219-upload-pipeline/mutate.py
Only some mutations: pass words from their names as arguments.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

UPLOAD = "core/tests/test_upload_pipeline.py"
LOGO = "teams/tests/test_logo_pipeline.py"
SCRUB = "core/tests/test_scrub_originals.py"

# (name, file, old, new, tests that must go red, replace all occurrences?)
MUTATIONS = [
    (
        "管线 不转正",
        "core/uploads.py",
        "            picture = ImageOps.exif_transpose(picture)\n",
        "",
        [UPLOAD],
        False,
    ),
    (
        "管线 不查像素",
        "core/uploads.py",
        "            if width * height > max_pixels:",
        "            if False:",
        [UPLOAD],
        False,
    ),
    (
        "管线 不查格式",
        "core/uploads.py",
        "            if picture.format not in IMAGE_FORMATS:",
        "            if False:",
        [UPLOAD],
        False,
    ),
    (
        "管线 不缩小",
        "core/uploads.py",
        "    if max(picture.size) > max_side:",
        "    if False:",
        [UPLOAD],
        False,
    ),
    (
        "管线 文件名不随机",
        "core/uploads.py",
        'name=f"upload-{secrets.token_hex(10)}.webp"',
        'name="upload.webp"',
        [UPLOAD],
        False,
    ),
    (
        "管线 洗过的又洗一遍",
        "core/uploads.py",
        "    if isinstance(uploaded, CleanImage):",
        "    if False:",
        [UPLOAD],
        False,
    ),
    (
        "限次 超管也限",
        "core/uploads.py",
        '    if getattr(user, "is_superuser", False):\n        return None\n',
        "",
        [UPLOAD],
        False,
    ),
    (
        "限次 编辑和成员一个数",
        "core/uploads.py",
        "    if user.groups.filter(name=EDITOR_GROUP).exists():",
        "    if False:",
        [UPLOAD],
        False,
    ),
    (
        "限次 不计数",
        "core/uploads.py",
        '    return over_limit(f"upload:{user.pk}", limit, 86400)',
        "    return False",
        [UPLOAD, LOGO],
        False,
    ),
    (
        "入口 Wagtail 表单不过管线",
        "core/image_forms.py",
        "            cleaned = clean_image(uploaded)",
        "            cleaned = uploaded",
        [UPLOAD],
        False,
    ),
    (
        "入口 Wagtail 表单不限次",
        "core/image_forms.py",
        "        if self.uploader is not None and over_daily_limit(self.uploader):",
        "        if False:",
        [UPLOAD],
        False,
    ),
    (
        "入口 设置里不指向安全表单",
        "sjtu_ow/settings/base.py",
        'WAGTAILIMAGES_IMAGE_FORM_BASE = "core.image_forms.SafeImageForm"\n',
        "",
        [UPLOAD],
        False,
    ),
    (
        "入口 Wagtail 像素上限放回 1.28 亿",
        "sjtu_ow/settings/base.py",
        "WAGTAILIMAGES_MAX_IMAGE_PIXELS = 40_000_000",
        "WAGTAILIMAGES_MAX_IMAGE_PIXELS = 128_000_000",
        [UPLOAD],
        False,
    ),
    (
        "队标 表单不过管线",
        "teams/forms.py",
        "            cleaned = clean_logo(uploaded)",
        "            cleaned = uploaded",
        [LOGO],
        False,
    ),
    (
        "队标 表单不限次",
        "teams/forms.py",
        "        if self.user is not None and over_daily_limit(self.user):",
        "        if False:",
        [LOGO],
        False,
    ),
    (
        "队标 不放进队标集合",
        "teams/images.py",
        "        collection=ensure_team_logo_collection(),\n",
        "",
        [LOGO],
        False,
    ),
    (
        "队标 换了不删旧的",
        "teams/services.py",
        "        transaction.on_commit(lambda: discard_logo(old_logo))",
        "        pass",
        [LOGO],
        False,
    ),
    (
        "队标 别的队还在用也删",
        "teams/images.py",
        "    if Team.objects.filter(logo=image).exists():\n        return\n",
        "",
        [LOGO],
        False,
    ),
    (
        "队标 不是队标集合里的也删",
        "teams/images.py",
        "    if image is None or image.collection.name != TEAM_LOGO_COLLECTION:",
        "    if image is None:",
        [LOGO],
        False,
    ),
    (
        "历史 不删旧文件",
        "core/management/commands/scrub_originals.py",
        "        storage.delete(old_name)\n",
        "",
        [SCRUB],
        False,
    ),
    (
        "历史 干净的也重编",
        "core/management/commands/scrub_originals.py",
        "            if not has_any:",
        "            if False:",
        [SCRUB],
        False,
    ),
    (
        "历史 预演也动手",
        "core/management/commands/scrub_originals.py",
        '                self.stdout.write(f"#{image.pk} {image.title}（{tag}）")\n                continue\n',
        '                self.stdout.write(f"#{image.pk} {image.title}（{tag}）")\n',
        [SCRUB],
        False,
    ),
    (
        "历史 队标不搬家",
        "core/management/commands/scrub_originals.py",
        "            image.collection = ensure_team_logo_collection()\n            image.save(update_fields=[\"collection\"])\n",
        "            pass\n",
        [SCRUB],
        False,
    ),
    (
        "历史 不限定集合",
        "core/management/commands/scrub_originals.py",
        '        if not options["all"]:',
        "        if False:",
        [SCRUB],
        False,
    ),
]

if len(sys.argv) > 1:
    MUTATIONS = [m for m in MUTATIONS if any(word in m[0] for word in sys.argv[1:])]

BASELINE = sorted({test for m in MUTATIONS for test in m[4]})


def run(tests):
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *tests],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-6:])
        print(f"    ---- 输出尾巴 ----\n{tail}")
    return result.returncode


def main():
    print("基线：", flush=True)
    if run(BASELINE) != 0:
        print("基线就是红的，停下（083 的教训）。")
        return 1
    print("基线全绿，开始变异。\n", flush=True)
    bad = 0
    for name, filename, old, new, tests, everywhere in MUTATIONS:
        path = ROOT / filename
        original = path.read_text(encoding="utf-8")
        found = original.count(old)
        if found == 0 or (found > 1 and not everywhere):
            # 216 的坑：改坏的那行出现不止一次时，replace(.., 1) 会改到别处
            print(f"!! {name}：要改坏的代码在 {filename} 里出现 {found} 次，跳过")
            bad += 1
            continue
        backup = path.with_suffix(path.suffix + ".bak218")
        shutil.copy2(path, backup)
        try:
            path.write_text(original.replace(old, new), encoding="utf-8")
            code = run(tests)
            if code == 0:
                print(f"!! {name}：改坏后测试仍然全绿 —— 没抓到", flush=True)
                bad += 1
            else:
                print(f"ok {name}：改坏后红了", flush=True)
        finally:
            shutil.move(backup, path)
            # 027 的坑：mtime/size 没变时清掉缓存再跑
            for cache in path.parent.glob(f"__pycache__/{path.stem}.*"):
                cache.unlink()
    print()
    if run(BASELINE) != 0:
        print("!! 改回之后基线红了，有文件没恢复好")
        return 1
    print("改回后基线全绿。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
