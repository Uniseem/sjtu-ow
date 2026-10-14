"""Private production checks and a short-lived existing-admin browser session."""
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import urllib.request

os.umask(0o077)
root = Path("/srv/sjtu-ow")
private = Path("/root/sjtu-ow-301-private")
local = "http://127.0.0.1:22887"
public = "https://sjtu.ow-shanghaiuniversity.com"
database = Path("/var/lib/docker/volumes/sjtu-ow-next-data-301-retry/_data/sjtuow.sqlite3")
log = Path("/root/sjtu-ow-301-cutover.log").read_text()
matches = re.findall(r"^CUTOVER-BACKUP (/root/sjtu-ow-backups/cutover-[0-9]+)$", log, re.M)
if len(matches) != 1 or "CUTOVER-HEALTH-OK" not in log:
    raise SystemExit("Cutover success and explicit backup path required")
source = Path(matches[0]) / "legacy-source.sqlite3"
checks = []

def check(name, value):
    if not value:
        raise RuntimeError(name)
    checks.append(name)
    print("PASS PRODUCTION " + name, flush=True)

def request(path, cookie=""):
    headers = {"Cookie": cookie} if cookie else {}
    with urllib.request.urlopen(urllib.request.Request(local + path, headers=headers), timeout=20) as response:
        return response.status, response.headers, response.read()

status, headers, body = request("/healthz")
health = json.loads(body)
check("new stack health all checks", status == 200 and health.get("status") == "ok" and all(item.get("ok") for item in health.get("checks", {}).values()))
check("legacy cron disabled", not Path("/etc/cron.d/sjtu-ow").exists())
with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as old, sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as new:
    old_passwords = old.execute("SELECT id,password FROM accounts_user ORDER BY id").fetchall()
    new_passwords = new.execute("SELECT id,password_hash FROM users ORDER BY id").fetchall()
    check("all existing password hashes preserved", old_passwords == new_passwords)
    check("new SQLite integrity and foreign keys", new.execute("PRAGMA quick_check").fetchone() == ("ok",) and not new.execute("PRAGMA foreign_key_check").fetchall())
    choices = new.execute("SELECT email FROM users WHERE is_active=1 AND is_superuser=1 AND email_verified_at IS NOT NULL ORDER BY id LIMIT 1").fetchall()
    check("existing verified superuser retained", len(choices) == 1)
    paths = ["/", "/news/", "/teams/", "/members/", "/tournaments/", "/scrims/", "/about/", "/terms/", "/privacy/", "/accounts/login/"]
    from urllib.parse import quote
    for (slug,) in new.execute("SELECT p.slug FROM pages p JOIN articles a ON a.page_id=p.id WHERE p.live=1 AND p.is_public=1 ORDER BY p.id LIMIT 2"):
        paths.append("/news/" + quote(slug, safe="") + "/")
    image = new.execute("SELECT id FROM images ORDER BY id LIMIT 1").fetchone()
    check("image records retained", image is not None)
    # Public SSR already projects the exact permitted spec and source URL.
    _, _, homepage = request("/")
    media_urls = re.findall(rb'(?:src|srcset)="(/media/r/[0-9]+/[a-z0-9-]+\.webp)', homepage)
    check("real homepage image responds", bool(media_urls) and request(media_urls[0].decode())[0] == 200)
container = subprocess.check_output(["docker", "compose", "-p", "sjtu-ow-next", "-f", str(root / "deploy/docker-compose.new.yml"), "-f", str(root / "deploy/docker-compose.next-vps.yml"), "--env-file", str(root / ".env.next"), "ps", "-q", "server"], text=True).strip()
token = subprocess.check_output(["docker", "exec", container, "/srv/sjtuow/sjtuow", "session", choices[0][0]], text=True).strip()
status, headers, body = request("/api/session", "ow_session=" + token)
user = json.loads(body).get("user")
check("real existing account session and superuser gate", status == 200 and user and user.get("superuser"))
_, _, body = request("/api/session", "sessionid=legacy-session-marker")
check("old Django cookies require relogin", json.loads(body).get("user") is None)
config = {"base": public, "paths": paths, "sessions": [{"token": token, "admin": True}]}
target = private / "browser.json"
target.write_text(json.dumps(config))
target.chmod(0o600)
(private / "verification-summary.json").write_text(json.dumps({"checks": checks, "health": health, "password_accounts": len(old_passwords), "backup": str(source.parent)}))
print("PRODUCTION-PRIVATE-API-CHECKS-OK count=" + str(len(checks)), flush=True)
