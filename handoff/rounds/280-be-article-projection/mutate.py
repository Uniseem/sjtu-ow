"""测试机后台运行；每项先编译，再确认本轮回归失败，最后恢复源码。"""
from pathlib import Path
import subprocess

server = Path(__file__).resolve().parents[3] / 'server'
article = 'internal/content/article_page.go'
imports = 'internal/content/import.go'
pools = 'internal/platform/media/pools.go'
cases = [
 ('作者公开篇数排除草稿',article,'WHERE p.live=1 AND p.search_public=1 AND a.author_id=?','WHERE p.search_public=1 AND a.author_id=?','content','TestArticleProjectionAPI'),
 ('作者公开篇数排除受限',article,'WHERE p.live=1 AND p.search_public=1 AND a.author_id=?','WHERE p.live=1 AND a.author_id=?','content','TestArticleProjectionAPI'),
 ('停用作者不出头像',article,'if !out.IsActive {','if false {','content','TestArticleProjectionAuthorAvatars'),
 ('补位置按固定顺序选头像',article,'main = roles[0]','main = roles[len(roles)-1]','content','TestArticleProjectionAuthorAvatars'),
 ('相邻只取同栏目',article,'p.parent_id IS (SELECT parent_id FROM pages WHERE id=?)','? IS NOT NULL','content','TestArticleProjectionAPI'),
 ('相邻排除草稿',article,"WHERE p.kind='article' AND p.live=1 AND p.search_public=1","WHERE p.kind='article' AND p.search_public=1",'content','TestArticleProjectionAPI'),
 ('相邻排除受限',article,"WHERE p.kind='article' AND p.live=1 AND p.search_public=1","WHERE p.kind='article' AND p.live=1",'content','TestArticleProjectionAPI'),
 ('同时间不是前篇',article,'comparison, order := "<", "DESC"','comparison, order := "<=", "DESC"','content','TestArticleProjectionAPI'),
 ('前篇取最近',article,'comparison, order := "<", "DESC"','comparison, order := "<", "ASC"','content','TestArticleProjectionAPI'),
 ('后篇取最近',article,'comparison, order = ">", "ASC"','comparison, order = ">", "DESC"','content','TestArticleProjectionAPI'),
 ('无首发不查上下篇',article,'if article.FirstPublishedAt != nil {','if true {','content','TestArticleProjectionEdges'),
 ('相关文章同分类',article,'a.category_id IS ?','(? IS NOT NULL OR a.category_id IS NULL)','content','TestArticleProjectionAPI'),
 ('相关文章排除自己',article,'p.id<>?','? IS NOT NULL','content','TestArticleProjectionEdges'),
 ('相关文章排除草稿',article,'WHERE p.live=1 AND p.search_public=1 AND a.category_id','WHERE p.search_public=1 AND a.category_id','content','TestArticleProjectionAPI'),
 ('相关文章排除受限',article,'WHERE p.live=1 AND p.search_public=1 AND a.category_id','WHERE p.live=1 AND a.category_id','content','TestArticleProjectionAPI'),
 ('相关文章最多三篇',article,'p.id ASC LIMIT 3','p.id ASC LIMIT 4','content','TestArticleProjectionAPI'),
 ('相关文章最近发布第二排序',article,'utcTimeOrder("p.last_published_at")+` DESC','utcTimeOrder("p.last_published_at")+` ASC','content','TestArticleProjectionEdges'),
 ('赛事草稿不出卡片',article,'if t != nil && t.IsPublic() {','if t != nil {','content','TestArticleProjectionEdges'),
 ('赛事阶段使用请求时钟',article,'t.Phase(ctx.Now())','t.Phase(time.Now())','content','TestArticleProjectionEdges'),
 ('赛事默认封面偏移13',article,'media.PickCover(pool, t.ID, 13)','media.PickCover(pool, t.ID, 0)','content','TestArticleProjectionAPI'),
 ('个人报名卡片标签',article,'if t.TakesIndividuals() {','if false {','content','TestArticleProjectionEdges'),
 ('游客隐藏评论不计数','internal/comments/store.go','c.is_hidden=0 AND c.is_deleted=0','c.is_deleted=0','content','TestArticleProjectionAPI'),
 ('管理员空已删楼不计数','internal/comments/store.go','c.is_deleted=0 OR EXISTS','1=1 OR EXISTS','content','TestArticleProjectionAPI'),
 ('管理员不返回已删回复','internal/comments/store.go','where += " AND c.is_deleted = 0"','where += " AND 1=1"','content','TestArticleProjectionAPI'),
 ('图库包含子目录',pools,'ON c.parent_id=p.id','ON c.parent_id=p.id AND 0=1','content','TestArticleProjection'),
 ('图库按图片编号排序',pools,'ORDER BY i.id','ORDER BY i.id DESC','content','TestArticleProjection'),
 ('头像位置只看第一层目录',pools,'p.at_root=1',"p.role=''",'content','TestArticleProjectionAuthorAvatars'),
 ('导入保留文章父栏目',imports,'nowStr, nowStr, searchPublic, parentID','nowStr, nowStr, searchPublic, sql.NullInt64{}','content','TestImportContentParentLinks'),
 ('导入保留图库父目录',imports,'id, name, key, nowStr, parent','id, name, key, nowStr, sql.NullInt64{}','content','TestImportContentParentLinks'),
 ('同名子图库不抢根key',imports,'if claimedKeys[key] {','if false {','content','TestImportContentParentLinks'),
 ('新文章放进资讯栏目','internal/content/store.go',"kind='news_index' AND slug='news'","kind='news_index' AND slug='never'",'content','TestNewArticleUsesNewsParent'),
]
cases += [
 ('未知父栏目不猜上下篇',article,'AND p.parent_id IS NOT NULL','AND 1=1','content','TestArticleProjectionEdges'),
 ('时间保留微秒',article,'substr(" + column + ",21)','substr(" + column + ",21,3)','content','TestArticleProjectionEdges'),
 ('投影查询错误不吞掉',article,'out.CommentTotal, err = comments.NewStore','out.CommentTotal, _ = comments.NewStore','content','TestArticleProjectionEdges'),
 ('迁移不伪造文章父栏目','db/migrations/00020_content_parent_links.sql','ALTER TABLE pages ADD COLUMN parent_id INTEGER;','ALTER TABLE pages ADD COLUMN parent_id INTEGER DEFAULT 0;','platform/db','TestContentParentLinksUpgrade'),
 ('迁移不伪造图库父目录','db/migrations/00020_content_parent_links.sql','ALTER TABLE image_collections ADD COLUMN parent_id INTEGER REFERENCES','ALTER TABLE image_collections ADD COLUMN parent_id INTEGER DEFAULT 1 REFERENCES','platform/db','TestContentParentLinksUpgrade'),
]
for name,rel,old,new,module,test in cases:
 path=server/rel
 baseline=path.read_text()
 if old not in baseline:raise SystemExit(f'missing anchor: {name}')
 try:
  path.write_text(baseline.replace(old,new,1))
  built=subprocess.run(['go','test',f'./internal/{module}','-run','^$'],cwd=server,capture_output=True,text=True)
  if built.returncode:raise SystemExit(f'INVALID {name}: {built.stdout}{built.stderr}')
  result=subprocess.run(['go','test',f'./internal/{module}','-run',test,'-count=1'],cwd=server,capture_output=True,text=True)
  if result.returncode==0:raise SystemExit(f'SURVIVED {name}')
  print(f'CAUGHT {name}',flush=True)
 finally:path.write_text(baseline)
print(f'MUTATIONS-OK {len(cases)}',flush=True)
