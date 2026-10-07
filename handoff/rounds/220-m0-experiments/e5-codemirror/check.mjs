// E5: CodeMirror 6 under `style-src 'self'` (no unsafe-inline, no nonce): is the
// editor styled, does typing, a toolbar action and undo work, and does the page
// report any CSP violation? Same CDP plumbing as e1-ssr-csp/check.mjs.
// Usage: node check.mjs [chrome path] [base url]
import { spawn, execSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chrome = process.argv[2] ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const base = process.argv[3] ?? "http://localhost:5174";
const port = 9300 + Math.floor(Math.random() * 500);
const profile = mkdtempSync(join(tmpdir(), "e5-chrome-"));
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

const results = {};
for (const [name, path] of [["document root", "/"], ["shadow root", "/?shadow=1"]]) {
  const report = {};
  await send("Page.addScriptToEvaluateOnNewDocument", { source: "window.__violations = []; document.addEventListener('securitypolicyviolation', e => window.__violations.push(e.violatedDirective + ' ' + (e.blockedURI || 'inline')));" });
  await go(path);
  await sleep(500);
  report.styled = await evaluate(`(() => { const r = window.__root; const ed = r.querySelector('.cm-editor'); const c = r.querySelector('.cm-content'); const sc = r.querySelector('.cm-scroller'); const f = r.querySelector('.cm-line'); return { editorPresent: !!ed, editorDisplay: ed && getComputedStyle(ed).display, contentWhiteSpace: c && getComputedStyle(c).whiteSpace, contentFont: c && getComputedStyle(c).fontFamily, scrollerOverflowX: sc && getComputedStyle(sc).overflowX, themedMinHeight: ed && getComputedStyle(ed).minHeight, adoptedSheets: (r.adoptedStyleSheets || document.adoptedStyleSheets).length, styleElements: document.querySelectorAll('style').length + (r.querySelectorAll ? r.querySelectorAll('style').length : 0), lineHeightPx: f && getComputedStyle(f).lineHeight }; })()`);
  await evaluate(`window.__view.focus()`);
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "End", code: "End", modifiers: 2, windowsVirtualKeyCode: 35 });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "End", code: "End", modifiers: 2, windowsVirtualKeyCode: 35 });
  await send("Input.insertText", { text: "追加的一行，中文也能输入。" });
  await sleep(200);
  report.typing = await evaluate(`({ tail: window.__view.state.doc.toString().slice(-16), status: document.getElementById('status').textContent })`);
  await evaluate(`(() => { const v = window.__view; const i = v.state.doc.toString().indexOf('正文'); v.dispatch({ selection: { anchor: i, head: i + 2 } }); })()`);
  await evaluate(`document.querySelector('[data-act=bold]').click()`);
  const afterBold = await evaluate(`window.__view.state.doc.toString().includes('**正文**')`);
  await evaluate(`document.querySelector('[data-act=h2]').click()`);
  await evaluate(`document.querySelector('[data-act=undo]').click()`);
  report.toolbar = { boldApplied: afterBold, h2UndoneByUndo: await evaluate(`!window.__view.state.doc.toString().split(String.fromCharCode(10)).some(l => l.startsWith('## ') && l.includes('追加'))`) };
  report.selectionInside = await evaluate(`(() => { const v = window.__view; v.dispatch({ selection: { anchor: 0, head: 2 } }); const sel = (window.__root.getSelection ? window.__root.getSelection() : document.getSelection()); return { cmMain: v.state.selection.main.from + '-' + v.state.selection.main.to, domText: sel ? sel.toString() : null }; })()`);
  report.violations = await evaluate(`window.__violations`);
  report.messages = noted().filter((m) => !m.includes("favicon"));
  const shot = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(new URL(`./screenshot-${name.replace(" ", "-")}.png`, import.meta.url), Buffer.from(shot.result.data, "base64"));
  results[name] = report;
}
results.policyHeader = (await fetch(base + "/")).headers.get("content-security-policy");
console.log(JSON.stringify(results, null, 2));
ws.close();
proc.kill("SIGTERM");
try { execSync(`pkill -f ${profile} || true`); } catch {}
