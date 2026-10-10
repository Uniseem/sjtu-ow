"""264：拆掉旧图导入的守卫，确认测试会红，再改回来（硬规则 7）。

    bash scripts/remote-check.sh run bash -c 'export PATH=/srv/sjtu-ow-check/go/bin:$PATH; python3 handoff/rounds/264-f1-image-masters-parity/mutate.py'
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILE = ROOT / "server/internal/platform/media/import.go"
TEST = ["go", "test", "-count=1", "-run", "TestImportLegacyMasters|TestMediaUploadAndThumbnail", "./internal/platform/media/"]

CASES = [
    (
        "越出媒体目录的文件名也照读",
        "\tif full != root && !strings.HasPrefix(full, root+string(filepath.Separator)) {\n\t\treturn \"\", false\n\t}\n",
        "",
    ),
    (
        "找不到原图当成做好了",
        '\t\t\trep.Missing = append(rep.Missing, fmt.Sprintf("%d %s", r.id, r.file))\n',
        "\t\t\trep.Made++\n",
    ),
    (
        "已有母版不跳过",
        "\t\tif _, err := os.Stat(s.MasterPath(r.id)); err == nil {\n\t\t\trep.Skipped++\n\t\t\tcontinue\n\t\t}\n",
        "",
    ),
    (
        "坏文件不报",
        '\t\t\trep.Failed = append(rep.Failed, fmt.Sprintf("%d %s：读不出图头", r.id, r.file))\n',
        "",
    ),
]


def run():
    return subprocess.run(TEST, cwd=ROOT / "server", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def main():
    original = FILE.read_text(encoding="utf-8")
    if run() != 0:
        sys.exit("基线不是绿的，先修测试")
    print("基线全绿")
    try:
        for name, old, new in CASES:
            if original.count(old) != 1:
                sys.exit(f"要改的原文出现了 {original.count(old)} 次：{name}")
            FILE.write_text(original.replace(old, new, 1), encoding="utf-8")
            code = run()
            FILE.write_text(original, encoding="utf-8")
            if code == 0:
                sys.exit(f"没抓到：{name}")
            print(f"抓到 {name}（退出码 {code}）")
    finally:
        FILE.write_text(original, encoding="utf-8")
    if run() != 0:
        sys.exit("改回来之后不是绿的")
    print(f"{len(CASES)} 处全抓到，已改回")


if __name__ == "__main__":
    main()
