"""Round 214 follow-up: the C1 drill, for real (2026-10-07).

An SMTP server that accepts the connection and never answers. Before 214
the worker waited on it forever; now each attempt must give up after about
20 seconds, the next task must still run, and the retry must be queued.

Runs a throwaway site (temporary database, dev settings except that mail
really goes through SiteSettings SMTP), a fake SMTP server in this process,
and the real `manage.py run_worker` in a subprocess. Exit code 1 if any
check fails.

Run on the test machine:
  bash scripts/remote-check.sh run uv run python \
    handoff/rounds/214-worker-and-logging/c1_drill.py
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(tempfile.mkdtemp(prefix="c1-drill-"))
DB = WORK / "db.sqlite3"
TASK = "core.tasks.deliver_queued_email"
WAIT_LIMIT = 120

# Control run: `--without-timeout` takes the 214 fix back out of core/mail.py
# (only ever on the test machine's throwaway checkout, put back at the end).
# The drill must then fail: the worker hangs on the first letter.
MAIL_PY = ROOT / "core" / "mail.py"
FIX = "        timeout=SMTP_TIMEOUT_SECONDS,\n"
WITHOUT_TIMEOUT = "--without-timeout" in sys.argv
original_mail_py = MAIL_PY.read_text(encoding="utf-8")
if WITHOUT_TIMEOUT:
    assert original_mail_py.count(FIX) == 1, "core/mail.py 里找不到 214 的超时参数"
    MAIL_PY.write_text(original_mail_py.replace(FIX, ""), encoding="utf-8")
    WAIT_LIMIT = 60

# 214's first attempt ran under dev settings, whose delivery backend is the
# console: the "send" never touched SMTP and finished in 0 seconds. Here the
# delivery backend is the production one and the allowlist is off.
(WORK / "c1_settings.py").write_text(
    "from sjtu_ow.settings.dev import *  # noqa: F403\n"
    'EMAIL_DELIVERY_BACKEND = "core.mail.SiteSettingsEmailBackend"\n'
    "EMAIL_ALLOWLIST = []\n",
    encoding="utf-8",
)
ENV = {
    **os.environ,
    "DJANGO_SETTINGS_MODULE": "c1_settings",
    "PYTHONPATH": os.pathsep.join([str(WORK), str(ROOT)]),
    "DATABASE_PATH": str(DB),
    "MEDIA_ROOT": str(WORK / "media"),
    "PRERENDER_ROOT": str(WORK / "prerendered"),
    "EMAIL_ALLOWLIST": "",
    "PYTHONUTF8": "1",
}


def manage(*args, **kwargs):
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=ROOT,
        env=ENV,
        check=True,
        **kwargs,
    )


# --- the black hole -----------------------------------------------------------

accepted: list[float] = []
held: list[socket.socket] = []


def black_hole(server: socket.socket) -> None:
    while True:
        try:
            conn, _ = server.accept()
        except OSError:
            return
        accepted.append(time.monotonic())
        held.append(conn)  # keep it open, never say a word


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("127.0.0.1", 0))
server.listen()
PORT = server.getsockname()[1]
threading.Thread(target=black_hole, args=(server,), daemon=True).start()

# --- the site -------------------------------------------------------------------

manage("migrate", "--noinput", stdout=subprocess.DEVNULL)
manage("createcachetable")

SETUP = f"""
from django.core.mail import EmailMessage
from core.mail import serialize_email
from core.models import SiteSettings
from core.tasks import deliver_queued_email

site = SiteSettings.load()
site.smtp_host = "127.0.0.1"
site.smtp_port = {PORT}
site.smtp_security = SiteSettings.SmtpSecurity.NONE
site.smtp_username = ""
site.from_address = "drill@example.com"
site.save()
assert SiteSettings.load().smtp_port == {PORT}
print("SiteSettings 行数", SiteSettings.objects.count(), "端口", {PORT})
for n in (1, 2):
    to = [f"m{{n}}@example.com"]
    message = EmailMessage(subject=f"演练 {{n}}", body="黑洞", to=to)
    deliver_queued_email.enqueue(serialize_email(message))
"""
manage("shell", "-c", SETUP)

start = time.monotonic()
worker = subprocess.Popen(
    [sys.executable, "manage.py", "run_worker"],
    cwd=ROOT,
    env=ENV,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)


def mail_rows():
    with sqlite3.connect(DB) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "SELECT status, started_at, finished_at, run_after, args_kwargs,"
            " exception_class_path, traceback"
            " FROM django_tasks_database_dbtaskresult"
            " WHERE task_path = ? ORDER BY enqueued_at",
            (TASK,),
        ).fetchall()


def attempt(row) -> int:
    args = json.loads(row["args_kwargs"])["args"]
    return args[1] if len(args) > 1 else 0


def subject(row) -> str:
    return json.loads(row["args_kwargs"])["args"][0]["subject"]


def when(value):
    return datetime.fromisoformat(value) if value else None


try:
    while time.monotonic() - start < WAIT_LIMIT:
        firsts = [r for r in mail_rows() if attempt(r) == 0]
        if firsts and all(r["finished_at"] for r in firsts):
            break
        time.sleep(1)
    elapsed = time.monotonic() - start
finally:
    worker.terminate()
    try:
        out, _ = worker.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        worker.kill()
        out, _ = worker.communicate()
    server.close()
    MAIL_PY.write_text(original_mail_py, encoding="utf-8")

rows = mail_rows()
firsts = [r for r in rows if attempt(r) == 0]
retries = [r for r in rows if attempt(r) == 1]

print(f"\n黑洞端口 {PORT}，收下连接 {len(accepted)} 次", end="")
if accepted:
    print("，相对 worker 启动：" + "、".join(f"{t - start:.1f} 秒" for t in accepted))
else:
    print()
print(f"等了 {elapsed:.1f} 秒\n")
durations = []
for r in firsts:
    took = None
    if r["started_at"] and r["finished_at"]:
        took = (when(r["finished_at"]) - when(r["started_at"])).total_seconds()
        durations.append(took)
    shown = f"{took:.1f} 秒" if took is not None else "没跑完"
    error = r["exception_class_path"]
    print(f"{subject(r)}：{r['status']}，用时 {shown}，异常 {error}")
for r in retries:
    print(f"{subject(r)} 的第 1 次重试：{r['status']}，排在 {r['run_after']}")

checks = {
    "两封信都失败（不是 0 秒成功）": len(firsts) == 2
    and all(r["status"] == "FAILED" for r in firsts),
    "每次在 18–25 秒之间放弃": len(durations) == 2
    and all(18 <= d <= 25 for d in durations),
    # smtplib turns the socket timeout into SMTPServerDisconnected("...: timed
    # out"), so the class name alone does not say it was the timeout.
    "异常是超时（timed out）": len(firsts) == 2
    and all("timed out" in (r["traceback"] or "") for r in firsts),
    "第二封在第一封放弃后接着跑": len(firsts) == 2
    and firsts[1]["started_at"] is not None
    and firsts[0]["finished_at"] is not None
    and when(firsts[1]["started_at"]) >= when(firsts[0]["finished_at"]),
    "两封都排了 1 分钟后的重试": len(retries) == 2
    and all(r["status"] == "READY" for r in retries),
    "黑洞确实收到了连接": len(accepted) >= 2,
}
print()
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
passed = all(checks.values())
if WITHOUT_TIMEOUT:
    # The control run is meant to fail; it "passes" only if the drill caught it.
    verdict = "没红，演练测不出问题" if passed else "红了，符合预期"
    print("\n对照：拆掉超时后演练" + verdict)
    sys.exit(1 if passed else 0)
if not passed:
    print("\nworker 输出：\n" + out[-3000:])
    sys.exit(1)
print("\nC1 演练通过")
