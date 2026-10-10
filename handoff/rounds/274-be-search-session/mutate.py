"""All mutations must compile and fail a regression; run on the test machine."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
server = root / "server"
mutations = [
    ("query cap", "internal/search/service.go", "q = q[:50]", "q = q[:]", "search"),
    ("five terms", "internal/search/service.go", "terms = terms[:5]", "terms = terms[:]", "search"),
    ("all terms", "internal/search/service.go", "if !strings.Contains(folded, term) {\n\t\t\treturn false", "if !strings.Contains(folded, term) {\n\t\t\treturn true", "search"),
    ("Unicode fold", "internal/search/service.go", "folded := caseFold(text)", "folded := strings.ToLower(text)", "search"),
    ("public articles", "internal/search/service.go", "AND p.search_public=1", "AND 1=1", "search"),
    ("draft articles", "internal/search/service.go", "AND p.live=1", "AND p.live IN (0,1)", "search"),
    ("cancelled events", "internal/search/service.go", "status IN ('published','finished')", "status IN ('published','finished','cancelled')", "search"),
    ("last publication order", "internal/search/service.go", "ORDER BY p.last_published_at DESC", "ORDER BY p.first_published_at DESC", "search"),
    ("twenty per group", "internal/search/service.go", "const perTypeLimit = 20", "const perTypeLimit = 21", "search"),
    ("truncation signal", "internal/search/service.go", "g.Truncated = true", "g.Truncated = false", "search"),
    ("member nickname only", "internal/search/service.go", "!matches(item.Nickname, terms)", '!matches(item.Nickname+"\\n"+item.Motto, terms)', "search"),
    ("session email conflation", "internal/accounts/api.go", "CanSubmitArticle: ctx.Viewer.CanUse(FeatureArticleSubmit)", "CanSubmitArticle: ctx.Viewer.EmailVerified && ctx.Viewer.CanUse(FeatureArticleSubmit)", "accounts"),
    ("session feature ban", "internal/accounts/api.go", "CanSubmitArticle: ctx.Viewer.CanUse(FeatureArticleSubmit)", "CanSubmitArticle: true", "accounts"),
    ("inherited restrictions", "internal/content/import.go", "WHERE substr(p.path, 1, length(restricted.path)) = restricted.path", "WHERE 0", "content"),
    ("HTTP rate limit", "internal/search/api.go", "api.Limit(ratelimit.Search)", "api.Limit(func() ratelimit.Decl { d := ratelimit.Search; d.N = 300; return d }())", "search"),
]
for name, rel, old, new, module in mutations:
    p = server / rel
    baseline = p.read_text()
    if old not in baseline:
        raise SystemExit(f"missing anchor: {name}")
    try:
        p.write_text(baseline.replace(old, new, 1))
        vet = subprocess.run(["go", "vet", f"./internal/{module}"], cwd=server, capture_output=True, text=True)
        if vet.returncode:
            raise SystemExit(f"INVALID {name}: {vet.stderr}")
        regex = {"search":"TestSearch", "accounts":"TestSessionSubmit", "content":"TestImportArticleSearchPublic"}[module]
        result = subprocess.run(["go", "test", f"./internal/{module}", "-run", regex, "-count=1"], cwd=server, capture_output=True, text=True)
        if not result.returncode:
            raise SystemExit(f"SURVIVED {name}")
        print(f"CAUGHT {name}", flush=True)
    finally:
        p.write_text(baseline)
print(f"MUTATIONS-OK {len(mutations)}", flush=True)
