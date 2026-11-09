"""Real Go/SSR/Caddy specimens, with fictional data and a round-owned namespace."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "e2e/parity"))
import parity

WORK = Path(os.environ.get("POLISH_WORK", "/srv/build/sjtu-ow/305-fixture"))
phase = sys.argv[1] if len(sys.argv) > 1 else "after"
output = WORK.parent / ("305-" + phase)
WORK.mkdir(parents=True, exist_ok=True)
output.mkdir(parents=True, exist_ok=True)
parity.WORK = WORK
parity.OUT = WORK / "out"
parity.SHOTS = parity.OUT / "shots"
parity.screens.WORK = WORK
os.environ["PARITY_WORK"] = str(WORK)
os.environ["DJANGO_SECRET_KEY"] = parity.TEST_SIGNING_KEY
os.environ["SITE_URL"] = parity.TEST_SITE_URL
container = "ow-polish-305"
processes = []
logs = []

try:
    seed_file = WORK / "seed.json"
    if not seed_file.exists():
        data = parity.prepare_legacy()
        seed_file.write_text(json.dumps(data))
    data = json.loads(seed_file.read_text())
    api, ssr, caddy = [parity.screens.free_port() for _ in range(3)]
    env = parity.new_env(api)
    env.update(SITE_URL=f"http://127.0.0.1:{caddy}", EMAIL_ALLOWLIST=".test")
    session_file = WORK / "sessions.json"
    if not session_file.exists():
        sessions = parity.prepare_new(env)
        session_file.write_text(json.dumps(sessions))
    sessions = json.loads(session_file.read_text())
    assets = WORK / "assets"
    if assets.exists():
        assets.rename(WORK / ("assets-prev-" + str(time.time_ns())))
    parity.assets_dir()
    for name, args, cwd, child_env in [
        ("api", [str(WORK / "sjtuow"), "serve"], ROOT, env),
        ("ssr", ["node", "dist/server/server.js"], ROOT / "web/apps/site", {**os.environ, "NODE_ENV": "production", "PORT": str(ssr), "API_BASE": f"http://127.0.0.1:{api}"}),
    ]:
        log = (output / (name + ".log")).open("w")
        logs.append(log)
        processes.append(subprocess.Popen(args, cwd=cwd, env=child_env, stdout=log, stderr=subprocess.STDOUT))
    subprocess.run([
        "docker", "run", "-d", "--name", container, "--network", "host",
        "-e", f"CADDY_SITE_ADDRESS=http://127.0.0.1:{caddy}",
        "-e", f"API_UPSTREAM=127.0.0.1:{api}", "-e", f"SSR_UPSTREAM=127.0.0.1:{ssr}",
        "-v", f"{ROOT}/deploy/Caddyfile.new:/etc/caddy/Caddyfile:ro",
        "-v", f"{ROOT}/deploy/error_pages:/srv/error_pages:ro",
        "-v", f"{assets}:/var/assets:ro", "-v", f"{WORK}/media:/var/media:ro",
        "caddy:2.10-alpine",
    ], check=True, stdout=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{caddy}"
    parity.screens.wait_for(base + "/robots.txt")
    config = output / "config.json"
    config.write_text(json.dumps({"base": base, "sessions": sessions, "data": data, "phase": phase, "output": str(output)}))
    script = Path(__file__).with_name(os.environ.get("POLISH_BROWSER", "browser.mjs"))
    command = ["node", str(script), str(config), str(ROOT)]
    if os.environ.get("UI_ENGINE") == "webkit":
        browser_tool = Path(os.environ.get("POLISH_PLAYWRIGHT", str(ROOT / "web")))
        version = json.loads((browser_tool / "node_modules/playwright/package.json").read_text())["version"]
        command = [
            "docker", "run", "--rm", "--init", "--name", "ow-polish-305-webkit", "--network", "host", "--ipc=host",
            "-e", "UI_ENGINE=webkit", "-e", f"POLISH_PLAYWRIGHT={browser_tool}",
            "-v", f"{browser_tool}:{browser_tool}:ro", "-v", f"{ROOT}:{ROOT}:ro", "-v", f"{output}:{output}",
            "-v", "/usr/share/fonts:/usr/share/fonts:ro", "-w", str(ROOT),
            f"mcr.microsoft.com/playwright:v{version}-noble", *command,
        ]
    subprocess.run(command, cwd=ROOT, check=True)
finally:
    subprocess.run(["docker", "rm", "-f", "ow-polish-305-webkit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for process in processes:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    for log in logs:
        log.close()
