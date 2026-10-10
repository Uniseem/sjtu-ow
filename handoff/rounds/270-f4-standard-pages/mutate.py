"""270: break each rule the content pages follow; the SSR tests must go red.

Run on the test machine: bash scripts/remote-check.sh run python3 handoff/rounds/270-f4-standard-pages/mutate.py
Each mutation's text must occur exactly once (AGENTS: a mutation that lands
elsewhere looks like a miss).
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / "web/apps/site/src"
mutations = [
    (SITE / "pages/StandardPage.vue", ":aria-current=\"route.path === tab.href ? 'page' : undefined\"", ":aria-current=\"undefined\"", "current about tab"),
    (SITE / "pages/StandardPage.vue", "title: page.seo_title || page.title", "title: page.title", "SEO title wins"),
    (SITE / "pages/StandardPage.vue", '<p v-if="updated" class="c-article__meta">', '<p class="c-article__meta">', "no update line without a date"),
    (SITE / "routes.ts", '"/:slug([\\\\w%\\\\u0080-\\\\uffff-]+)/"', '"/:slug([^/]+)/"', "slug never has a dot"),
    (SITE / "meta.ts", "`${text} · ${SITE_NAME}`", "`${text} - ${SITE_NAME}`", "document title format"),
    (SITE / "pages/Search.vue", "terms.length ? (await searchSite(ctx.api, query)).groups : []", "(await searchSite(ctx.api, query)).groups", "empty query does not call Go"),
    (SITE / "pages/Search.vue", "(raw ?? \"\").trim().slice(0, MAX_QUERY_LENGTH)", "(raw ?? \"\").trim()", "query cut to 50"),
    (SITE / "pages/Search.vue", ':aria-labelledby="`search-${index + 1}`"', ':aria-labelledby="`search-${index}`"', "group ids count every group"),
    (SITE / "pages/Search.vue", '<p v-if="group.truncated"', '<p v-if="true"', "20-hit note only when cut"),
    (SITE / "pages/Submit.vue", "  if (!reasons.length) throw new PageRedirect(ARTICLE_NEW, 302)\n", "", "contributor goes to the editor"),
    (SITE / "pages/Submit.vue", "user.email_verified ? !contributor : user.can_submit_article === false", "!contributor", "unverified is not also called banned"),
    (SITE / "entry-server.ts", "viewer: () => session,", "viewer: () => fetchSession(api),", "load shares the page's session call"),
]
env = dict(os.environ, PATH="/srv/sjtu-ow-check/node24/bin:" + os.environ.get("PATH", ""))
command = ["pnpm", "--filter", "@sjtu-ow/site", "exec", "vitest", "run", "src/content.test.ts", "src/guards.test.ts"]


def run():
    return subprocess.run(command, cwd=ROOT / "web", text=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


subprocess.run(["pnpm", "install", "--frozen-lockfile"], cwd=ROOT / "web", env=env, check=True, stdout=subprocess.DEVNULL)
base = run()
if base.returncode:
    print(base.stdout)
    raise SystemExit("baseline failed")
for path, old, new, name in mutations:
    original = path.read_text()
    count = original.count(old)
    if count != 1:
        raise SystemExit(f"{name}: expected the text once, found {count}")
    try:
        path.write_text(original.replace(old, new))
        result = run()
        if result.returncode == 0 or "FAIL " not in result.stdout:
            print(result.stdout)
            raise SystemExit(f"NOT CAUGHT: {name}")
        print(f"CAUGHT {name}", flush=True)
    finally:
        path.write_text(original)
final = run()
if final.returncode:
    print(final.stdout)
    raise SystemExit("restored baseline failed")
print(f"MUTATIONS-OK {len(mutations)}; restored baseline green")
