"""One retained WebKit operation check, using fictional seeded data only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "e2e/parity"))
import parity


def main():
    work = Path(tempfile.mkdtemp(prefix="sjtuow-300-operations-"))
    parity.WORK = work
    parity.OUT = work / "out"
    parity.SHOTS = parity.OUT / "shots"
    parity.screens.WORK = work
    processes = []
    success = False
    try:
        parity.SHOTS.mkdir(parents=True)
        os.environ["DJANGO_SECRET_KEY"] = parity.TEST_SIGNING_KEY
        os.environ["SITE_URL"] = parity.TEST_SITE_URL
        data = parity.prepare_legacy()
        # Build fixtures directly. Registration/SMTP journeys already passed298.
        seeded = subprocess.run(
            [sys.executable, "manage.py", "shell", "-c", """
from django.utils import timezone
from allauth.account.models import EmailAddress
from accounts.models import User, GameAccount, ContactMethod, ContactType
from scrims.models import Scrim
from scrims.services import sign_up
from tournaments.models import Tournament
from tournaments.registration import sign_up_individual
now = timezone.now()
scrim = Scrim.objects.get(pk=%d)
cup = Tournament.objects.get(pk=%d)
for index in range(1, 10):
    email = f'operations{index}@example.test'
    user = User.objects.create_user(email=email, password=None, nickname=f'操作队员{index}', is_sjtu=True, main_role='support', agreed_terms_at=now, agreed_cross_border_at=now)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    account = GameAccount.objects.create(user=user, battletag=f'Operations{index}#12345', rank_tank=20, rank_damage=20, rank_support=20)
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value='123456789')
    sign_up(scrim=scrim, user=user, game_account_id=account.pk, roles=['tank','damage','support'])
    if index <= 2:
        sign_up_individual(tournament=cup, user=user, game_account_id=account.pk, roles=['support'])
print('DIRECT-FICTIONAL-FIXTURE-READY')
""" % (data["scrim"], data["cup"])],
            cwd=ROOT, env=parity.screens.site_env(), capture_output=True, text=True,
        )
        if seeded.returncode:
            raise RuntimeError(seeded.stderr)
        print(seeded.stdout.strip(), flush=True)
        api, ssr, caddy = [parity.screens.free_port() for _ in range(3)]
        env = parity.new_env(api)
        env.update(SITE_URL=f"http://127.0.0.1:{caddy}", EMAIL_ALLOWLIST=".test")
        sessions = parity.prepare_new(env)
        # No worker: held-letter confirmation is real, outbound mail stays queued.
        processes.extend(parity.start_new(env, api, ssr, caddy))
        parity.screens.wait_for(env["SITE_URL"] + "/robots.txt")
        config = work / "config.json"
        config.write_text(json.dumps({"base": env["SITE_URL"], "work": str(work), "sessions": sessions, "data": data, "only": sys.argv[1] if len(sys.argv) > 1 else "all"}))
        print("OPERATIONS-FIXTURE " + str(work), flush=True)
        subprocess.run(["node", str(Path(__file__).with_name("operations.mjs")), str(config)], cwd=ROOT, check=True)
        success = True
    finally:
        subprocess.run(["docker", "rm", "-f", "ow-parity-caddy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if success:
            retired = work.with_name(work.name + "-retired")
            work.rename(retired)
            shutil.rmtree(retired)
            print("OPERATIONS-FIXTURE-REMOVED", flush=True)
        else:
            print("OPERATIONS-FAILED-FIXTURE-KEPT " + str(work), flush=True)


if __name__ == "__main__":
    main()
