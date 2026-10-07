// The "thin SSR server" of 12-architecture 6.2 in one file: static files, the
// SSR render, and a stand-in for the Go API. Strict CSP on every response.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const client = join(root, "dist/client");
const PORT = Number(process.env.PORT ?? 5173);
const CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self' https://player.bilibili.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'";
const types = { ".js": "text/javascript", ".css": "text/css", ".html": "text/html; charset=utf-8", ".json": "application/json", ".map": "application/json" };

const teams = Array.from({ length: 6 }, (_, i) => ({ id: i + 1, name: `交大战队 ${i + 1}`, members: 5 + i, founded: `2026-0${(i % 9) + 1}-15T04:30:00Z` }));
const template = await readFile(join(client, "index.html"), "utf8");
const { render } = await import(pathToFileURL(join(root, "dist/server/entry-server.js")));

const escapeState = (value) =>
  JSON.stringify(value)
    .replace(/</g, "\\u003c")
    .replace(new RegExp(String.fromCharCode(0x2028), "g"), "\\u2028")
    .replace(new RegExp(String.fromCharCode(0x2029), "g"), "\\u2029");

createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const send = (status, body, type = "text/html; charset=utf-8", extra = {}) => {
    res.writeHead(status, { "content-type": type, "content-security-policy": CSP, ...extra });
    res.end(body);
  };
  if (url.pathname === "/api/page/home") return send(200, JSON.stringify({ title: "SSR 实验", teams, now: new Date().toISOString() }), types[".json"]);
  const team = url.pathname.match(/^\/api\/page\/team\/(\d+)$/);
  if (team) {
    const row = teams.find((t) => t.id === Number(team[1]));
    return row ? send(200, JSON.stringify({ ...row, description: "一支用来做实验的战队。" }), types[".json"]) : send(404, "{}", types[".json"]);
  }
  const file = join(client, url.pathname);
  if (url.pathname.includes("/assets/") || url.pathname === "/theme.js") {
    try {
      const body = await readFile(file);
      return send(200, body, types[extname(file)] ?? "application/octet-stream", { "cache-control": "public, max-age=31536000, immutable" });
    } catch { return send(404, "not found", "text/plain"); }
  }
  const { status, html, head, htmlAttrs, state } = await render(url.pathname);
  let page = template.replace("<!--head-->", head).replace("<!--app-->", html);
  page = page.replace("<!--state-->", state ? `<script type="application/json" id="ow-state">${escapeState(state)}</script>` : "");
  if (url.searchParams.has("nojs")) page = page.replace(/<script type="module"[^>]*><\/script>/g, "").replace(/<link rel="modulepreload"[^>]*>/g, "");
  send(status, page, "text/html; charset=utf-8", { "cache-control": "no-cache", vary: "Cookie" });
}).listen(PORT, () => console.log(`e1 listening on http://localhost:${PORT}`));
