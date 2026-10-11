package content

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

type PlainPageDraft struct {
	Title             string `json:"title"`
	BodyMD            string `json:"body_md"`
	SeoTitle          string `json:"seo_title"`
	SearchDescription string `json:"search_description"`
}

type PlainPageItem struct {
	ID                    int64     `json:"id"`
	Slug                  string    `json:"slug"`
	Title                 string    `json:"title"`
	Live                  bool      `json:"live"`
	HasUnpublishedChanges bool      `json:"has_unpublished_changes"`
	UpdatedAt             time.Time `json:"updated_at"`
	Version               int64     `json:"version"`
}

type PlainPageDetail struct {
	Page       PlainPageItem  `json:"page"`
	Draft      PlainPageDraft `json:"draft"`
	Version    int64          `json:"version"`
	PreviewURL *string        `json:"preview_url"`
	CanPublish bool           `json:"can_publish"`
}

type PlainPageIn struct {
	ID api.ID `path:"id"`
}
type PlainPagePatchIn struct {
	ID          api.ID         `path:"id"`
	BaseVersion int64          `json:"base_version"`
	Changes     map[string]any `json:"changes"`
}

type PlainPagePatchOut struct {
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	Values  PlainPageDraft      `json:"values"`
	SavedAt time.Time           `json:"saved_at"`
}

type PlainPagePublishIn struct {
	ID          api.ID `path:"id"`
	BaseVersion int64  `json:"base_version"`
}
type PlainPagePublishOut struct {
	Page    PlainPageItem `json:"page"`
	Version int64         `json:"version"`
}

func readPlainPageRow(ctx context.Context, q db.DBTX, id int64) (PlainPageDetail, error) {
	out := PlainPageDetail{CanPublish: true}
	var live, unpublished int
	var updated string
	var revision sql.NullString
	err := q.QueryRowContext(ctx, `SELECT p.id,p.slug,p.title,p.live,p.has_unpublished_changes,p.updated_at,p.version,
        sp.body_md,p.seo_title,p.search_description,r.content FROM pages p JOIN site_pages sp ON sp.page_id=p.id
        LEFT JOIN page_revisions r ON r.id=p.latest_revision_id WHERE p.kind='site_page' AND p.id=?`, id).Scan(
		&out.Page.ID, &out.Page.Slug, &out.Page.Title, &live, &unpublished, &updated, &out.Page.Version,
		&out.Draft.BodyMD, &out.Draft.SeoTitle, &out.Draft.SearchDescription, &revision,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return out, api.NotFound("页面不存在")
	}
	if err != nil {
		return out, err
	}
	out.Page.Live = live == 1
	out.Page.HasUnpublishedChanges = unpublished == 1
	out.Page.UpdatedAt, _ = db.ParseUTC(updated)
	out.Draft.Title = out.Page.Title
	out.Version = out.Page.Version
	if revision.Valid {
		// Additive decoding preserves live values for imported historical fields.
		out.Draft, err = readPlainRevisionContent(revision.String, out.Draft)
		if err != nil {
			return out, fmt.Errorf("页面草稿内容损坏: %w", err)
		}
	}
	url := fmt.Sprintf("/api/admin/pages/%d/preview", id)
	out.PreviewURL = &url
	return out, nil
}

func (m *Module) readPlainPage(ctx *app.Ctx, in PlainPageIn) (PlainPageDetail, error) {
	return readPlainPageRow(ctx.Context, m.svc.store.d.ReadPool(), int64(in.ID))
}

func plainTextField(key string, value any) (string, string) {
	text, ok := value.(string)
	if !ok {
		return "", "格式无效"
	}
	switch key {
	case "title", "seo_title":
		if utf8.RuneCountInString(text) > 255 {
			return "", "不超过255字"
		}
	case "search_description":
		if utf8.RuneCountInString(text) > 1000 {
			return "", "不超过1000字"
		}
	case "body_md":
		if len(text) > 1024*1024 {
			return "", "正文不超过1 MB"
		}
	default:
		return "", "这个字段不能修改"
	}
	return text, ""
}

func (m *Module) patchPlainPage(ctx *app.Ctx, in PlainPagePatchIn) (PlainPagePatchOut, error) {
	out := PlainPagePatchOut{Saved: []string{}, Fields: map[string][]string{}, SavedAt: ctx.Now().UTC()}
	err := m.svc.store.d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		current, err := readPlainPageRow(c, tx, int64(in.ID))
		if err != nil {
			return err
		}
		out.Values = current.Draft
		out.Version = current.Version
		if current.Version != in.BaseVersion {
			return api.Stale(map[string]any{"version": current.Version, "values": current.Draft})
		}
		for key, value := range in.Changes {
			text, message := plainTextField(key, value)
			if message != "" {
				out.Fields[key] = []string{message}
				continue
			}
			switch key {
			case "title":
				out.Values.Title = text
			case "body_md":
				out.Values.BodyMD = text
			case "seo_title":
				out.Values.SeoTitle = text
			case "search_description":
				out.Values.SearchDescription = text
			}
			out.Saved = append(out.Saved, key)
		}
		if len(out.Saved) == 0 {
			return nil
		}
		bytes, err := json.Marshal(out.Values)
		if err != nil {
			return err
		}
		var latest, live *int64
		if err := tx.QueryRowContext(c, "SELECT latest_revision_id,live_revision_id FROM pages WHERE id=?", int64(in.ID)).Scan(&latest, &live); err != nil {
			return err
		}
		var revisionID int64
		if latest != nil {
			var author *int64
			var created string
			var scheduled sql.NullString
			err := tx.QueryRowContext(c, "SELECT author_id,created_at,approved_go_live_at FROM page_revisions WHERE id=? AND page_id=?", *latest, int64(in.ID)).Scan(&author, &created, &scheduled)
			if err != nil {
				return err
			}
			at, parseErr := db.ParseUTC(created)
			sameAuthor := author != nil && *author == ctx.Viewer.ID
			notLive := live == nil || *live != *latest
			recent := parseErr == nil && ctx.Now().Sub(at) >= 0 && ctx.Now().Sub(at) < 30*time.Minute
			if sameAuthor && notLive && !scheduled.Valid && recent {
				revisionID = *latest
			}
		}
		if revisionID != 0 {
			if _, err := tx.ExecContext(c, "UPDATE page_revisions SET content=?,created_at=? WHERE id=? AND page_id=?", string(bytes), out.SavedAt.Format(time.RFC3339Nano), revisionID, int64(in.ID)); err != nil {
				return err
			}
		} else {
			result, err := tx.ExecContext(c, "INSERT INTO page_revisions(page_id,author_id,content,created_at) VALUES(?,?,?,?)", int64(in.ID), ctx.Viewer.ID, string(bytes), out.SavedAt.Format(time.RFC3339Nano))
			if err != nil {
				return err
			}
			revisionID, err = result.LastInsertId()
			if err != nil {
				return err
			}
		}
		_, err = tx.ExecContext(c, "UPDATE pages SET version=version+1,latest_revision_id=?,has_unpublished_changes=1,updated_at=? WHERE id=? AND version=?",
			revisionID, out.SavedAt.Format(time.RFC3339Nano), int64(in.ID), in.BaseVersion)
		if err != nil {
			return err
		}
		out.Version++
		return contentAudit(c, tx, ctx.Viewer.ID, "page.save_draft", "page", int64(in.ID), map[string]any{"saved": out.Saved}, out.SavedAt)
	})
	return out, err
}

func (m *Module) publishPlainPage(ctx *app.Ctx, in PlainPagePublishIn) (PlainPagePublishOut, error) {
	out := PlainPagePublishOut{}
	err := m.svc.store.d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		current, err := readPlainPageRow(c, tx, int64(in.ID))
		if err != nil {
			return err
		}
		if current.Version != in.BaseVersion {
			return api.Stale(map[string]any{"version": current.Version, "values": current.Draft})
		}
		if strings.TrimSpace(current.Draft.Title) == "" {
			return api.InvalidFields(map[string][]string{"title": {"标题不能为空"}})
		}
		rendered, _, err := markdown.Render(current.Draft.BodyMD, m.svc.siteURL, nil)
		if err != nil {
			return err
		}
		now := ctx.Now().UTC().Format(time.RFC3339Nano)
		_, err = tx.ExecContext(c, "UPDATE site_pages SET body_md=?,body_html=?,body_plain=? WHERE page_id=?", current.Draft.BodyMD, rendered, markdown.PlainHTML(rendered), int64(in.ID))
		if err != nil {
			return err
		}
		_, err = tx.ExecContext(c, `UPDATE pages SET title=?,seo_title=?,search_description=?,live=1,has_unpublished_changes=0,
            live_revision_id=latest_revision_id,version=version+1,last_published_at=?,first_published_at=COALESCE(first_published_at,?),updated_at=? WHERE id=? AND version=?`,
			current.Draft.Title, current.Draft.SeoTitle, current.Draft.SearchDescription, now, now, now, int64(in.ID), in.BaseVersion)
		if err != nil {
			return err
		}
		out.Version = current.Version + 1
		out.Page = current.Page
		out.Page.Version = out.Version
		out.Page.Title = current.Draft.Title
		out.Page.Live = true
		out.Page.HasUnpublishedChanges = false
		out.Page.UpdatedAt = ctx.Now().UTC()
		return contentAudit(c, tx, ctx.Viewer.ID, "page.publish", "page", int64(in.ID), nil, ctx.Now())
	})
	return out, err
}

func contentAudit(ctx context.Context, tx *db.Tx, actor int64, action, kind string, id int64, data any, now time.Time) error {
	if data == nil {
		data = map[string]any{}
	}
	encoded, err := json.Marshal(data)
	if err != nil {
		return err
	}
	_, err = tx.ExecContext(ctx, "INSERT INTO audit_log(actor_id,action,object_type,object_id,data,created_at) VALUES(?,?,?,?,?,?)", actor, action, kind, id, string(encoded), now.UTC().Format(time.RFC3339Nano))
	return err
}

func (m *Module) servePlainPagePreview(w http.ResponseWriter, r *http.Request) {
	privatePreviewHeaders(w)
	viewer := m.previewViewer(w, r)
	if viewer == nil {
		return
	}
	if !viewer.HasCap(CapSitePagesManage) {
		http.Error(w, "没有权限", http.StatusForbidden)
		return
	}
	id, ok := api.ParseID(r.PathValue("id"))
	if !ok {
		http.NotFound(w, r)
		return
	}
	result, err := readPlainPageRow(r.Context(), m.svc.store.d.ReadPool(), int64(id))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	rendered, _, err := markdown.Render(result.Draft.BodyMD, m.svc.siteURL, nil)
	if err != nil {
		http.Error(w, "预览暂时不可用", http.StatusInternalServerError)
		return
	}
	_, _ = fmt.Fprint(w, m.previewDocument(result.Draft.Title, rendered))
}
