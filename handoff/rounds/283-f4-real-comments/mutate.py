"""递归生成的规则变异先编译，再被回归抓住。"""
from pathlib import Path
import subprocess
server=Path(__file__).resolve().parents[3]/'server'
cases=[
 ('cycle references','internal/platform/apigen/apigen.go','out = named[0][t]','out = "unknown"'),
 ('nullable recursion','internal/platform/apigen/apigen.go','if nullable {','if nullable && (len(named)==0 || named[0][t]=="") {'),
 ('complete cycle component','internal/platform/apigen/recursive.go','for _, item := range stack[at:] {','for _, item := range stack[at:at+1] {'),
]
cases=[(*case,"platform/apigen","TestRecursiveJSONTypes") for case in cases]
cases.append(("daily edit allowance","internal/comments/api.go",'api.Patch(r, "/api/comments/{id}", api.Member, m.patchComment,\n\t\tapi.Limit(ratelimit.CommentCreateMinute, ratelimit.CommentCreateDaily))','api.Patch(r, "/api/comments/{id}", api.Member, m.patchComment,\n\t\tapi.Limit(ratelimit.CommentCreateMinute))',"comments","TestCommentEditDailyLimit"))
for name,rel,old,new,module,test in cases:
 p=server/rel;baseline=p.read_text()
 if old not in baseline:raise SystemExit(f'missing anchor {name}')
 try:
  p.write_text(baseline.replace(old,new,1))
  built=subprocess.run(['go','test',f'./internal/{module}','-run','^$'],cwd=server,capture_output=True,text=True)
  if built.returncode:raise SystemExit(f'INVALID {name}: {built.stdout}{built.stderr}')
  result=subprocess.run(['go','test',f'./internal/{module}','-run',test,'-count=1'],cwd=server,capture_output=True,text=True)
  if result.returncode==0:raise SystemExit(f'SURVIVED {name}')
  print(f'CAUGHT {name}',flush=True)
 finally:p.write_text(baseline)
print(f'MUTATIONS-OK {len(cases)}',flush=True)
