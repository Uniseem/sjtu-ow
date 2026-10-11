"""运行时SSR验证edited_at和null过滤，不只检查源代码字符串。"""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[3];site=root/'web/apps/site'
cases=[
 ('root edit marker','web/packages/ui/src/CCommentItem.vue','v-if="item.edited_at"','v-if="item.updated_at !== item.created_at"'),
 ('reply edit marker','web/packages/ui/src/CCommentReply.vue','v-if="reply.edited_at"','v-if="false"'),
 ('null root filter','web/packages/ui/src/CComments.vue','item !== null','true'),
 ('null reply filter','web/packages/ui/src/CCommentItem.vue','reply !== null','true'),
]
for name,rel,old,new in cases:
 p=root/rel;baseline=p.read_text()
 if old not in baseline:raise SystemExit(f'missing anchor {name}')
 try:
  p.write_text(baseline.replace(old,new,1))
  built=subprocess.run(['pnpm','exec','vite','build','--ssr','server.ts','--outDir','dist/mutation-283'],cwd=site,capture_output=True,text=True)
  if built.returncode:raise SystemExit(f'INVALID {name}: {built.stdout}{built.stderr}')
  result=subprocess.run(['pnpm','exec','vitest','run','src/content.test.ts'],cwd=site,capture_output=True,text=True)
  if result.returncode==0:raise SystemExit(f'SURVIVED {name}')
  print(f'CAUGHT {name}',flush=True)
 finally:p.write_text(baseline)
print(f'WEB-MUTATIONS-OK {len(cases)}',flush=True)
