"""No exclusions or weaker flags: Vue props/API keys/nullability must be checked."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
web = root / 'web'
probe = web / 'packages/ui/src/StrictTypeProbe.vue'
cases = [
    ('valid API and Vue template', '''<script setup lang="ts">
import CSeats from './CSeats.vue'
import { getApiTeams, type Requester, type GetApiPageHomeOut } from '@sjtu-ow/api'
declare const api: Requester
declare const home: GetApiPageHomeOut
getApiTeams(api, { recruiting: true })
home.scrims.filter((row): row is NonNullable<typeof row> => row !== null).map(row => row.id)
</script><template><CSeats :taken="1" :total="10" data-probe="yes" /></template>''', None),
    ('unknown API query', '''<script setup lang="ts">
import { getApiTeams, type Requester } from '@sjtu-ow/api'
declare const api: Requester
getApiTeams(api, { imaginary_query: true })
</script><template><p>probe</p></template>''', 'imaginary_query'),
    ('nullable API item', '''<script setup lang="ts">
import type { GetApiPageHomeOut } from '@sjtu-ow/api'
declare const home: GetApiPageHomeOut
home.scrims.map(row => row.id)
</script><template><p>probe</p></template>''', 'possibly'),
    ('unknown Vue prop', '''<script setup lang="ts">
import CSeats from './CSeats.vue'
</script><template><CSeats :taken="1" :total="10" imaginary_prop="no" /></template>''', 'imaginary_prop'),
    ('wrong Vue prop value', '''<script setup lang="ts">
import CSeats from './CSeats.vue'
</script><template><CSeats taken="wrong" :total="10" /></template>''', 'not assignable'),
]
try:
    for name, source, expected in cases:
        probe.write_text(source)
        result = subprocess.run(['pnpm', 'typecheck', '--pretty', 'false'], cwd=web, capture_output=True, text=True)
        output = result.stdout + result.stderr
        if expected is None:
            if result.returncode:
                raise SystemExit('INVALID positive type probe\n' + output)
        elif result.returncode == 0 or 'StrictTypeProbe.vue' not in output or expected not in output:
            raise SystemExit('SURVIVED/INVALID ' + name + '\n' + output)
        print('TYPE-PROBE-OK ' + name, flush=True)
finally:
    probe.unlink(missing_ok=True)
