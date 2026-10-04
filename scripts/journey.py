"""A newcomer's first evening, in a real browser, on the test machine (round 168).

    bash scripts/remote-check.sh run uv run python scripts/journey.py

The tests drive Django directly; this drives Chromium, so it also catches
what only a browser shows: a script the CSP blocks, a form whose button does
nothing, a slot that never fills. On a throwaway site (screens.py's seed: a
captain with a team, a scrim) it registers through the sign-up form with test
values, reads the code from the worker's console mail, verifies, adds a game
ID and a contact, signs up for the scrim, applies to the team and looks for
the scrim under 「我的安排」 on the homepage. Every console error, uncaught
exception and CSP report on the way is printed and counts as a failure.
Exits 1 if any step fails. Needs ``chromium`` (installed on the test machine).
"""

from __future__ import annotations

import email
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import screens  # noqa: E402

screens.WORK = Path("/tmp/sjtu-ow-journey")
WORK = screens.WORK
LOG = WORK / "worker.log"
EVENTS: list[tuple[str, str]] = []
# Test values for this throwaway site only.
EMAIL, NICKNAME, PASSWORD = "newbie@journey.test", "新来的", "Journey-Test-Pass-2026"


class Watching(screens.DevTools):
    """Keeps the browser's own messages: exceptions, error logs, CSP."""

    def _receive(self):
        message = super()._receive()
        method, params = message.get("method", ""), message.get("params", {})
        if method == "Runtime.exceptionThrown":
            EVENTS.append(("exception", params["exceptionDetails"].get("text", "")))
        elif method == "Log.entryAdded" and params["entry"].get("level") == "error":
            entry = params["entry"]
            EVENTS.append(("error", f"{entry.get('text', '')} {entry.get('url', '')}"))
        elif method == "Runtime.consoleAPICalled" and params.get("type") == "error":
            EVENTS.append(
                ("console", str(params.get("args", [{}])[0].get("value", "")))
            )
        return message


def verification_code(console: str) -> str | None:
    """The code in the newest letter to EMAIL that the console mail backend
    printed. Its plain-text part says 验证码：XXXXXX (templates/account/email),
    transfer-encoded, so each letter is parsed and decoded first."""
    for chunk in reversed(console.split("-" * 79)):
        start = chunk.find("Content-Type:")
        if start < 0 or f"To: {EMAIL}" not in chunk:
            continue
        letter = email.message_from_string(chunk[start:])
        for part in letter.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", "replace")
                found = re.search(r"验证码：([A-Z0-9]{6})", body)
                if found:
                    return found.group(1)
    return None


def journey(tools, base, data) -> list[str]:
    failed = []

    def js(expression):
        reply = tools.send(
            "Runtime.evaluate", {"expression": expression, "returnByValue": True}
        )
        return reply.get("result", {}).get("value")

    def go(path):
        tools.send("Page.navigate", {"url": path if "://" in path else base + path})
        time.sleep(2)

    def fill_and_submit(script):
        """Run ``script`` (it marks its form with data-journey), then submit."""
        js(script)
        js("document.querySelector('form[data-journey]').requestSubmit()")
        time.sleep(2.5)

    def step(name, ok, detail=""):
        print(f"{'ok ' if ok else 'BAD'} {name} {detail}".rstrip())
        if not ok:
            failed.append(name)

    def page_says(text):
        return bool(js(f"document.body.innerText.includes({text!r})"))

    go("/accounts/signup/")
    fill_and_submit(f"""(() => {{
        const f = document.querySelector('form[action*="signup"]');
        f.querySelector('[name=email]').value = {EMAIL!r};
        f.querySelector('[name=nickname]').value = {NICKNAME!r};
        f.querySelector('[name=password1]').value = {PASSWORD!r};
        f.querySelector('[name=password2]').value = {PASSWORD!r};
        f.querySelector('[name=is_sjtu][value=true]').checked = true;
        f.querySelectorAll('input[type=checkbox]').forEach(box => box.checked = true);
        f.setAttribute('data-journey', '1');
    }})()""")
    step("注册表单提交", js("location.pathname") == "/accounts/confirm-email/")

    code = None
    for _ in range(40):
        text = LOG.read_text(encoding="utf-8", errors="replace") if LOG.exists() else ""
        code = verification_code(text)
        if code:
            break
        time.sleep(0.5)
    step("验证码邮件发出", code is not None)
    if code:
        fill_and_submit(f"""(() => {{
            const field = document.querySelector('input[name=code]');
            field.value = {code!r};
            field.form.setAttribute('data-journey', '1');
        }})()""")
    step("验证后到了个人中心", js("location.pathname") == "/me/")

    go("/me/game-accounts/?new=1")
    fill_and_submit("""(() => {
        const f = [...document.querySelectorAll('main form')]
            .find(form => form.querySelector('[name=battletag]'));
        f.querySelector('[name=battletag]').value = 'Newbie#1234';
        f.querySelectorAll('select')
            .forEach(s => { s.selectedIndex = s.options.length - 5; });
        f.setAttribute('data-journey', '1');
    })()""")
    step("加了游戏 ID", page_says("Newbie#1234"))

    go("/me/contacts/?new=1")
    fill_and_submit("""(() => {
        const f = [...document.querySelectorAll('main form')]
            .find(form => form.querySelector('[name=value]'));
        const kind = f.querySelector('[name=type]');
        kind.value = kind.options[1].value;
        f.querySelector('[name=value]').value = '123456789';
        f.setAttribute('data-journey', '1');
    })()""")
    step("加了联系方式", page_says("123456789"))

    go(f"/scrims/{data['scrim']}/")
    fill_and_submit("""(() => {
        const f = [...document.querySelectorAll('form')]
            .find(form => form.action.includes('/signup/'));
        const pick = f.querySelector('[name=game_account]');
        if (pick.tagName === 'SELECT') pick.selectedIndex = pick.options.length - 1;
        else pick.checked = true;
        f.querySelectorAll('[name=roles]').forEach(box => box.checked = true);
        f.setAttribute('data-journey', '1');
    })()""")
    step("报了内战", page_says("报名成功"))

    go(f"/teams/{data['team']}/apply/")
    fill_and_submit("""(() => {
        const f = [...document.querySelectorAll('main form')].pop();
        f.querySelectorAll('input[type=checkbox]').forEach(box => box.checked = true);
        f.setAttribute('data-journey', '1');
    })()""")
    applied = page_says("申请已提交")
    detail = (
        ""
        if applied
        else js(
            "[...document.forms].map(f => f.getAttribute('action') + ' ['"
            " + [...f.elements].map(e => e.name + '=' + e.value).join('&') + ']')"
            ".join(' | ') + ' || ' + [...document.querySelectorAll("
            "'.errorlist, [role=alert], .c-field__error, .text-danger')]"
            ".map(e => e.innerText).join(' / ')"
        )
    )
    step("申请了战队", applied, detail)

    go("/")
    agenda = js("(document.querySelector('[data-my-agenda]') || {}).innerText || ''")
    step("首页「我的安排」里有这场内战", "截图内战" in (agenda or ""))

    tools.send("Runtime.evaluate", {"expression": "1"})  # collect what is pending
    for kind, text in EVENTS:
        print(f"    浏览器报告 {kind}: {text[:200]}")
    step("浏览器没有报错", not EVENTS, f"（{len(EVENTS)} 条）" if EVENTS else "")
    return failed


def main() -> int:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    env = screens.site_env()
    if not (ROOT / "static/css/app.css").exists():
        screens.manage("tailwind", "build")
    screens.manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
    screens.manage("createcachetable")
    screens.manage("init_site", "--verbosity", "0", stdout=subprocess.DEVNULL)
    seeded = subprocess.run(
        [sys.executable, str(ROOT / "scripts/screens.py"), "seed"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(seeded.stdout.strip().splitlines()[-1])

    port, debug = screens.free_port(), screens.free_port()
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with LOG.open("w") as log:
        worker = subprocess.Popen(
            [sys.executable, "manage.py", "run_worker"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    browser = subprocess.Popen(
        [
            "chromium",
            "--headless=new",
            "--no-sandbox",
            f"--remote-debugging-port={debug}",
            f"--user-data-dir={WORK / 'profile'}",
            "--window-size=1280,900",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        screens.wait_for(f"{base}/robots.txt")
        screens.wait_for(f"http://127.0.0.1:{debug}/json/version")
        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug}/json"))
        page = next(t for t in targets if t.get("type") == "page")
        tools = Watching(page["webSocketDebuggerUrl"])
        for domain in ("Page", "Runtime", "Log"):
            tools.send(f"{domain}.enable")
        failed = journey(tools, base, data)
    finally:
        for process in (browser, worker, server):
            process.terminate()
        for process in (browser, worker, server):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    print("全部走通" if not failed else f"没走通：{'、'.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
