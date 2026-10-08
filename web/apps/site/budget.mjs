// Homepage shell after the production build (12-architecture 6.9):
// rendered HTML + the entry script + stylesheets and scripts it preloads.
// Lazy route chunks (the style guide) are not part of the first page.
import { readFileSync } from "node:fs"
import { gzipSync } from "node:zlib"
import { join } from "node:path"

const JS_GZIP_MAX = 120 * 1024
const SHELL_GZIP_MAX = 300 * 1024

const dist = join(import.meta.dirname, "dist/client")
const manifest = JSON.parse(readFileSync(join(dist, ".vite/manifest.json"), "utf8"))
const { assetsFromManifest, handle, staticImgPath, staticImgRoot } = await import("./dist/server/server.js")
const imgRoot = staticImgRoot()
if (!staticImgPath("/static/img/placeholders/cover-07.svg", imgRoot)) {
  console.error("构建后的服务找不到 /static/img/placeholders/cover-07.svg")
  process.exit(1)
}
const assets = assetsFromManifest(manifest)
if (!assets?.entry) {
  console.error("清单里没有入口脚本")
  process.exit(1)
}

function gz(urlPath) {
  const rel = urlPath.replace(/^\//, "")
  return gzipSync(readFileSync(join(dist, rel))).length
}

const out = await handle(
  { method: "GET", url: "/", headers: { get: () => null } },
  {
    apiBase: "http://api.test",
    fetch: async () => new Response(JSON.stringify({ user: null }), { status: 200 }),
    assets,
  },
)
if (out.status !== 200) {
  console.error("首页渲染失败", out.status)
  process.exit(1)
}

const html = gzipSync(Buffer.from(out.body)).length
const scripts = [assets.entry, ...assets.preloads.filter((href) => href.endsWith(".js"))]
const styles = [...assets.css, ...assets.preloads.filter((href) => href.endsWith(".css"))]
const js = scripts.reduce((sum, href) => sum + gz(href), 0)
const css = styles.reduce((sum, href) => sum + gz(href), 0)
const shell = html + css + js
console.log(
  `首页壳 gzip：HTML ${html} + CSS ${css} + JS ${js} = ${shell} 字节（脚本上限 ${JS_GZIP_MAX}，合计上限 ${SHELL_GZIP_MAX}）`,
)
if (js > JS_GZIP_MAX || shell > SHELL_GZIP_MAX) process.exit(1)
console.log("BUDGET-OK")
