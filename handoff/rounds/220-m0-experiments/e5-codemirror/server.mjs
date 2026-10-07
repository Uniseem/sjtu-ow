import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";
const root = join(fileURLToPath(new URL(".", import.meta.url)), "dist");
const CSP = process.env.CSP ?? "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'";
const types = { ".js": "text/javascript", ".css": "text/css", ".html": "text/html; charset=utf-8" };
createServer(async (req, res) => {
  const path = new URL(req.url, "http://x").pathname;
  try {
    const file = join(root, path === "/" ? "index.html" : path);
    const body = await readFile(file); // read first: a missing file must still be able to answer 404
    res.writeHead(200, { "content-type": types[extname(file)] ?? "application/octet-stream", "content-security-policy": CSP });
    res.end(body);
  } catch { res.writeHead(404, { "content-security-policy": CSP }); res.end("not found"); }
}).listen(Number(process.env.PORT ?? 5174), () => console.log("e5 on http://localhost:" + (process.env.PORT ?? 5174)));
