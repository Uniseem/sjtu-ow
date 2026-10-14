"""Prepare private next-stack host files from the live legacy environment."""
import json
import os
from pathlib import Path
import shutil
import subprocess

os.umask(0o077)
root = Path("/srv/sjtu-ow")
container = subprocess.check_output(["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=sjtu-ow", "--filter", "label=com.docker.compose.service=web"], text=True).split()
if len(container) != 1:
    raise SystemExit("Expected one live legacy web")
details = json.loads(subprocess.check_output(["docker", "inspect", container[0]], text=True))[0]
legacy = dict(item.split("=", 1) for item in details["Config"]["Env"] if "=" in item)
required = {"SITE_URL": "SITE_URL", "SIGNING_KEY": "DJANGO_SECRET_KEY", "FIELD_ENCRYPTION_KEY": "FIELD_ENCRYPTION_KEY"}
values = {}
for target, source in required.items():
    value = legacy.get(source, "")
    if not value or target.endswith("KEY") and len(value) < 32:
        raise SystemExit("Missing valid legacy configuration: " + source)
    values[target] = value
values["BACKUP_ENCRYPTION_KEY"] = legacy.get("BACKUP_ENCRYPTION_KEY", "")
values.update(SJTUOW_ENV="prod", MEDIA_VOLUME="sjtu-ow-next_media", PORT="22887", EMAIL_ALLOWLIST="", TEST_ENVIRONMENT="false")
for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_SECURITY"):
    values[key] = legacy.get(key, "")
values["SMTP_PORT"] = values["SMTP_PORT"] or "587"
values["SMTP_SECURITY"] = values["SMTP_SECURITY"] or "starttls"
environment = root / ".env.next"
if environment.exists():
    raise SystemExit("Next environment already exists; review it before replacing")
for value in values.values():
    if "\n" in value or "\r" in value:
        raise SystemExit("Invalid multiline environment value")
environment.write_text("".join(key + "='" + value.replace("\\", "\\\\").replace("'", "\\'") + "'\n" for key, value in values.items()))
environment.chmod(0o600)
shutil.copyfile(root / "deploy/Caddyfile.new", root / "deploy/Caddyfile.next-vps")
(root / "deploy/docker-compose.next-vps.yml").write_text("""services:
  server:
    image: sjtu-ow-next-server:301
    build: !reset null
  worker:
    image: sjtu-ow-next-server:301
    build: !reset null
  web:
    image: sjtu-ow-next-web:301
    build: !reset null
  proxy:
    ports: !override ["22887:80"]
    environment:
      CADDY_SITE_ADDRESS: ":80"
    volumes: !override
      - ./Caddyfile.next-vps:/etc/caddy/Caddyfile:ro
      - ./error_pages:/srv/error_pages:ro
      - sjtuow_media:/var/media:ro
      - sjtuow_assets:/var/assets:ro
""")
exclude = root / ".git/info/exclude"
text = exclude.read_text()
for line in ("/.env.next", "/deploy/docker-compose.next-vps.yml", "/deploy/Caddyfile.next-vps"):
    if line not in text.splitlines():
        text += "\n" + line + "\n"
exclude.write_text(text)
print("HOST-NEXT-CONFIG-PREPARED secrets-not-output", flush=True)
subprocess.run(["docker", "compose", "-p", "sjtu-ow-next", "-f", str(root / "deploy/docker-compose.new.yml"), "-f", str(root / "deploy/docker-compose.next-vps.yml"), "--env-file", str(environment), "config", "--quiet"], check=True)
print("HOST-NEXT-COMPOSE-VALID", flush=True)
