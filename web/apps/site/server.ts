import { createServer } from "node:http"
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs"
import { extname, join, resolve, sep } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { render, type Rendered, type RenderOpts } from "./src/entry-server"

const LOGIN = "/accounts/login/?next="
// 12-architecture 6.9, verbatim. Caddy sends this on every page; the
// standalone server sends it when STRICT_CSP=1.
export const CSP =
  "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self' https://player.bilibili.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

// 12-architecture 3.4: fixed addresses (icons, share images, old mail), one day.
export const STATIC_IMG = "/static/img/"
export const STATIC_IMG_CACHE = "public, max-age=86400"

export function staticImgRoot(): string {
  // Source lives in web/apps/site (three levels under the repo). The built
  // file is web/apps/site/dist/server (five). The process is started in the
  // site directory, so cwd is a third place to look.
  const starts = [fileURLToPath(new URL(".", import.meta.url)), process.cwd()]
  const rels = ["../../../static/img", "../../../../static/img", "../../../../../static/img"]
  for (const start of starts) {
    for (const rel of rels) {
      const dir = resolve(start, rel)
      if (existsSync(join(dir, "placeholders", "cover-07.svg"))) return dir
    }
  }
  return ""
}

export function staticImgPath(urlPath: string, root: string): string | null {
  if (!root) return null
  let pathname: string
  try {
    pathname = new URL(urlPath, "http://site").pathname
  } catch {
    return null
  }
  if (!pathname.startsWith(STATIC_IMG)) return null
  let rel: string
  try {
    rel = decodeURIComponent(pathname.slice(STATIC_IMG.length))
  } catch {
    return null
  }
  if (rel.includes("\0")) return null
  const file = resolve(root, rel)
  const base = resolve(root)
  if (file !== base && !file.startsWith(base + sep)) return null
  if (!existsSync(file) || !statSync(file).isFile()) return null
  return file
}

export function escapeState(value: unknown): string {
  return JSON.stringify(value)
    .replaceAll("<", "\\u003c")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029")
}

// What the Vite client manifest says this page needs: the entry chunk, its
// stylesheets and the chunks to preload. Null in dev, where the entry stays
// the source module and Vite's middleware serves everything.
export type Assets = { entry: string; css: string[]; preloads: string[] } | null

type ManifestEntry = { file: string; css?: string[]; imports?: string[]; isEntry?: boolean }

export function assetsFromManifest(manifest: Record<string, ManifestEntry>): Assets {
  // Vite keys the entry by index.html when the client build starts there (no
  // dynamic imports: entry-client lands in the same chunk), and by the source
  // module when the html is not the entry. Take either.
  const entry = manifest["src/entry-client.ts"] ?? Object.values(manifest).find((chunk) => chunk.isEntry)
  if (!entry?.file) return null
  const preloads: string[] = []
  for (const key of entry.imports ?? []) {
    const chunk = manifest[key]
    if (chunk?.file) preloads.push("/" + chunk.file)
    for (const css of chunk.css ?? []) preloads.push("/" + css)
  }
  return { entry: "/" + entry.file, css: (entry.css ?? []).map((href) => "/" + href), preloads }
}

export function documentHTML(parts: { head: string; html: string; state: unknown | null; assets: Assets }): string {
  const links = parts.assets
    ? [
        ...parts.assets.css.map((href) => `<link rel="stylesheet" href="${href}">`),
        ...parts.assets.preloads.map((href) => `<link rel="modulepreload" href="${href}">`),
      ].join("")
    : ""
  // state null marks the script-less pages (errors): no data block, no
  // entry script, no noscript banner — nothing to activate.
  const script =
    parts.state === null
      ? ""
      : `<script type="application/json" id="ow-state">${escapeState(parts.state)}</script>
${
  parts.assets
    ? `<script type="module" src="${parts.assets.entry}"></script>`
    : `<script type="module" src="/src/entry-client.ts"></script>`
}
<p class="c-nojs">页面脚本没有加载成功，部分按钮暂时用不了，请刷新</p>`
  return `<!doctype html>
<html lang="zh-Hans">
<head>
<script src="/theme.js"></script>
${parts.head}
${links}</head>
<body class="flex min-h-screen flex-col">
<div id="app">${parts.html}</div>
${script}
</body>
</html>
`
}

export type Incoming = { method: string; url: string; headers: { get(name: string): string | null } }

export async function handle(
  req: Incoming,
  opts: Pick<RenderOpts, "apiBase" | "fetch" | "load"> & { assets?: Assets },
): Promise<{ status: number; headers: Record<string, string>; body: string }> {
  const method = req.method.toUpperCase()
  if (method !== "GET" && method !== "HEAD") {
    return { status: 405, headers: { allow: "GET, HEAD" }, body: "" }
  }
  const rendered = await render(req.url, { ...opts, headers: req.headers })
  const out = toResponse(rendered, opts.assets ?? null)
  if (method === "HEAD") out.body = ""
  return out
}

function toResponse(rendered: Rendered, assets: Assets): { status: number; headers: Record<string, string>; body: string } {
  if (rendered.kind === "slash") return { status: 301, headers: { location: rendered.location }, body: "" }
  if (rendered.kind === "login") {
    return { status: 302, headers: { location: LOGIN + encodeURIComponent(rendered.next) }, body: "" }
  }
  const cache =
    rendered.status === 200 ? (rendered.viewer.user !== null ? "private, no-store" : "no-cache") : "no-store"
  return {
    status: rendered.status,
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": cache, vary: "Cookie" },
    body: documentHTML({ head: rendered.head, html: rendered.html, state: rendered.state, assets }),
  }
}

const MIME: Record<string, string> = {
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
}

// The standalone server also hands out the client build (in production
// Caddy does, from the assets volume; 12-architecture 3.4).
function serveStatic(req: { method?: string; url?: string }, res: import("node:http").ServerResponse, dist: string): boolean {
  if (req.method !== "GET" && req.method !== "HEAD") return false
  let pathname: string
  try {
    pathname = new URL(req.url ?? "/", "http://site").pathname
  } catch {
    return false
  }
  const imgFile = staticImgPath(req.url ?? "/", staticImgRoot())
  if (imgFile) {
    res.writeHead(200, {
      "content-type": MIME[extname(imgFile)] ?? "application/octet-stream",
      "cache-control": STATIC_IMG_CACHE,
    })
    if (req.method === "HEAD") res.end()
    else createReadStream(imgFile).pipe(res)
    return true
  }
  if (pathname !== "/theme.js" && !pathname.startsWith("/assets/")) return false
  const file = resolve(join(dist, decodeURIComponent(pathname.slice(1))))
  if (!file.startsWith(resolve(dist) + "/")) return false
  if (!existsSync(file) || !statSync(file).isFile()) return false
  res.writeHead(200, {
    "content-type": MIME[extname(file)] ?? "application/octet-stream",
    "cache-control": pathname.startsWith("/assets/") ? "public, max-age=31536000, immutable" : "no-cache",
  })
  if (req.method === "HEAD") {
    res.end()
  } else {
    createReadStream(file).pipe(res)
  }
  return true
}

const isMain = process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href
if (isMain) {
  const port = Number(process.env.PORT ?? 5173)
  const apiBase = process.env.API_BASE ?? "http://127.0.0.1:8080"
  const dist = join(process.cwd(), "dist/client")
  const manifestPath = join(dist, ".vite/manifest.json")
  const assets =
    process.env.NODE_ENV === "production" && existsSync(manifestPath)
      ? assetsFromManifest(JSON.parse(readFileSync(manifestPath, "utf8")) as Record<string, ManifestEntry>)
      : null
  const strict = process.env.STRICT_CSP === "1"
  console.log(`site ssr on :${port} (api ${apiBase}, ${assets ? "built assets" : "dev entry"})`)
  createServer((req, res) => {
    if (serveStatic(req, res, dist)) return
    if (req.url?.startsWith("/api/")) {
      fetch(apiBase + req.url, {
        method: req.method,
        headers: req.headers as HeadersInit,
      }).then(async (apiRes) => {
        const h: Record<string, string> = {}
        apiRes.headers.forEach((v, k) => { h[k] = v })
        res.writeHead(apiRes.status, h)
        res.end(Buffer.from(await apiRes.arrayBuffer()))
      }).catch(() => {
        res.writeHead(502)
        res.end()
      })
      return
    }
    const headers = {
      get(name: string) {
        const value = req.headers[name.toLowerCase()]
        return Array.isArray(value) ? (value[0] ?? null) : (value ?? null)
      },
    }
    handle({ method: req.method ?? "GET", url: req.url ?? "/", headers }, { apiBase, fetch, assets }).then((out) => {
      if (strict && (out.headers["content-type"] ?? "").startsWith("text/html")) {
        out.headers["content-security-policy"] = CSP
      }
      res.writeHead(out.status, out.headers)
      res.end(out.body)
    })
  }).listen(port)
}
