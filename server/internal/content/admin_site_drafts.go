package content

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"net/http"
	"reflect"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

type HomeDraft struct {
	ArticleIDs []int64 `json:"article_ids"`
}
type NewsDraft struct {
	IntroMD string `json:"intro_md"`
}
type HomeDraftOut struct {
	Live                  bool       `json:"live"`
	LastPublishedAt       *time.Time `json:"last_published_at"`
	ID                    int64      `json:"id"`
	Version               int64      `json:"version"`
	Draft                 HomeDraft  `json:"draft"`
	HasUnpublishedChanges bool       `json:"has_unpublished_changes"`
	PreviewURL            *string    `json:"preview_url"`
	CanPublish            bool       `json:"can_publish"`
}
type NewsDraftOut struct {
	IntroMD               string     `json:"intro_md"`
	Live                  bool       `json:"live"`
	LastPublishedAt       *time.Time `json:"last_published_at"`
	ID                    int64      `json:"id"`
	Version               int64      `json:"version"`
	Draft                 NewsDraft  `json:"draft"`
	HasUnpublishedChanges bool       `json:"has_unpublished_changes"`
	PreviewURL            *string    `json:"preview_url"`
	CanPublish            bool       `json:"can_publish"`
}
type PinnedArticleItem struct {
	ID    int64  `json:"id"`
	Title string `json:"title"`
	Live  bool   `json:"live"`
}

type SitePartsOut struct {
	Pinned []PinnedArticleItem `json:"pinned"`
	Items  []PlainPageItem     `json:"items"`
	Home   HomeDraftOut        `json:"home"`
	News   NewsDraftOut        `json:"news"`
}
type SiteDraftPatchIn struct {
	BaseVersion int64          `json:"base_version"`
	Changes     map[string]any `json:"changes"`
}
type HomeDraftPatchOut struct {
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	Values  HomeDraft           `json:"values"`
	SavedAt time.Time           `json:"saved_at"`
}
type NewsDraftPatchOut struct {
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	Values  NewsDraft           `json:"values"`
	SavedAt time.Time           `json:"saved_at"`
}
type SiteDraftPublishIn struct {
	BaseVersion int64 `json:"base_version"`
}
type SiteDraftPublishOut struct {
	Version int64 `json:"version"`
}

func readScope(ctx context.Context, q db.DBTX, scope string) (int64, string, string, error) {
	var version int64
	var content, live string
	err := q.QueryRowContext(ctx, "SELECT version,content,live_content FROM content_editor_drafts WHERE scope=?", scope).Scan(&version, &content, &live)
	if errors.Is(err, sql.ErrNoRows) {
		if scope == "home_pins" {
			ids := []int64{}
			rows, err := q.QueryContext(ctx, "SELECT article_page_id FROM home_pins ORDER BY sort_order,article_page_id")
			if err != nil {
				return 0, "", "", err
			}
			for rows.Next() {
				var id int64
				if err := rows.Scan(&id); err != nil {
					rows.Close()
					return 0, "", "", err
				}
				ids = append(ids, id)
			}
			err = rows.Err()
			rows.Close()
			if err != nil {
				return 0, "", "", err
			}
			raw, err := json.Marshal(HomeDraft{ArticleIDs: ids})
			return 0, string(raw), string(raw), err
		}
		var intro string
		err = q.QueryRowContext(ctx, "SELECT n.intro FROM news_index n JOIN pages p ON p.id=n.page_id WHERE p.slug='news' AND p.kind='news_index' LIMIT 1").Scan(&intro)
		if errors.Is(err, sql.ErrNoRows) {
			return 0, "", "", api.NotFound("资讯栏目不存在")
		}
		if err != nil {
			return 0, "", "", err
		}
		liveBytes, err := json.Marshal(NewsDraft{IntroMD: intro})
		if err != nil {
			return 0, "", "", err
		}
		draft := NewsDraft{IntroMD: intro}
		var revision sql.NullString
		err = q.QueryRowContext(ctx, `SELECT r.content FROM pages p LEFT JOIN page_revisions r ON r.id=p.latest_revision_id
            WHERE p.kind='news_index' AND p.slug='news' AND p.has_unpublished_changes=1 LIMIT 1`).Scan(&revision)
		if err != nil && !errors.Is(err, sql.ErrNoRows) {
			return 0, "", "", err
		}
		if revision.Valid {
			draft, err = readNewsRevisionContent(revision.String, draft)
			if err != nil {
				return 0, "", "", err
			}
		}
		raw, err := json.Marshal(draft)
		return 0, string(raw), string(liveBytes), err
	}
	return version, content, live, err
}

func writeScope(ctx context.Context, tx *db.Tx, scope string, version int64, content, live string, actor int64, now time.Time) error {
	if version == 0 {
		_, err := tx.ExecContext(ctx, "INSERT INTO content_editor_drafts(scope,version,content,live_content,updated_at,author_id) VALUES(?,1,?,?,?,?)", scope, content, live, now.UTC().Format(time.RFC3339Nano), actor)
		return err
	}
	result, err := tx.ExecContext(ctx, "UPDATE content_editor_drafts SET version=version+1,content=?,live_content=?,updated_at=?,author_id=? WHERE scope=? AND version=?", content, live, now.UTC().Format(time.RFC3339Nano), actor, scope, version)
	if err != nil {
		return err
	}
	changed, err := result.RowsAffected()
	if err != nil {
		return err
	}
	if changed != 1 {
		return api.NewErr(409, "stale", "内容刚被修改，请重新加载")
	}
	return nil
}

func (m *Module) readHomeDraft(ctx *app.Ctx, _ struct{}) (HomeDraftOut, error) {
	out := HomeDraftOut{ID: 0, CanPublish: true, Draft: HomeDraft{ArticleIDs: []int64{}}}
	version, content, live, err := readScope(ctx.Context, m.svc.store.d.ReadPool(), "home_pins")
	if err != nil {
		return out, err
	}
	if err := json.Unmarshal([]byte(content), &out.Draft); err != nil {
		return out, err
	}
	out.Version = version
	out.HasUnpublishedChanges = !equivalentScopeDraft(content, live)
	if err := readHomeDraftState(ctx.Context, m.svc.store.d.ReadPool(), &out); err != nil {
		return out, err
	}
	url := "/api/admin/home-pins/preview"
	out.PreviewURL = &url
	return out, nil
}

func (m *Module) readNewsDraft(ctx *app.Ctx, _ struct{}) (NewsDraftOut, error) {
	out := NewsDraftOut{CanPublish: true}
	version, content, live, err := readScope(ctx.Context, m.svc.store.d.ReadPool(), "news_intro")
	if err != nil {
		return out, err
	}
	if err := json.Unmarshal([]byte(content), &out.Draft); err != nil {
		return out, err
	}
	var publishedDraft NewsDraft
	if err := json.Unmarshal([]byte(live), &publishedDraft); err != nil {
		return out, err
	}
	out.IntroMD = publishedDraft.IntroMD
	out.Version = version
	out.HasUnpublishedChanges = !equivalentScopeDraft(content, live)
	if err := m.svc.store.d.ReadPool().QueryRowContext(ctx.Context, "SELECT id FROM pages WHERE kind='news_index' AND slug='news' LIMIT 1").Scan(&out.ID); err != nil {
		return out, err
	}
	if err := readSiteDraftState(ctx.Context, m.svc.store.d.ReadPool(), "news_index", &out.Live, &out.LastPublishedAt); err != nil {
		return out, err
	}
	url := "/api/admin/news-intro/preview"
	out.PreviewURL = &url
	return out, nil
}

func pinChanges(value any) ([]int64, error) {
	array, ok := value.([]any)
	if !ok || len(array) > 3 {
		return nil, api.InvalidFields(map[string][]string{"article_ids": {"最多选择3篇文章"}})
	}
	ids := []int64{}
	seen := map[int64]bool{}
	for _, raw := range array {
		id, ok := toInt64(raw)
		if !ok || id <= 0 || seen[id] {
			return nil, api.InvalidFields(map[string][]string{"article_ids": {"文章编号无效或重复"}})
		}
		seen[id] = true
		ids = append(ids, id)
	}
	return ids, nil
}

func (m *Module) patchHomeDraft(ctx *app.Ctx, in SiteDraftPatchIn) (HomeDraftPatchOut, error) {
	out := HomeDraftPatchOut{Saved: []string{}, Fields: map[string][]string{}, SavedAt: ctx.Now().UTC()}
	err := m.svc.store.d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		version, content, live, err := readScope(c, tx, "home_pins")
		if err != nil {
			return err
		}
		if err := json.Unmarshal([]byte(content), &out.Values); err != nil {
			return err
		}
		out.Version = version
		if version != in.BaseVersion {
			return api.Stale(map[string]any{"version": version, "values": out.Values})
		}
		for key, value := range in.Changes {
			if key != "article_ids" {
				out.Fields[key] = []string{"这个字段不能修改"}
				continue
			}
			ids, err := pinChanges(value)
			if err != nil {
				out.Fields[key] = []string{"最多3篇，不能重复选择"}
				continue
			}
			valid := true
			for _, id := range ids {
				var exists int
				if err := tx.QueryRowContext(c, "SELECT COUNT(*) FROM pages WHERE id=? AND kind='article' AND live=1", id).Scan(&exists); err != nil {
					return err
				}
				if exists == 0 {
					// Removing/reordering an existing unpublished pin must stay possible.
					present := false
					for _, old := range out.Values.ArticleIDs {
						if old == id {
							present = true
						}
					}
					if !present {
						valid = false
						break
					}
				}
			}
			if !valid {
				out.Fields[key] = []string{"只能新选已发布的文章"}
				continue
			}
			out.Values.ArticleIDs = ids
			out.Saved = append(out.Saved, key)
		}
		if len(out.Saved) == 0 {
			return nil
		}
		raw, err := json.Marshal(out.Values)
		if err != nil {
			return err
		}
		if err := writeScope(c, tx, "home_pins", version, string(raw), live, ctx.Viewer.ID, ctx.Now()); err != nil {
			return err
		}
		out.Version++
		if _, err := tx.ExecContext(c, "UPDATE content_home_state SET has_unpublished_changes=1"); err != nil {
			return err
		}
		return contentAudit(c, tx, ctx.Viewer.ID, "home.save_draft", "home", 0, nil, ctx.Now())
	})
	return out, err
}

func (m *Module) patchNewsDraft(ctx *app.Ctx, in SiteDraftPatchIn) (NewsDraftPatchOut, error) {
	out := NewsDraftPatchOut{Saved: []string{}, Fields: map[string][]string{}, SavedAt: ctx.Now().UTC()}
	err := m.svc.store.d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		version, content, live, err := readScope(c, tx, "news_intro")
		if err != nil {
			return err
		}
		if err := json.Unmarshal([]byte(content), &out.Values); err != nil {
			return err
		}
		out.Version = version
		if version != in.BaseVersion {
			return api.Stale(map[string]any{"version": version, "values": out.Values})
		}
		for key, value := range in.Changes {
			text, ok := value.(string)
			if key != "intro_md" {
				out.Fields[key] = []string{"这个字段不能修改"}
				continue
			}
			if !ok || len(text) > 1024*1024 {
				out.Fields[key] = []string{"介绍格式无效或超过1 MB"}
				continue
			}
			out.Values.IntroMD = text
			out.Saved = append(out.Saved, key)
		}
		if len(out.Saved) == 0 {
			return nil
		}
		raw, err := json.Marshal(out.Values)
		if err != nil {
			return err
		}
		if err := writeScope(c, tx, "news_intro", version, string(raw), live, ctx.Viewer.ID, ctx.Now()); err != nil {
			return err
		}
		out.Version++
		return contentAudit(c, tx, ctx.Viewer.ID, "news.save_draft", "news", 0, nil, ctx.Now())
	})
	return out, err
}

func (m *Module) publishHomeDraft(ctx *app.Ctx, in SiteDraftPublishIn) (SiteDraftPublishOut, error) {
	out := SiteDraftPublishOut{}
	err := m.svc.store.d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		version, content, _, err := readScope(c, tx, "home_pins")
		if err != nil {
			return err
		}
		var draft HomeDraft
		if err := json.Unmarshal([]byte(content), &draft); err != nil {
			return err
		}
		if version != in.BaseVersion {
			return api.Stale(map[string]any{"version": version, "values": draft})
		}
		if len(draft.ArticleIDs) > 3 {
			return api.InvalidFields(map[string][]string{"article_ids": {"最多3篇文章"}})
		}
		if _, err := tx.ExecContext(c, "DELETE FROM home_pins"); err != nil {
			return err
		}
		for index, id := range draft.ArticleIDs {
			var exists int
			if err := tx.QueryRowContext(c, "SELECT COUNT(*) FROM pages WHERE id=? AND kind='article'", id).Scan(&exists); err != nil {
				return err
			}
			if exists != 1 {
				return api.InvalidFields(map[string][]string{"article_ids": {"有文章已经删除，请移除后再发布"}})
			}
			if _, err := tx.ExecContext(c, "INSERT INTO home_pins(article_page_id,sort_order) VALUES(?,?)", id, index); err != nil {
				return err
			}
		}
		if err := writeScope(c, tx, "home_pins", version, content, content, ctx.Viewer.ID, ctx.Now()); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "UPDATE content_home_state SET live=1,has_unpublished_changes=0,last_published_at=?", db.FormatUTC(ctx.Now())); err != nil {
			return err
		}
		out.Version = version + 1
		return contentAudit(c, tx, ctx.Viewer.ID, "home.publish", "home", 0, nil, ctx.Now())
	})
	return out, err
}

func (m *Module) publishNewsDraft(ctx *app.Ctx, in SiteDraftPublishIn) (SiteDraftPublishOut, error) {
	out := SiteDraftPublishOut{}
	err := m.svc.store.d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		version, content, _, err := readScope(c, tx, "news_intro")
		if err != nil {
			return err
		}
		var draft NewsDraft
		if err := json.Unmarshal([]byte(content), &draft); err != nil {
			return err
		}
		if version != in.BaseVersion {
			return api.Stale(map[string]any{"version": version, "values": draft})
		}
		if _, _, err := markdown.Render(draft.IntroMD, m.svc.siteURL, nil); err != nil {
			return err
		}
		var pageID int64
		if err := tx.QueryRowContext(c, "SELECT id FROM pages WHERE kind='news_index' AND slug='news' LIMIT 1").Scan(&pageID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "UPDATE news_index SET intro=? WHERE page_id=?", draft.IntroMD, pageID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "UPDATE pages SET live=1,version=version+1,has_unpublished_changes=0,first_published_at=COALESCE(first_published_at,?),last_published_at=?,updated_at=? WHERE id=?", ctx.Now().UTC().Format(time.RFC3339Nano), ctx.Now().UTC().Format(time.RFC3339Nano), ctx.Now().UTC().Format(time.RFC3339Nano), pageID); err != nil {
			return err
		}
		if err := writeScope(c, tx, "news_intro", version, content, content, ctx.Viewer.ID, ctx.Now()); err != nil {
			return err
		}
		out.Version = version + 1
		return contentAudit(c, tx, ctx.Viewer.ID, "news.publish", "page", pageID, nil, ctx.Now())
	})
	return out, err
}

func (m *Module) listSiteParts(ctx *app.Ctx, _ struct{}) (SitePartsOut, error) {
	out := SitePartsOut{Items: []PlainPageItem{}, Pinned: []PinnedArticleItem{}}
	rows, err := m.svc.store.d.ReadPool().QueryContext(ctx.Context, `SELECT p.id,p.slug,p.title,p.live,p.has_unpublished_changes,p.updated_at,p.version,r.content,p.last_published_at,r.created_at,p.expired,EXISTS(SELECT 1 FROM page_revisions schedule WHERE schedule.page_id=p.id AND schedule.approved_go_live_at IS NOT NULL) FROM pages p
        LEFT JOIN page_revisions r ON r.id=p.latest_revision_id WHERE p.kind='site_page' ORDER BY CASE p.slug WHEN 'about' THEN 0 WHEN 'terms' THEN 1 WHEN 'privacy' THEN 2 ELSE 99 END,p.id`)
	if err != nil {
		return out, err
	}
	for rows.Next() {
		var item PlainPageItem
		var live, unpublished, expired, scheduled int
		var updated string
		var revision, published, revised sql.NullString
		if err := rows.Scan(&item.ID, &item.Slug, &item.Title, &live, &unpublished, &updated, &item.Version, &revision, &published, &revised, &expired, &scheduled); err != nil {
			rows.Close()
			return out, err
		}
		if revision.Valid {
			draft, err := readPlainRevisionContent(revision.String, PlainPageDraft{Title: item.Title})
			if err != nil {
				rows.Close()
				return out, fmt.Errorf("页面草稿内容损坏: %w", err)
			}
			item.DraftTitle = &draft.Title
		}
		if published.Valid {
			value, err := db.ParseUTC(published.String)
			if err != nil {
				rows.Close()
				return out, err
			}
			item.LastPublishedAt = &value
		}
		if revised.Valid {
			value, err := db.ParseUTC(revised.String)
			if err != nil {
				rows.Close()
				return out, err
			}
			item.LatestRevisionCreatedAt = &value
		}
		item.Expired = expired == 1
		item.ApprovedSchedule = scheduled == 1
		item.Live = live == 1
		item.HasUnpublishedChanges = unpublished == 1
		item.UpdatedAt, _ = db.ParseUTC(updated)
		out.Items = append(out.Items, item)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return out, err
	}
	out.Home, err = m.readHomeDraft(ctx, struct{}{})
	if err != nil {
		return out, err
	}
	out.News, err = m.readNewsDraft(ctx, struct{}{})
	if err != nil {
		return out, err
	}
	pins, err := m.svc.store.GetHomePins(ctx.Context)
	if err != nil {
		return out, err
	}
	for _, pin := range pins {
		id := pin.ArticlePageID
		var item PinnedArticleItem
		var live int
		err := m.svc.store.d.ReadPool().QueryRowContext(ctx.Context, "SELECT id,title,live FROM pages WHERE id=? AND kind='article'", id).Scan(&item.ID, &item.Title, &live)
		if errors.Is(err, sql.ErrNoRows) {
			continue
		}
		if err != nil {
			return out, err
		}
		item.Live = live == 1
		out.Pinned = append(out.Pinned, item)
	}
	return out, nil
}

func (m *Module) serveHomePreview(w http.ResponseWriter, r *http.Request) {
	privatePreviewHeaders(w)
	viewer := m.previewViewer(w, r)
	if viewer == nil {
		return
	}
	if !viewer.HasCap(CapSitePagesManage) {
		http.Error(w, "没有权限", http.StatusForbidden)
		return
	}
	ctx := &app.Ctx{Context: r.Context(), Viewer: viewer}
	draft, err := m.readHomeDraft(ctx, struct{}{})
	if err != nil {
		http.Error(w, "预览暂时不可用", http.StatusInternalServerError)
		return
	}
	var body strings.Builder
	body.WriteString("<ol>")
	for _, id := range draft.Draft.ArticleIDs {
		article, err := m.svc.store.GetArticleByID(r.Context(), id)
		if err != nil {
			http.Error(w, "预览暂时不可用", http.StatusInternalServerError)
			return
		}
		if article == nil || !article.Live || !article.Public {
			continue
		}
		body.WriteString("<li><h2>" + html.EscapeString(article.Title) + "</h2><p>" + html.EscapeString(article.Summary) + "</p></li>")
	}
	body.WriteString("</ol>")
	_, _ = fmt.Fprint(w, m.previewDocument("首页置顶", body.String()))
}

func (m *Module) serveNewsPreview(w http.ResponseWriter, r *http.Request) {
	privatePreviewHeaders(w)
	viewer := m.previewViewer(w, r)
	if viewer == nil {
		return
	}
	if !viewer.HasCap(CapSitePagesManage) {
		http.Error(w, "没有权限", http.StatusForbidden)
		return
	}
	ctx := &app.Ctx{Context: r.Context(), Viewer: viewer}
	draft, err := m.readNewsDraft(ctx, struct{}{})
	if err != nil {
		http.Error(w, "预览暂时不可用", http.StatusInternalServerError)
		return
	}
	body, _, err := markdown.Render(draft.Draft.IntroMD, m.svc.siteURL, nil)
	if err != nil {
		http.Error(w, "预览暂时不可用", http.StatusInternalServerError)
		return
	}
	_, _ = fmt.Fprint(w, m.previewDocument("资讯栏目的介绍", body))
}

// Keep scope draft encodings canonical: equal field values should not mark changes.
func equivalentScopeDraft(left, right string) bool {
	var a, b any
	if json.Unmarshal([]byte(left), &a) != nil || json.Unmarshal([]byte(right), &b) != nil {
		return false
	}
	return reflect.DeepEqual(a, b)
}

func readSiteDraftState(ctx context.Context, q db.DBTX, kind string, live *bool, published **time.Time) error {
	var active int
	var stamp sql.NullString
	err := q.QueryRowContext(ctx, "SELECT live,last_published_at FROM pages WHERE kind=? ORDER BY id LIMIT 1", kind).Scan(&active, &stamp)
	if errors.Is(err, sql.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	*live = active == 1
	if stamp.Valid {
		value, err := db.ParseUTC(stamp.String)
		if err != nil {
			return err
		}
		*published = &value
	}
	return nil
}

func readHomeDraftState(ctx context.Context, q db.DBTX, out *HomeDraftOut) error {
	var live, unpublished int
	var published sql.NullString
	err := q.QueryRowContext(ctx, "SELECT id,live,has_unpublished_changes,last_published_at FROM content_home_state ORDER BY id LIMIT 1").Scan(&out.ID, &live, &unpublished, &published)
	if errors.Is(err, sql.ErrNoRows) {
		out.Live = true
		return nil
	}
	if err != nil {
		return err
	}
	out.Live = live == 1
	out.HasUnpublishedChanges = out.HasUnpublishedChanges || unpublished == 1
	if published.Valid {
		value, err := db.ParseUTC(published.String)
		if err != nil {
			return err
		}
		out.LastPublishedAt = &value
	}
	return nil
}
