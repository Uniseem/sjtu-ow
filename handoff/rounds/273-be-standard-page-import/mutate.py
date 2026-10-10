"""Run only on the test machine; each mutation must fail the focused regressions."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
server = root / "server"
mutations = [
    ("wrong legacy table", "internal/content/import.go", "FROM content_standardpage sp", "FROM content_sitepage sp"),
    ("lost SEO", "internal/content/api.go", "SeoTitle:          sp.SeoTitle,", 'SeoTitle:          "",'),
    ("lost last publication", "internal/content/store.go", "sp.LastPublishedAt = &t", "_ = t"),
    ("swallowed inserts", "internal/content/import.go", 'return fmt.Errorf("写普通页正文 %d: %w", id, err)', "return nil"),
    ("swallowed scan", "internal/content/import.go", 'return fmt.Errorf("3. 导入文章分类 (content_articlecategory -> article_categories)：扫描失败: %w", err)', "return nil"),
    ("swallowed iteration", "internal/content/import.go", "return rows.Err()", "return nil"),
]
for name, rel, old, new in mutations:
    p = server / rel
    baseline = p.read_text()
    if old not in baseline:
        raise SystemExit(f"mutation anchor missing: {name}")
    try:
        p.write_text(baseline.replace(old, new, 1))
        vet = subprocess.run(["go", "vet", "./internal/content"], cwd=server, capture_output=True, text=True)
        if vet.returncode:
            raise SystemExit(f"INVALID {name}: {vet.stderr}")
        test = subprocess.run(["go", "test", "./internal/content", "-run", "TestImport(Standard|Content)", "-count=1"], cwd=server, capture_output=True, text=True)
        if not test.returncode:
            raise SystemExit(f"SURVIVED {name}")
        print(f"CAUGHT {name}", flush=True)
    finally:
        p.write_text(baseline)
print(f"MUTATIONS-OK {len(mutations)}", flush=True)
