"""可编译的错误行为必须被公开矩阵/事务不变性/导入回归抓住。"""
from pathlib import Path
import subprocess
server=Path(__file__).resolve().parents[3]/'server'
cases=[
 ('公开详情不出草稿','internal/content/article_page.go','!article.Live || !article.Public','false || !article.Public','content','TestPublicContentHTTPMatrix'),
 ('公开详情不出私密','internal/content/article_page.go','!article.Live || !article.Public','!article.Live || false','content','TestPublicContentHTTPMatrix'),
 ('普通页访问限制','internal/content/api.go','!sp.Live || !sp.Public','!sp.Live || false','content','TestPublicContentHTTPMatrix'),
 ('普通页发布门','internal/content/api.go','!sp.Live || !sp.Public','false || !sp.Public','content','TestPublicContentHTTPMatrix'),
 ('列表过滤私密','internal/content/news_page.go',"where := `p.kind='article' AND p.live=1 AND p.is_public=1", "where := `p.kind='article' AND p.live=1",'content','TestPublicContentHTTPMatrix'),
 ('首页资讯私密门','internal/content/home_store.go','WHERE p.live=1 AND p.is_public=1 ORDER','WHERE p.live=1 ORDER','content','TestPublicContentHTTPMatrix'),
 ('公告私密门','internal/content/home_store.go',"p.live=1 AND p.is_public=1 AND c.slug IN", "p.live=1 AND c.slug IN",'content','TestPublicContentHTTPMatrix'),
 ('站点地图私密门','internal/content/sitemap.go','AND is_public = 1 ORDER BY id','ORDER BY id','content','TestPublicContentHTTPMatrix'),
 ('公开置顶门','internal/content/home_pins.go','a.Live && a.Public','a.Live','content','TestPublicContentHTTPMatrix'),
 ('后台置顶能力门','internal/content/home_pins.go','if !publicOnly &&','if false &&','content','TestPublicPinsKeepAdminSelection'),
 ('搜索仍过滤私密','internal/search/service.go','AND p.is_public=1 AND p.search_public=1','AND p.search_public=1','content','TestPublicContentHTTPMatrix'),
 ('评论公开读门','internal/comments/service.go','p.live=1 AND p.is_public=1','p.live=1','comments','TestPublicCommentHTTPMatrix'),
 ('评论发布读门','internal/comments/service.go','p.live=1 AND p.is_public=1','p.is_public=1','comments','TestPublicCommentHTTPMatrix'),
 ('事务公开门','internal/comments/store.go','p.live=1 AND p.is_public=1','p.live=1','comments','TestCommentStorePublicChecksInsideTransaction'),
 ('事务发布门','internal/comments/store.go','p.live=1 AND p.is_public=1','p.is_public=1','comments','TestCommentStorePublicChecksInsideTransaction'),
 ('回复父评论不可隐藏','internal/comments/store.go','AND is_hidden=0 AND is_deleted=0','AND is_deleted=0','comments','TestReplyParentCheckedInsideTransaction'),
 ('回复父评论不可已删','internal/comments/store.go','AND is_hidden=0 AND is_deleted=0','AND is_hidden=0','comments','TestReplyParentCheckedInsideTransaction'),
 ('回复同篇','internal/comments/store.go','id=? AND article_id=? AND is_hidden','id=? AND ? IS NOT NULL AND is_hidden','comments','TestReplyParentCheckedInsideTransaction'),
 ('取消置顶只改目标','internal/comments/store.go','WHERE id=? AND article_id=?`, now, commentID, articleID','WHERE ? IS NOT NULL AND article_id=?`, now, commentID, articleID','comments','TestClosedCommentsAndUnpinIsolation'),
 ('旧库限制保留','db/migrations/00021_page_public.sql','UPDATE pages SET is_public=search_public','UPDATE pages SET is_public=1','platform/db','TestPagePublicMigration'),
]
for name,rel,old,new,module,test in cases:
 p=server/rel;baseline=p.read_text()
 if old not in baseline:raise SystemExit(f'missing anchor: {name}')
 try:
  p.write_text(baseline.replace(old,new,1))
  built=subprocess.run(['go','test',f'./internal/{module}','-run','^$'],cwd=server,capture_output=True,text=True)
  if built.returncode:raise SystemExit(f'INVALID {name}: {built.stdout}{built.stderr}')
  result=subprocess.run(['go','test',f'./internal/{module}','-run',test,'-count=1'],cwd=server,capture_output=True,text=True)
  if result.returncode==0:raise SystemExit(f'SURVIVED {name}')
  print(f'CAUGHT {name}',flush=True)
 finally:p.write_text(baseline)
print(f'MUTATIONS-OK {len(cases)}',flush=True)
