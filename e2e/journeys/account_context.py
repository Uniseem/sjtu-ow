"""Fresh fictional account GET contexts for the real seven-role page walk."""
import json
import os
from pathlib import Path
import sys
import urllib.parse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'parity'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import parity
from account_scenarios import context

config=json.loads(Path(sys.argv[1]).read_text())
name,role,path=sys.argv[2:5]
os.environ['DJANGO_SECRET_KEY']=parity.TEST_SIGNING_KEY
old,new,suffix=context(name,role,config['data'],config['sessions'],Path(config['work']),config['legacy_env'])
path+=suffix
cookies='; '.join(item['name']+'='+item['value'] for item in old)
status,location=parity.fetch_status(config['old_base']+urllib.parse.quote(path,safe='/?=&#%'),cookies)
print(json.dumps({'path':path,'status':status,'location':location,'cookies':new}))
