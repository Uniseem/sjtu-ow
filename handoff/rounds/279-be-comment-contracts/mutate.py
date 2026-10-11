"""测试机上逐一变异，要求先编译成功，再由本轮回归抓住。"""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
server = root / 'server'
cases = [
 ('邮箱错误合并进评论权限','internal/accounts/api.go','CanComment:       ctx.Viewer.CanUse(FeatureArticleComment)','CanComment:       ctx.Viewer.EmailVerified && ctx.Viewer.CanUse(FeatureArticleComment)','accounts','TestSessionComment'),
 ('忽略评论功能禁用','internal/accounts/api.go','CanComment:       ctx.Viewer.CanUse(FeatureArticleComment)','CanComment:       true','accounts','TestSessionComment'),
 ('投影遗漏编辑时间','internal/comments/store.go','c.EditedAt = &at','_ = at; c.EditedAt = nil','comments','TestCommentEditedAtContract'),
 ('作者编辑不记录时间','internal/comments/store.go','updated_at = ?, edited_at = ?','updated_at = ?, edited_at = NULLIF(?, ?)','comments','TestCommentEditedAtContract'),
 ('管理隐藏伪造编辑时间','internal/comments/store.go','SET is_hidden = ?, is_pinned = 0, version = version + 1, updated_at = ?','SET is_hidden = ?, is_pinned = 0, version = version + 1, edited_at = updated_at, updated_at = ?','comments','TestCommentEditedAtContract'),
 ('置顶覆盖编辑时间','internal/comments/store.go','SET is_pinned = 1, version = version + 1, updated_at = ?','SET is_pinned = 1, version = version + 1, edited_at = created_at, updated_at = ?','comments','TestCommentEditedAtContract'),
 ('未改正文伪造编辑时间','internal/comments/service.go','!comment.IsHidden && !comment.IsDeleted && content == comment.Content','!comment.IsHidden && !comment.IsDeleted && content == "__never__"','comments','TestCommentEditedAtContract'),
 ('旧库编辑时间丢失','internal/content/import.go','editedUTC = updatedUTC','editedUTC = nil','content','TestImportCommentEditedAt'),
 ('已有评论虚构编辑历史','db/migrations/00019_comment_edited_at.sql','ALTER TABLE comments ADD COLUMN edited_at TEXT;','ALTER TABLE comments ADD COLUMN edited_at TEXT;\nUPDATE comments SET edited_at = updated_at;','platform/db','TestCommentEditedAtUpgrade'),
]
for name, rel, old, new, module, test in cases:
 p = server / rel
 baseline = p.read_text()
 if old not in baseline: raise SystemExit(f'missing anchor: {name}')
 changed=baseline.replace(old,new,1)
 # 保持参数个数合法，NULLIF(now, now) 专门模拟作者编辑写回 NULL。
 if name=='作者编辑不记录时间':
  changed=changed.replace('newContent, now, now, id, authorID','newContent, now, now, now, id, authorID',1)
 try:
  p.write_text(changed)
  compile_result=subprocess.run(['go','test',f'./internal/{module}','-run','^$'],cwd=server,capture_output=True,text=True)
  if compile_result.returncode: raise SystemExit(f'INVALID {name}: {compile_result.stdout} {compile_result.stderr}')
  result=subprocess.run(['go','test',f'./internal/{module}','-run',test,'-count=1'],cwd=server,capture_output=True,text=True)
  if not result.returncode: raise SystemExit(f'SURVIVED {name}')
  print(f'CAUGHT {name}',flush=True)
 finally: p.write_text(baseline)
print(f'MUTATIONS-OK {len(cases)}',flush=True)
