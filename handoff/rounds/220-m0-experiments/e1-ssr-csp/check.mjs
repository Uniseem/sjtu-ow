// Drives headless Chrome over the DevTools protocol (Node's built-in
// WebSocket, no extra packages) against the running e1 server and reports what
// 12-architecture 6.2/6.9/6.10 promise: hydration works, nothing is blocked by
// the strict CSP, client navigation works, and with no script the banner shows
// up after 8 s. Usage: node check.mjs [chrome path] [base url]
import { spawn, execSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chrome = process.argv[2] ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const base = process.argv[3] ?? "http://localhost:5173";
const port = 9300 + Math.floor(Math.random() * 500);
const profile = mkdtempSync(join(tmpdir(), "e1-chrome-"));
const proc = spawn(chrome, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--no-sandbox", "--window-size=1000,800", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function connect() {
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      const page = list.find((t) => t.type === "page");
      if (page) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(200);
  }
  throw new Error("no chrome");
}

const ws = new WebSocket(await connect());
await new Promise((r) => (ws.onopen = r));
let id = 0;
const waiting = new Map();
const events = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && waiting.has(msg.id)) { waiting.get(msg.id)(msg); waiting.delete(msg.id); }
  else events.push(msg);
};
const send = (method, params = {}) => new Promise((r) => { const i = ++id; waiting.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  return r.result.result.value;
};
await send("Runtime.enable"); await send("Log.enable"); await send("Page.enable"); await send("Network.enable");
const noted = () => events.filter((e) => ["Log.entryAdded", "Runtime.exceptionThrown", "Runtime.consoleAPICalled"].includes(e.method))
  .map((e) => e.method === "Log.entryAdded" ? `${e.params.entry.level}: ${e.params.entry.text} ${e.params.entry.url ?? ""}` : e.method === "Runtime.exceptionThrown" ? `exception: ${e.params.exceptionDetails.text}` : `console.${e.params.type}: ${e.params.args.map((a) => a.value ?? a.description).join(" ")}`);
const go = async (path) => { events.length = 0; await send("Page.navigate", { url: base + path }); await sleep(1200); };

const report = {};
// 1. first page, hydration, the strict CSP
await go("/");
report.home = await evaluate(`(async () => { const b = document.querySelector('[data-test=counter]'); b.click(); b.click(); await new Promise(r => setTimeout(r, 100)); return { counter: b.textContent, jsReady: document.documentElement.classList.contains('js-ready'), title: document.title }; })()`);
report.homeMessages = noted();
// 2. the policy really is on: inline things are stopped, CSSOM is not
report.policy = await evaluate(`(async () => { const v = []; document.addEventListener('securitypolicyviolation', e => v.push(e.violatedDirective)); const s = document.createElement('script'); s.textContent = 'window.__ran = 1'; document.body.append(s); const d = document.createElement('div'); d.setAttribute('style', 'color:red'); document.body.append(d); const el = document.createElement('div'); el.style.color = 'red'; document.body.append(el); await new Promise(r => setTimeout(r, 200)); return { inlineScriptRan: !!window.__ran, violations: v, cssom: getComputedStyle(el).color }; })()`);
// 3. client-side navigation and back
report.navigation = await evaluate(`(async () => { window.__same = 1; const v = []; document.addEventListener('securitypolicyviolation', e => v.push(e.violatedDirective)); [...document.querySelectorAll('nav a')].find(a => a.textContent === '战队一').click(); await new Promise(r => setTimeout(r, 600)); const a = { path: location.pathname, h1: document.querySelector('h1').textContent, same: window.__same, title: document.title }; history.back(); await new Promise(r => setTimeout(r, 600)); return { a, back: { path: location.pathname, h1: document.querySelector('h1').textContent, same: window.__same }, violations: v }; })()`);
// 4. a second route straight from the server, hydrated
await go("/teams/2/");
report.team = await evaluate(`({ h1: document.querySelector('h1').textContent, jsReady: document.documentElement.classList.contains('js-ready'), title: document.title })`);
report.teamMessages = noted();
// 5. no script: still readable, banner after 8 s
await go("/?nojs=1");
const early = await evaluate(`getComputedStyle(document.querySelector('.noscript-banner')).visibility`);
await sleep(8500);
report.noScript = { early, after8s: await evaluate(`getComputedStyle(document.querySelector('.noscript-banner')).visibility`), readable: await evaluate(`document.querySelector('h1').textContent`) };
const shot = await send("Page.captureScreenshot", { format: "png" });
writeFileSync(new URL("./screenshot-noscript.png", import.meta.url), Buffer.from(shot.result.data, "base64"));
// 6. unknown address: the server's 404, not a blank page
const status = await fetch(base + "/no-such-page/").then((r) => r.status);
report.unknownPageStatus = status;

console.log(JSON.stringify(report, null, 2));
ws.close();
proc.kill("SIGTERM");
try { execSync(`pkill -f ${profile} || true`); } catch {}
