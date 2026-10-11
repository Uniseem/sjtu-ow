#!/usr/bin/env python3
"""Round 290 real Go HTTP/DB journey, using only a new local temporary site.

Run on the test machine after its checked Go build has been provided:
  uv run python handoff/rounds/290-f6-f9-full-frontend/api-journey.py \
      --binary /tmp/sjtuow-290 --repo /path/to/sjtu-ow

The script never builds, migrates a pre-existing database, deploys, contacts
Google/S3, or changes other test drivers. fontTools/Pillow come from the existing
repository Python environment. --work-dir may name a NEW empty directory only.
Evidence, fictional SQLite DB, and captured local mail remain there afterwards.
SQL writes are confined to initial fictional fixture setup before serve starts;
all tested mutations subsequently use real HTTP and are verified by read-only DB.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import socketserver
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Failure(AssertionError):
    pass


def check(condition, message):
    if not condition:
        raise Failure(message)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def scrub(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if any(part in key.lower() for part in ["password", "secret", "token", "cookie"])
            and not key.startswith("has_") else scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


class Mailbox(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 localhost fixture SMTP\r\n")
        recipients = []
        while line := self.rfile.readline():
            command = line.decode("utf-8", "replace").strip()
            upper = command.upper()
            if upper.startswith(("EHLO", "HELO")):
                self.wfile.write(b"250 localhost\r\n")
            elif upper.startswith("MAIL FROM:"):
                recipients = []
                self.wfile.write(b"250 OK\r\n")
            elif upper.startswith("RCPT TO:"):
                recipient = command.split(":", 1)[1].strip().strip("<>")
                if not recipient.lower().endswith(".test"):
                    self.wfile.write(b"550 fictional test addresses only\r\n")
                else:
                    recipients.append(recipient)
                    self.wfile.write(b"250 OK\r\n")
            elif upper == "DATA":
                self.wfile.write(b"354 Send data\r\n")
                parts = []
                while (part := self.rfile.readline()) not in (b".\r\n", b""):
                    parts.append(part[1:] if part.startswith(b"..") else part)
                message = BytesParser(policy=policy.default).parsebytes(b"".join(parts))
                record = {"server": self.server.label, "recipients": recipients,
                          "subject": str(message["Subject"]), "content_type": message.get_content_type()}
                with self.server.lock:
                    self.server.records.append(record)
                    with self.server.mailbox.open("a", encoding="utf-8") as output:
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                self.wfile.write(b"250 accepted\r\n")
            elif upper == "QUIT":
                self.wfile.write(b"221 Bye\r\n")
                break
            elif upper == "RSET":
                recipients = []
                self.wfile.write(b"250 OK\r\n")
            else:
                self.wfile.write(b"250 OK\r\n")


class LocalSMTP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, label, mailbox):
        super().__init__(("127.0.0.1", 0), Mailbox)
        self.label = label
        self.mailbox = mailbox
        self.records = []
        self.lock = threading.Lock()
        threading.Thread(target=self.serve_forever, daemon=True).start()


class Journey:
    def __init__(self, repo, binary, work):
        self.repo = repo
        self.binary = binary
        self.work = work
        self.base = f"http://127.0.0.1:{free_port()}"
        self.database = work / "data" / "sjtuow.sqlite3"
        self.environment = {**os.environ, "DATA_DIR": str(work / "data"),
            "MEDIA_DIR": str(work / "media"), "ASSETS_DIR": str(work / "assets"),
            "SITE_URL": self.base, "SIGNING_KEY": "round-290-fictional-signing-key-32chars",
            "FIELD_ENCRYPTION_KEY": "round-290-fictional-field-key-32chars",
            "SJTUOW_ENV": "dev", "TEST_ENVIRONMENT": "1", "EMAIL_ALLOWLIST": "",
            "SMTP_HOST": "127.0.0.1", "SMTP_SECURITY": "plain", "SMTP_USER": "", "SMTP_PASSWORD": "",
            "SMTP_FROM": "site@example.test", "SJTUOW_HTTP_ADDR": urlsplit(self.base).netloc}
        self.processes = []
        self.files = []
        self.smtp = []
        self.sessions = {}
        self.results = []
        self.opener = build_opener(NoRedirect)
        self.article = None
        self.font = None

    def cli(self, *arguments):
        result = subprocess.run([str(self.binary), *arguments], cwd=self.repo / "server",
            env=self.environment, text=True, capture_output=True, timeout=60)
        check(result.returncode == 0, f"CLI {' '.join(arguments[:1])} failed; stderr={result.stderr[-1500:]}")
        return result.stdout.strip()

    def db(self, query, parameters=()):
        with sqlite3.connect(f"file:{self.database}?mode=ro", uri=True) as database:
            database.row_factory = sqlite3.Row
            return [dict(row) for row in database.execute(query, parameters)]

    def start(self):
        self.smtp = [LocalSMTP("environment-fallback", self.work / "mailbox.jsonl"),
                     LocalSMTP("database-settings", self.work / "mailbox.jsonl")]
        self.environment["SMTP_PORT"] = str(self.smtp[0].server_address[1])
        self.cli("migrate")
        # CLI seed/session create the same fictional identities used by screenshots.
        # Discard its session JSON from evidence; cookies stay in process memory.
        self.cli("seed")
        self.fixture_setup()
        for actor, email in {"member": "member@screens.test", "captain": "captain@screens.test",
                             "super": "officer@screens.test", "auxsuper": "auxsuper@screens.test"}.items():
            token = self.cli("session", email).splitlines()[-1].strip()
            check(bool(token) and " " not in token, "session CLI did not return a token")
            self.sessions[actor] = token
        self.spawn("serve", "api.log")
        self.spawn("worker", "worker.log")
        for _ in range(120):
            try:
                self.http("GET", "/api/session", actor="super", evidence=False)
                break
            except Exception:
                check(all(process.poll() is None for process in self.processes), "temporary Go process exited during startup")
                time.sleep(0.25)
        else:
            raise Failure("temporary Go API did not become ready")

    def fixture_setup(self):
        """Initial fictional fixtures only; never write a tested operation's result."""
        now = utc(datetime.now(timezone.utc))
        with sqlite3.connect(self.database) as database:
            database.execute("PRAGMA foreign_keys=ON")
            # Captain is also the non-superuser tournament manager; default member
            # remains an ordinary verified contributor through the real role rules.
            database.execute("INSERT OR IGNORE INTO user_roles(user_id,role,created_at) VALUES(2,'tournament_admin',?)", (now,))
            for user in [1,2,3]:
                database.execute("INSERT INTO game_accounts(user_id,battletag,battletag_norm,created_at,updated_at,ranks_updated_at) SELECT ?,?,?,?, ?,? WHERE NOT EXISTS(SELECT 1 FROM game_accounts WHERE user_id=?)", (user,f"Fixture#{1000+user}",f"fixture#{1000+user}",now,now,now,user))
            for user in [1,2,3]:
                database.execute("INSERT INTO contacts(user_id,type,value,created_at,updated_at) SELECT ?,'qq',?,?,? WHERE NOT EXISTS(SELECT 1 FROM contacts WHERE user_id=?)", (user, f"123450000{user}", now, now, user))
            database.execute("INSERT INTO users(id,email,email_norm,nickname,password_hash,is_sjtu,agreed_terms_at,agreed_cross_border_at,email_verified_at,is_active,is_superuser,created_at,updated_at) VALUES(5,'auxsuper@screens.test','auxsuper@screens.test','辅助超管','not-a-real-password',1,?,?,?,1,1,?,?)", (now, now, now, now, now))
            database.execute("UPDATE site_settings SET founded_on='2020-09-01' WHERE id=1")
            # Ordinary pages are pre-existing site objects, not manufactured saves.
            for page_id, kind, slug, title in [(1100, "site_page", "journey-about", "旅程说明"),
                                              (1101, "news_index", "news", "资讯")]:
                exists = database.execute("SELECT id FROM pages WHERE kind=? AND slug=?", (kind, slug)).fetchone()
                if exists:
                    continue
                database.execute("INSERT INTO pages(id,kind,slug,title,owner_id,created_at,updated_at) VALUES(?,?,?,?,4,?,?)", (page_id, kind, slug, title, now, now))
                if kind == "site_page":
                    database.execute("INSERT INTO site_pages(page_id,body_md,body_html,body_plain) VALUES(?,'初始说明','<p>初始说明</p>','初始说明')", (page_id,))
                else:
                    database.execute("INSERT INTO news_index(page_id,intro) VALUES(?,'初始栏目')", (page_id,))
        (self.work / "fixture-description.json").write_text(json.dumps({
            "identities": ["ordinary contributor", "captain/tournament manager", "superuser"],
            "objects": ["three fictional team members with game IDs and QQ contacts", "pre-existing ordinary page", "news index"],
            "result_sql_writes": False}, ensure_ascii=False, indent=2))

    def spawn(self, command, filename):
        output = (self.work / filename).open("w", encoding="utf-8")
        self.files.append(output)
        self.processes.append(subprocess.Popen([str(self.binary), command], cwd=self.repo / "server",
            env=self.environment, stdout=output, stderr=subprocess.STDOUT))

    def http(self, method, path, body=None, actor="super", expect=200, key=None, evidence=True):
        check(path.startswith("/") and not path.startswith("//"), "journey must stay on localhost")
        headers = {"Accept": "application/json", "Sec-Fetch-Site": "same-origin"}
        if actor:
            headers["Cookie"] = "ow_session=" + self.sessions[actor]
        if method != "GET":
            headers["Content-Type"] = "application/json"
            headers["Idempotency-Key"] = key or str(uuid.uuid4())
            headers["Origin"] = self.base
        data = json.dumps(body if body is not None else {}).encode() if method != "GET" else None
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=90)
        except HTTPError as error:
            response = error
        with response:
            status = response.status
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            result = json.loads(raw)
        else:
            result = raw.decode("utf-8", "replace")
        if evidence:
            with (self.work / "http.jsonl").open("a", encoding="utf-8") as output:
                output.write(json.dumps({"method": method, "path": path, "actor": actor or "visitor",
                    "status": status, "response": scrub(result)}, ensure_ascii=False) + "\n")
        check(status == expect, f"{method} {path}: HTTP {status}, expected {expect}; inspect http.jsonl")
        letters = result.get("letters") if isinstance(result, dict) else None
        if status == 200 and isinstance(letters, dict) and letters.get("batch"):
            batch = letters["batch"]
            held = self.http("GET", "/api/letters/" + quote(batch, safe=""), actor=actor)
            check(held["state"] == "waiting", "write returned a letter batch that is not waiting")
            ids = [letter["id"] for letter in held["letters"]]
            self.http("POST", "/api/letters/" + quote(batch, safe=""), {"send": ids, "skip": False}, actor=actor)
            self.assertion("real pending letter decision " + str(len(ids)), not self.db("SELECT id FROM held_letters WHERE batch=? AND state='waiting'", (batch,)) and len(self.db("SELECT id FROM held_letters WHERE batch=? AND state='sent'", (batch,))) == len(ids))
        return result

    def assertion(self, name, condition):
        check(condition, name)
        self.results.append({"name": name, "status": "passed"})
        print("PASS", name, flush=True)

    @contextmanager
    def group(self, name):
        try:
            yield
        except Exception as error:
            self.results.append({"name": name, "status": "failed", "message": str(error)})
            print("FAIL", name, str(error), flush=True)

    def close(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
        for process in self.processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for output in self.files:
            output.close()
        for server in self.smtp:
            server.shutdown()
            server.server_close()

    def navigation(self):
        with self.group("navigation and permission matrix"):
            self.http("GET", "/api/admin/navigation", actor=None, expect=401)
            member = self.http("GET", "/api/admin/navigation", actor="member")
            manager = self.http("GET", "/api/admin/navigation", actor="captain")
            owner = self.http("GET", "/api/admin/navigation")
            self.assertion("ordinary contributor can enter content but has no settings", any(row["key"] == "content" for row in member["sections"]) and not any(row["key"] == "settings" for row in member["sections"]))
            self.assertion("non-superuser manager sees activities", any(row["key"] == "activities" for row in manager["sections"]))
            self.assertion("superuser sees eight navigation sections", len(owner["sections"]) == 8)
            for endpoint in ["/api/admin/settings", "/api/admin/settings/backup", "/api/admin/fonts", "/api/admin/roles", "/api/admin/users/search"]:
                self.http("GET", endpoint, actor="member", expect=403)
            self.http("GET", "/api/admin/registrations", actor="member", expect=403)
            self.assertion("privileged management API rejects ordinary contributor", True)

    def content(self):
        with self.group("article draft and publish"):
            categories = self.http("GET", "/api/admin/categories")["items"]
            category = next(row["id"] for row in categories if row["allow_submission"])
            article = self.http("POST", "/api/articles", {"title": "真实接口旅程文章", "category_id": category,
                "summary": "虚构测试摘要", "body_md": "第一版 **真实正文**。"})
            self.article = article["id"]
            detail = self.http("GET", f"/api/admin/articles/{self.article}")
            self.assertion("draft editor reads real draft revision", detail["article"]["id"] == self.article and detail["version"] == article["version"])
            # The plain member must not see another person's unpublished draft.
            self.http("GET", f"/api/admin/articles/{self.article}", actor="member", expect=404)
            save = self.http("PATCH", f"/api/articles/{self.article}", {"base_version": detail["version"], "changes": {"body_md": "第二版 **真实正文**。", "slug": "round-290-api-journey"}})
            stale = self.http("PATCH", f"/api/articles/{self.article}", {"base_version": detail["version"], "changes": {"title": "陈旧覆盖"}}, expect=409)
            self.assertion("stale content save returns current values", "current" in stale)
            self.http("POST", f"/api/articles/{self.article}/publish", {"base_version": save["version"]})
            public = self.http("GET", "/api/page/news/round-290-api-journey", actor=None)
            self.assertion("published article contains latest real body", "第二版" in json.dumps(public, ensure_ascii=False) and "真实正文" in json.dumps(public, ensure_ascii=False))
            self.assertion("publish changed persisted live state", self.db("SELECT live FROM pages WHERE id=?", (self.article,))[0]["live"] == 1)
        with self.group("ordinary page, pins and news draft publication"):
            check(self.article is not None, "article prerequisite failed")
            page = self.http("GET", "/api/admin/pages/1100")
            saved = self.http("PATCH", "/api/admin/pages/1100", {"base_version": page["version"], "changes": {"body_md": "真实普通页已修改。", "title": "旅程页面"}})
            self.http("POST", "/api/admin/pages/1100/publish", {"base_version": saved["version"]})
            visible = self.http("GET", "/api/page/journey-about", actor=None)
            self.assertion("ordinary page publishes saved Markdown", "真实普通页已修改" in json.dumps(visible, ensure_ascii=False))
            pins = self.http("GET", "/api/admin/home-pins/draft")
            saved = self.http("PATCH", "/api/admin/home-pins/draft", {"base_version": pins["version"], "changes": {"article_ids": [self.article]}})
            self.http("POST", "/api/admin/home-pins/publish", {"base_version": saved["version"]})
            self.assertion("home pins publish actual ordered selection", self.db("SELECT article_page_id FROM home_pins ORDER BY sort_order")[0]["article_page_id"] == self.article)
            news = self.http("GET", "/api/admin/news-intro")
            saved = self.http("PATCH", "/api/admin/news-intro", {"base_version": news["version"], "changes": {"intro_md": "真实资讯栏目介绍。"}})
            self.http("POST", "/api/admin/news-intro/publish", {"base_version": saved["version"]})
            public = self.http("GET", "/api/page/news", actor=None)
            self.assertion("news intro publishes actual saved draft", "真实资讯栏目介绍" in json.dumps(public, ensure_ascii=False))

    def images(self):
        with self.group("image upload, metadata, collections and deletion protection"):
            from PIL import Image
            collections = self.http("GET", "/api/admin/image-collections")["collections"]
            root_collection = next(row["id"] for row in collections if row["parent_id"] is None)
            parent = self.http("POST", "/api/admin/image-collections", {"name": "旅程父集合", "parent_id": root_collection})["collection"]
            child = self.http("POST", "/api/admin/image-collections", {"name": "旅程子集合", "parent_id": parent["id"]})["collection"]
            self.http("DELETE", f"/api/admin/image-collections/{parent['id']}", expect=422)
            buffer = io.BytesIO()
            Image.new("RGB", (64, 64), (32, 96, 160)).save(buffer, format="PNG")
            uploaded = self.http("POST", "/api/admin/images/upload", {"title": "真实上传图片", "collection_key": "contributed",
                "file_name": "fictional.png", "data_url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()})["image"]
            edit = self.http("PATCH", f"/api/admin/images/{uploaded['id']}", {"base_version": uploaded["version"],
                "changes": {"title": "修改后的图片", "collection_id": child["id"]}})
            self.assertion("image edit persists metadata in actual table", self.db("SELECT title,collection_id FROM images WHERE id=?", (uploaded["id"],))[0] == {"title": "修改后的图片", "collection_id": child["id"]})
            self.http("DELETE", f"/api/admin/image-collections/{child['id']}", expect=422)
            self.http("PATCH", f"/api/admin/images/{uploaded['id']}", {"base_version": uploaded["version"], "changes": {"title": "陈旧覆盖"}}, expect=409)
            self.http("DELETE", f"/api/images/{uploaded['id']}")
            self.http("DELETE", f"/api/admin/image-collections/{child['id']}")
            self.http("DELETE", f"/api/admin/image-collections/{parent['id']}")
            self.assertion("image and empty child collection deletions persist", not self.db("SELECT id FROM images WHERE id=?", (uploaded["id"],)) and not self.db("SELECT id FROM image_collections WHERE id=?", (child["id"],)))

    def settings(self):
        with self.group("settings partial save, secrets, stale projection and dynamic SMTP"):
            old = self.http("GET", "/api/admin/settings")["settings"]
            partial = self.http("PATCH", "/api/admin/settings", {"base_version": old["version"],
                "changes": {"site_description": "  真实旅程简介  ", "smtp_port": 0}})
            self.assertion("partial save applies only valid settings field", partial["saved"] == ["site_description"] and partial["fields"].get("smtp_port") and partial["values"]["smtp_port"] == old["smtp_port"])
            self.http("PATCH", "/api/admin/settings", {"base_version": old["version"], "changes": {"site_description": "陈旧覆盖"}}, expect=409)
            password = "fictional-journey-smtp-secret"
            secret = self.http("PATCH", "/api/admin/settings", {"smtp_password": password})
            check(secret["settings"]["has_smtp_password"], "explicit SMTP secret not saved")
            stored = self.db("SELECT smtp_password FROM site_settings WHERE id=1")[0]["smtp_password"]
            self.assertion("SMTP secret is encrypted and never echoed", stored and stored != password and password not in json.dumps(secret) and stored not in json.dumps(secret))
            self.http("PATCH", "/api/admin/settings", {"smtp_password": ""})
            self.assertion("empty explicit SMTP secret preserves ciphertext", self.db("SELECT smtp_password FROM site_settings WHERE id=1")[0]["smtp_password"] == stored)
            stale = self.http("PATCH", "/api/admin/settings", {"base_version": old["version"], "changes": {"from_name": "陈旧覆盖"}}, expect=409)
            self.assertion("409 safe current projection excludes password and ciphertext", "current" in stale and password not in json.dumps(stale) and stored not in json.dumps(stale))
            self.http("PATCH", "/api/admin/settings", {"clear_smtp_password": True})
            current = self.http("GET", "/api/admin/settings")["settings"]
            saved = self.http("PATCH", "/api/admin/settings", {"base_version": current["version"], "changes": {
                "smtp_host": "127.0.0.1", "smtp_port": self.smtp[1].server_address[1], "smtp_security": "none",
                "smtp_username": "", "from_address": "site@example.test", "from_name": "本地旅程邮件"}})
            check(not saved.get("fields"), "local SMTP settings failed validation")
            before = len(self.smtp[1].records)
            self.http("POST", "/api/admin/settings/test-email")
            for _ in range(50):
                if len(self.smtp[1].records) > before:
                    break
                time.sleep(0.1)
            self.assertion("test mail uses DB SMTP instead of environment fallback", len(self.smtp[1].records) == before + 1 and self.smtp[1].records[-1]["recipients"] == ["officer@screens.test"])
            audits = self.db("SELECT data FROM audit_log WHERE object_type='site_settings'")
            self.assertion("settings audit excludes submitted secret and encrypted token", audits and all(password not in row["data"] and stored not in row["data"] for row in audits))
        with self.group("backup saved prerequisites, secret action and safe projection without S3"):
            page = self.http("GET", "/api/admin/settings/backup")
            result = self.http("PATCH", "/api/admin/settings/backup", {"base_version": page["version"], "changes": {"enabled": True, "retention_days": 30}})
            self.assertion("backup enabling waits for complete saved credentials", not result["values"]["enabled"] and result["fields"].get("enabled") and result["values"]["retention_days"] == 30)
            secret = self.http("POST", "/api/admin/settings/backup/secret", {"secret_access_key": "fictional-s3-secret"})
            stored = self.db("SELECT secret_access_key FROM backup_settings WHERE id=1")[0]["secret_access_key"]
            projection = self.http("GET", "/api/admin/settings/backup")
            self.assertion("backup secret POST returns only presence and version", secret["has_secret_access_key"] and stored != "fictional-s3-secret" and "fictional-s3-secret" not in json.dumps(projection) and stored not in json.dumps(projection))
            # We deliberately never call test-storage or any worker remote upload.
            self.http("POST", "/api/admin/settings/backup/secret", {"clear": True})
            projection = self.http("GET", "/api/admin/settings/backup")
            self.assertion("explicit backup secret clear leaves backups disabled", not projection["values"]["has_secret_access_key"] and not projection["values"]["enabled"])

    def build_font_package(self):
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        builder = FontBuilder(1024, isTTF=True)
        builder.setupGlyphOrder([".notdef", "space", "A"])
        builder.setupCharacterMap({32: "space", 65: "A"})
        pen = TTGlyphPen(None)
        pen.moveTo((100, 0)); pen.lineTo((500, 800)); pen.lineTo((900, 0)); pen.closePath()
        blank = TTGlyphPen(None).glyph()
        builder.setupGlyf({".notdef": blank, "space": blank, "A": pen.glyph()})
        builder.setupHorizontalMetrics({name: (1024, 0) for name in [".notdef", "space", "A"]})
        builder.setupHorizontalHeader(ascent=800, descent=-224)
        builder.setupNameTable({"familyName": "JourneyFixture", "styleName": "Regular", "uniqueFontIdentifier": "JourneyFixture-Regular", "fullName": "JourneyFixture Regular", "psName": "JourneyFixture-Regular", "version": "Version 1.0"})
        builder.setupOS2(sTypoAscender=800, sTypoDescender=-224, usWinAscent=800, usWinDescent=224, fsType=0)
        builder.setupPost()
        original = self.work / "font-fixture.ttf"
        builder.save(original)
        spec = importlib.util.spec_from_file_location("round290_font_package", self.repo / "server/internal/fonts/offline_package.py")
        check(spec is not None and spec.loader is not None, "offline D4 tool unavailable")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        files = tool.build("JourneyFixture", "真实旅程字体", "OFL fictional fixture", [(400, "normal", original)])
        package = self.work / "font-fixture.zip"
        tool.write_package(package, files)
        return package.read_bytes()

    def fonts(self):
        with self.group("actual offline font package, owner-bound chunks and nine-region CSS"):
            package = self.build_font_package()
            upload = self.http("POST", "/api/admin/fonts/uploads", {"name": "fixture.zip", "total_bytes": len(package), "license_confirmed": True})
            self.http("POST", f"/api/admin/fonts/uploads/{upload['id']}/chunks", {"offset": 0, "data_base64": base64.b64encode(package[:upload["chunk_size"]]).decode()}, actor="auxsuper", expect=404)
            self.assertion("different superuser cannot write another owner's font upload", True)
            for offset in range(0, len(package), upload["chunk_size"]):
                chunk = {"offset": offset, "data_base64": base64.b64encode(package[offset:offset + upload["chunk_size"]]).decode()}
                key = str(uuid.uuid4())
                self.http("POST", f"/api/admin/fonts/uploads/{upload['id']}/chunks", chunk, key=key)
                self.http("POST", f"/api/admin/fonts/uploads/{upload['id']}/chunks", chunk, key=key)
            imported = self.http("POST", "/api/admin/fonts", {"source": "package", "package_name": "fixture.zip", "upload_id": upload["id"], "license_confirmed": True})
            self.font = imported["font"]["id"]
            self.assertion("real offline package imports ready normal weight and actual slices", imported["font"]["weights"] == [400] and imported["font"]["slices"] > 0 and imported["font"]["bytes"] > 48)
            page = self.http("GET", "/api/admin/typography")
            check(len(page["regions"]) == 9, "typography must include nine actual regions")
            rows = page["regions"]
            for row in rows:
                if row["region"] == "body":
                    row.update(mode="custom", family_id=self.font, weight=400)
            saved = self.http("PATCH", "/api/admin/typography", {"base_version": page["version"], "changes": {"regions": rows}})
            self.http("PATCH", "/api/admin/typography", {"base_version": page["version"], "changes": {"regions": rows}}, expect=409)
            actual = self.http("GET", "/api/admin/typography")
            css_path = actual["css_path"]
            check(css_path.startswith("/media/fonts/css/"), "generated CSS must be same-origin font artifact")
            css_file = (self.work / "media" / css_path.removeprefix("/media/")).resolve()
            check(css_file.is_relative_to((self.work / "media").resolve()), "CSS path escaped test media")
            css = css_file.read_text()
            self.assertion("nine-region stylesheet contains real font faces and variables", "@font-face" in css and all("--font-" + suffix + ":" in css for suffix in ["body", "h1", "h2", "h3", "h4", "nav", "button", "numeric", "code"]))
            preview = self.http("POST", "/api/admin/typography/preview", {"regions": rows})
            preview_text = (self.work / "media" / preview["css_path"].removeprefix("/media/")).read_text()
            self.assertion("draft font preview is scoped and leaves stored version untouched", "#typography-preview {" in preview_text and ":root {" not in preview_text and self.http("GET", "/api/admin/typography")["version"] == actual["version"])
            self.http("DELETE", f"/api/admin/fonts/{self.font}", expect=422)
            for row in rows:
                row.update(mode="system", family_id=None)
            self.http("PATCH", "/api/admin/typography", {"base_version": actual["version"], "changes": {"regions": rows}})
            self.http("DELETE", f"/api/admin/fonts/{self.font}")
            self.assertion("font deletion follows actual reference release", not self.db("SELECT id FROM font_families WHERE id=?", (self.font,)))

    def registrations(self):
        with self.group("real tournament registration, global review, partial batch and CSV audit"):
            now = datetime.now(timezone.utc)
            created = self.http("POST", "/api/admin/tournaments", actor="captain")["tournament"]
            event = created["id"]
            saved = self.http("PATCH", f"/api/admin/tournaments/{event}", {"base_version": created["version"], "changes": {
                "title": "接口旅程战队杯", "description": "仅虚构测试报名。", "registration_mode": "team", "roster_min": 3,
                "roster_max": 3, "auto_approve": False, "starts_at": utc(now + timedelta(days=2)),
                "registration_opens_at": utc(now - timedelta(hours=1)), "registration_closes_at": utc(now + timedelta(days=1))}}, actor="captain")
            check(not saved.get("fields"), "tournament draft invalid; inspect HTTP evidence")
            self.http("POST", f"/api/admin/tournaments/{event}/publish", actor="captain")
            team = self.http("GET", "/api/teams/1", actor="captain")
            form = self.http("GET", f"/api/tournaments/{event}/register?team=1", actor="captain")
            selections = {str(row["user_id"]): row["selected_account_id"] for row in form["rows"]}
            check(form["can_submit"], "real roster form is blocked; inspect HTTP evidence")
            registration = self.http("POST", f"/api/tournaments/{event}/registrations", {"team_id":1,
                "accounts":selections,"base_team_version":form["team"]["version"]}, actor="captain")["registration"]
            review = self.http("GET", "/api/admin/registrations?" + urlencode({"tournament_id": event, "status": "pending"}), actor="captain")
            self.assertion("global review includes real submitted pending registration", any(row["id"] == registration["id"] for row in review["items"]))
            receipt = self.http("POST", "/api/admin/registrations/bulk-approve", {"ids": [registration["id"], 999999999]}, actor="captain")
            self.assertion("partial bulk result matches actual approved transition and missing-ID failure", receipt["approved"] == [registration["id"]] and len(receipt["failed"]) == 1 and self.db("SELECT status FROM registrations WHERE id=?", (registration["id"],))[0]["status"] == "approved")
            detail = self.http("GET", f"/api/admin/registrations/{registration['id']}", actor="captain")
            self.assertion("global registration detail has real frozen roster and status log", len(detail["roster"]) == 3 and any(row["action"] == "通过" for row in detail["logs"]))
            exported = self.http("POST", "/api/admin/registrations/export?" + urlencode({"tournament_id": event}), actor="captain")
            self.assertion("real CSV contains authorized roster and records export audit", "截图队长" in exported["csv"] and "联系方式" in exported["csv"] and bool(self.db("SELECT id FROM audit_log WHERE action='registration.export' AND object_id=?", (event,))))
            self.http("GET", f"/api/admin/registrations/{registration['id']}", actor="member", expect=403)
            self.assertion("ordinary participant cannot use global admin registration detail", True)

    def run(self):
        self.navigation()
        self.content()
        self.images()
        self.settings()
        self.fonts()
        self.registrations()
        summary = {"transport": "real HTTP to temporary Go serve", "database": "real temporary SQLite",
            "smtp": "two loopback-only captured servers", "external_google_s3": "not called",
            "results": self.results, "passed": sum(row["status"] == "passed" for row in self.results),
            "failed": sum(row["status"] == "failed" for row in self.results), "work_dir": str(self.work)}
        (self.work / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False), flush=True)
        return 1 if summary["failed"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True, help="existing tested Go binary; no build is performed")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--work-dir", type=Path, help="new empty temporary output directory; never point at a site data directory")
    args = parser.parse_args()
    binary = args.binary.resolve()
    check(binary.is_file() and os.access(binary, os.X_OK), "provided binary is missing or not executable")
    if args.work_dir:
        work = args.work_dir.resolve()
        check(not work.exists(), "--work-dir must not already exist")
        work.mkdir(parents=True, mode=0o700)
    else:
        work = Path(tempfile.mkdtemp(prefix="sjtuow-290-api-journey-"))
    journey = Journey(args.repo.resolve(), binary, work)
    status = 1
    try:
        journey.start()
        status = journey.run()
    except Exception as error:
        (work / "startup-error.txt").write_text(str(error))
        print("FAIL setup", str(error), flush=True)
    finally:
        journey.close()
        print("API-JOURNEY-WORK", str(work), flush=True)
    return status


if __name__ == "__main__":
    sys.exit(main())
