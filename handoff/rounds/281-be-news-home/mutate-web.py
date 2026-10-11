"""验证本轮前端接入规则，不以实现镜像测试替代真正 SSR 输出。"""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[3]
site=root/'web/apps/site'
cases=[
 ('首页读取聚合安排','Home.vue','const agenda = home.agenda ?? []','const agenda = []'),
 ('日历日保留前导零','Home.vue','owDay(new Date(scrim.starts_at))','scrim.day'),
 ('资讯SEO标题','News.vue','data?.data?.seo_title || data?.title','data?.title'),
 ('零页码取最后一页','News.vue','numeric === 0 ? -1 : numeric','numeric === 0 ? 1 : numeric'),
 ('推荐默认封面沿用漂移类','Home.vue','!feature.cover_image_id && feature.default_cover_image_id ?','!feature.cover_image_id && false ?'),
]
for name,rel,old,new in cases:
 p=site/'src/pages'/rel;baseline=p.read_text()
 if old not in baseline:raise SystemExit(f'missing anchor: {name}')
 try:
  p.write_text(baseline.replace(old,new,1))
  built=subprocess.run(['pnpm','exec','vite','build','--ssr','server.ts','--outDir','dist/mutation-281'],cwd=site,capture_output=True,text=True)
  if built.returncode:raise SystemExit(f'INVALID {name}: {built.stdout}{built.stderr}')
  result=subprocess.run(['pnpm','exec','vitest','run','src/content.test.ts'],cwd=site,capture_output=True,text=True)
  if result.returncode==0:raise SystemExit(f'SURVIVED {name}')
  print(f'CAUGHT {name}',flush=True)
 finally:p.write_text(baseline)
print(f'WEB-MUTATIONS-OK {len(cases)}',flush=True)
