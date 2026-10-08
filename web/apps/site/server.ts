import { createServer } from "node:http"
import { pathToFileURL } from "node:url"
import { render, type Rendered, type RenderOpts } from "./src/entry-server"

const LOGIN = "/accounts/login/?next="

export function escapeState(value: unknown): string {
  return JSON.stringify(value)
    .replaceAll("<", "\\u003c")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029")
}

export function documentHTML(parts: { head: string; html: string; state: unknown }): string {
  return `<!doctype html>
<html lang="zh-Hans">
<head>
<script src="/theme.js"></script>
${parts.head}
</head>
<body>
<div id="app">${parts.html}</div>
<script type="application/json" id="ow-state">${escapeState(parts.state)}</script>
<script type="module" src="/src/entry-client.ts"></script>
<p class="c-nojs">页面脚本没有加载成功，部分按钮暂时用不了，请刷新</p>
</body>
</html>
`
}

export type Incoming = { method: string; url: string; headers: { get(name: string): string | null } }

export async function handle(req: Incoming, opts: Pick<RenderOpts, "apiBase" | "fetch" | "load">): Promise<{ status: number; headers: Record<string, string>; body: string }> {
  const method = req.method.toUpperCase()
  if (method !== "GET" && method !== "HEAD") {
    return { status: 405, headers: { allow: "GET, HEAD" }, body: "" }
  }
  const rendered = await render(req.url, { ...opts, headers: req.headers })
  const out = toResponse(rendered)
  if (method === "HEAD") out.body = ""
  return out
}

function toResponse(rendered: Rendered): { status: number; headers: Record<string, string>; body: string } {
  if (rendered.kind === "slash") return { status: 301, headers: { location: rendered.location }, body: "" }
  if (rendered.kind === "login") {
    return { status: 302, headers: { location: LOGIN + encodeURIComponent(rendered.next) }, body: "" }
  }
  const cache = rendered.status === 200 ? (rendered.loggedIn ? "private, no-store" : "no-cache") : "no-store"
  return {
    status: rendered.status,
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": cache, vary: "Cookie" },
    body: documentHTML({ head: rendered.head, html: rendered.html, state: { data: rendered.state } }),
  }
}

const isMain = process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href
if (isMain) {
  const port = Number(process.env.PORT ?? 5173)
  const apiBase = process.env.API_BASE ?? "http://127.0.0.1:8080"
  createServer((req, res) => {
    const headers = {
      get(name: string) {
        const value = req.headers[name.toLowerCase()]
        return Array.isArray(value) ? (value[0] ?? null) : (value ?? null)
      },
    }
    handle({ method: req.method ?? "GET", url: req.url ?? "/", headers }, { apiBase, fetch }).then((out) => {
      res.writeHead(out.status, out.headers)
      res.end(out.body)
    })
  }).listen(port)
}
