"""每项先编译，再由对应回归抓住；在测试机后台执行。"""
from pathlib import Path
import subprocess

server=Path(__file__).resolve().parents[3]/'server'
news='internal/content/news_page.go'
home='internal/content/home_store.go'
authors='internal/content/news_authors.go'
cases=[
 ('列表栏目公开门',news,"p.slug='news' AND p.live=1 AND p.search_public=1","p.slug='news' AND p.search_public=1",'TestNewsPageGate'),
 ('列表栏目限制门',news,"p.slug='news' AND p.live=1 AND p.search_public=1","p.slug='news' AND p.live=1",'TestNewsPageGate'),
 ('列表同栏目',news,'AND p.parent_id=?','AND ? IS NOT NULL','TestNewsPageAPI'),
 ('列表排除草稿',news,"where := `p.kind='article' AND p.live=1 AND p.search_public=1", "where := `p.kind='article' AND p.search_public=1",'TestNewsPageAPI'),
 ('列表排除受限',news,"where := `p.kind='article' AND p.live=1 AND p.search_public=1", "where := `p.kind='article' AND p.live=1",'TestNewsPageAPI'),
 ('分类有名字',news,"name<>'' AND slug<>''","slug<>''",'TestNewsPageAPI'),
 ('分类有网址',news,"name<>'' AND slug<>''","name<>''",'TestNewsPageAPI'),
 ('分类排序',news,'ORDER BY sort_order,name','ORDER BY sort_order DESC,name DESC','TestNewsPageAPI'),
 ('分类筛选',news,'where += ` AND c.slug=?`','where += ` AND ? IS NOT NULL`','TestNewsPageAPI'),
 ('列表最近发布排序',news,'utcTimeOrder("p.last_published_at")+` DESC','utcTimeOrder("p.last_published_at")+` ASC','TestNewsPageAPI'),
 ('页码回最后页',news,'page = lastPage','page = 1','TestNewsPageAPI'),
 ('栏目简介渲染',news,'IntroHTML: html','IntroHTML: func() string { _ = html; return intro }()','TestNewsPageAPI'),
 ('卡片作者编号',authors,'item.Author = authors[*a.AuthorID]','item.Author = nil','TestNewsPageAPI'),
 ('停用作者头像',authors,'if !a.IsActive {','if false {','TestNewsPageAPI'),
 ('成员统计验证邮箱',home,'is_active=1 AND email_verified_at IS NOT NULL','is_active=1','TestHomeProjection'),
 ('成员统计排除停用',home,'is_active=1 AND email_verified_at IS NOT NULL','email_verified_at IS NOT NULL','TestHomeProjection'),
 ('首页用请求时钟',home,'now := ctx.Now()','now := time.Now()','TestHomeFeatureChoice'),
 ('停用账号无安排',home,'v != nil && !v.Disabled && v.ID > 0','v != nil && v.ID > 0','TestHomeProjection'),
 ('安排只给本人',home,'s.store.d.ReadPool(), v.ID, now','s.store.d.ReadPool(), 1, now','TestHomeProjection'),
 ('推荐先取开放赛事',home,'if open != nil {','if false {','TestHomeFeatureChoice'),
 ('开放赛事先截止',home,'earlier(t.RegistrationClosesAt, open.RegistrationClosesAt)','earlier(open.RegistrationClosesAt, t.RegistrationClosesAt)','TestHomeFeatureChoice'),
 ('未结束赛事最先开始',home,'earlier(when(t), when(ahead))','earlier(when(ahead), when(t))','TestHomeFeatureChoice'),
 ('未来内战',home,"s.status='published' AND julianday(s.starts_at)>=julianday(?)","s.status='published' AND julianday(?)>0",'TestHomeProjection'),
 ('内战容量',home,'item.Capacity = sc.PlayersNeeded()','item.Capacity = 10','TestHomeProjection'),
 ('内战截止状态',home,'item.SignupOpen = sc.SignupOpen(now)','item.SignupOpen = true','TestHomeProjection'),
 ('内战上限5',home,'s.id LIMIT 5','s.id LIMIT 6','TestHomeLimits'),
 ('战队上限6',home,'t.id ASC LIMIT 6','t.id ASC LIMIT 7','TestHomeLimits'),
 ('战队排除解散',home,'WHERE t.disbanded_at IS NULL','WHERE 1=1','TestHomeLimits'),
 ('公告上限5',home,'p.id ASC LIMIT 5','p.id ASC LIMIT 6','TestHomeLimits'),
 ('公告分类',home,"c.slug IN ('notice','event-notice')","c.slug IN ('news')",'TestHomeProjection'),
 ('资讯上限4',home,'p.id ASC LIMIT 4','p.id ASC LIMIT 5','TestHomeLimits'),
 ('最多三篇置顶',home,'ORDER BY hp.sort_order LIMIT 3','ORDER BY hp.sort_order LIMIT 4','TestHomeLimits'),
 ('未来成立日期隐藏',home,'if founded.After(today) {','if false {','TestHomeAgeAndQueryFailures'),
 ('年龄上海日期',home,'today := date(now.In(loc))','today := date(now.UTC())','TestHomeAgeAndQueryFailures'),
 ('闰日周年',home,'day := min(founded.Day(), time.Date(year, founded.Month()+1, 0, 0, 0, 0, 0, time.UTC).Day())','day := founded.Day()','TestHomeAgeAndQueryFailures'),
 ('栏目修订不丢','internal/content/import.go',"model IN ('articlepage', 'standardpage', 'articleindexpage')","model IN ('articlepage', 'standardpage')",'TestImportNewsIndex'),
 ('最新草稿引用','internal/content/import.go','ORDER BY created_at DESC,id DESC LIMIT 1','ORDER BY created_at ASC,id ASC LIMIT 1','TestImportNewsIndex'),
 ('草稿不覆盖栏目发布值','internal/content/import_news.go','VALUES (?,?) ON CONFLICT(page_id) DO NOTHING',"VALUES (?, 'draft') ON CONFLICT(page_id) DO NOTHING",'TestImportNewsIndex'),
]
cases += [
 ("equal deadlines use registration order","internal/tournaments/home.go","THEN starts_at ELSE registration_opens_at END DESC","THEN starts_at ELSE starts_at END DESC","TestHomeFeatureTiePreference"),
 ("equal registration times use descending ID","internal/tournaments/home.go","status='published' THEN id END DESC","status='published' THEN id END ASC","TestHomeFeatureTiePreference"),
]
for name,rel,old,new,test in cases:
 p=server/rel;baseline=p.read_text()
 if old not in baseline:raise SystemExit(f'missing anchor: {name}')
 changed=baseline.replace(old,new,1)
 if name=='草稿不覆盖栏目发布值':changed=changed.replace('id, intro);','id);',1)
 try:
  p.write_text(changed)
  built=subprocess.run(['go','test','./internal/content','-run','^$'],cwd=server,capture_output=True,text=True)
  if built.returncode:raise SystemExit(f'INVALID {name}: {built.stdout}{built.stderr}')
  result=subprocess.run(['go','test','./internal/content','-run',test,'-count=1'],cwd=server,capture_output=True,text=True)
  if not result.returncode:raise SystemExit(f'SURVIVED {name}')
  print(f'CAUGHT {name}',flush=True)
 finally:p.write_text(baseline)
print(f'MUTATIONS-OK {len(cases)}',flush=True)
