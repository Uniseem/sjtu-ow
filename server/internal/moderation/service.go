// Package moderation 是内容审核（设计 5.5，12 号文档 7，规则 R184–R205）。AI 路径唯一能写的是
// 待复核记录，从不改内容、账号或可见性。**AI 巡查按决定 D5 割接后再移植**：本包现在有表、
// 送审接口（Submit，接给各域的 ModerationSink）、人工复核（标记、处置、发信要求作者修改）、
// 180 天清理和存量导入；巡查（调模型、配额、去重复用）不在这里。
package moderation

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

// 内容类型（规则 186）。
const (
	TargetNickname         = "nickname"
	TargetMotto            = "motto"
	TargetTeamName         = "team_name"
	TargetTeamDescription  = "team_description"
	TargetApplicationMsg   = "application_message"
	TargetArticle          = "article"
	TargetTournamentDesc   = "tournament_description"
	TargetScrimDescription = "scrim_description"
	TargetPage             = "page"
	TargetImage            = "image"
	TargetComment          = "comment"
)

var targetLabels = map[string]string{
	TargetNickname: "昵称", TargetMotto: "个人宣言", TargetTeamName: "队名", TargetTeamDescription: "战队简介",
	TargetApplicationMsg: "入队申请留言", TargetArticle: "文章 / 稿件", TargetTournamentDesc: "赛事说明",
	TargetScrimDescription: "内战说明", TargetPage: "普通页面", TargetImage: "图片", TargetComment: "评论",
}

// 短文只存摘录，别的整篇存 full_text 待巡查读（规则 188）。
var shortTypes = map[string]bool{TargetNickname: true, TargetMotto: true, TargetTeamName: true, TargetComment: true}

const (
	// ExcerptChars 摘录的字数（规则 188）。
	ExcerptChars = 2000
	// ReviseMaxChars 要求作者修改的说明上限（规则 203）。
	ReviseMaxChars = 500
	// NoteMax 处置说明上限。
	NoteMax = 300
	// KeepDays 已处理的记录保留多少天（规则 204）。
	KeepDays = 180
	// PageSize 复核列表每页条数。
	PageSize = 25
)

// 记录状态。
const (
	StatusPending = "pending"
	StatusOK      = "ok"
	StatusHandled = "handled"
	StatusIgnored = "ignored"
)

// Item 是一条待复核记录。
type Item struct {
	ID           int64      `json:"id"`
	TargetType   string     `json:"target_type"`
	TargetLabel  string     `json:"target_label"`
	TargetID     int64      `json:"target_id"`
	Field        string     `json:"field"`
	URL          string     `json:"url"`
	AuthorID     *int64     `json:"author_id"`
	Excerpt      string     `json:"excerpt"`
	FullText     string     `json:"full_text,omitempty"`
	TextHash     string     `json:"text_hash"`
	Risk         string     `json:"risk"`
	Categories   []string   `json:"categories"`
	Reason       string     `json:"reason"`
	Quote        string     `json:"quote"`
	Status       string     `json:"status"`
	ReviewedBy   *int64     `json:"reviewed_by"`
	ReviewedAt   *time.Time `json:"reviewed_at"`
	HandlingNote string     `json:"handling_note"`
	CheckedAt    *time.Time `json:"checked_at"`
	NotifiedAt   *time.Time `json:"notified_at"`
	Attempts     int        `json:"attempts"`
	LastError    string     `json:"last_error"`
	FailedAt     *time.Time `json:"failed_at"`
	CreatedAt    time.Time  `json:"created_at"`
}

// NeedsReview 等人复核：待复核且不是「无风险」。
func (i *Item) NeedsReview() bool { return i.Status == StatusPending && i.Risk != "none" }

// Service 是审核域的业务。
type Service struct {
	d       *db.DB
	siteURL string
}

// NewService 造审核服务；d 可以是 nil（apigen）。
func NewService(d *db.DB, siteURL string) *Service {
	return &Service{d: d, siteURL: strings.TrimRight(siteURL, "/")}
}

// Enabled 全站开关开着、并且配置好了才送审（规则 185）：没配好就入队的话，新装的站会攒一堆
// 永远等不到结论的「无法判定」。
func (s *Service) Enabled(ctx context.Context, q db.DBTX) bool {
	var enabled, configured int
	if err := q.QueryRowContext(ctx, `SELECT moderation_enabled, moderation_configured FROM site_settings WHERE id = 1`).
		Scan(&enabled, &configured); err != nil {
		return false
	}
	return enabled == 1 && configured == 1
}

func hashOf(text string) string {
	sum := sha256.Sum256([]byte(strings.TrimSpace(text)))
	return hex.EncodeToString(sum[:])
}

func truncate(s string, n int) string {
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n])
}

// Submit 把一段内容放进待巡查记录（规则 185–188）。各域的 ModerationSink 都是它；失败只记日志，
// 调用方不会因此失败。文本为空、开关没开都直接跳过。
func (s *Service) Submit(ctx context.Context, targetType string, targetID int64, field, text, url string, authorID int64) error {
	text = strings.TrimSpace(text)
	if text == "" || !s.Enabled(ctx, s.d.ReadPool()) {
		return nil
	}
	digest := hashOf(text)
	excerpt := truncate(text, ExcerptChars)
	full := text
	if shortTypes[targetType] {
		full = ""
	}
	var author any
	if authorID > 0 {
		author = authorID
	}
	now := db.FormatUTC(time.Now().UTC())
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		// 同一处没读过的旧文本被最新文本替换：自动保存的半成品不逐版排队（规则 187）。
		var existing int64
		err := tx.QueryRowContext(txCtx, `SELECT id FROM moderation_items WHERE target_type = ? AND target_id = ? AND field = ? AND text_hash = ?`,
			targetType, targetID, field, digest).Scan(&existing)
		if err == nil {
			// 文本相同：复用现有记录，旧的没读过的半成品一起清掉
			_, err = tx.ExecContext(txCtx, `DELETE FROM moderation_items WHERE target_type = ? AND target_id = ? AND field = ?
				AND checked_at IS NULL AND text_hash <> ?`, targetType, targetID, field, digest)
			return err
		}
		if !errors.Is(err, sql.ErrNoRows) {
			return err
		}
		var stale int64
		err = tx.QueryRowContext(txCtx, `SELECT id FROM moderation_items WHERE target_type = ? AND target_id = ? AND field = ?
			AND checked_at IS NULL ORDER BY created_at DESC, id DESC LIMIT 1`, targetType, targetID, field).Scan(&stale)
		if err == nil {
			if _, err := tx.ExecContext(txCtx, `DELETE FROM moderation_items WHERE target_type = ? AND target_id = ? AND field = ?
				AND checked_at IS NULL AND id <> ?`, targetType, targetID, field, stale); err != nil {
				return err
			}
			_, err = tx.ExecContext(txCtx, `UPDATE moderation_items SET excerpt = ?, url = ?, author_id = ?, full_text = ?, text_hash = ?,
				attempts = 0, last_error = '', failed_at = NULL WHERE id = ?`, excerpt, url, author, full, digest, stale)
			return err
		}
		if !errors.Is(err, sql.ErrNoRows) {
			return err
		}
		_, err = tx.ExecContext(txCtx, `INSERT INTO moderation_items
			(target_type, target_id, field, url, author_id, excerpt, full_text, text_hash, risk, created_at)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unknown', ?)`, targetType, targetID, field, url, author, excerpt, full, digest, now)
		return err
	})
}

func requireReviewer(ctx *app.Ctx) (*app.Viewer, error) {
	v := ctx.Viewer
	if v == nil || v.Disabled || v.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if !v.HasCap(accounts.CapModerationReview) {
		return nil, api.Forbidden()
	}
	return v, nil
}

const itemCols = `id, target_type, target_id, field, url, author_id, excerpt, full_text, text_hash, risk, categories, reason,
	quote, status, reviewed_by, reviewed_at, handling_note, checked_at, notified_at, attempts, last_error, failed_at, created_at`

func scanItem(row interface{ Scan(...any) error }) (*Item, error) {
	var i Item
	var author, by sql.NullInt64
	var reviewed, checked, notified, failed sql.NullString
	var cats, created string
	if err := row.Scan(&i.ID, &i.TargetType, &i.TargetID, &i.Field, &i.URL, &author, &i.Excerpt, &i.FullText, &i.TextHash,
		&i.Risk, &cats, &i.Reason, &i.Quote, &i.Status, &by, &reviewed, &i.HandlingNote, &checked, &notified,
		&i.Attempts, &i.LastError, &failed, &created); err != nil {
		return nil, err
	}
	if author.Valid {
		v := author.Int64
		i.AuthorID = &v
	}
	if by.Valid {
		v := by.Int64
		i.ReviewedBy = &v
	}
	pt := func(ns sql.NullString) *time.Time {
		if !ns.Valid || ns.String == "" {
			return nil
		}
		t, err := db.ParseUTC(ns.String)
		if err != nil {
			return nil
		}
		return &t
	}
	i.ReviewedAt, i.CheckedAt, i.NotifiedAt, i.FailedAt = pt(reviewed), pt(checked), pt(notified), pt(failed)
	i.CreatedAt, _ = db.ParseUTC(created)
	i.Categories = []string{}
	_ = json.Unmarshal([]byte(cats), &i.Categories)
	i.TargetLabel = targetLabels[i.TargetType]
	return &i, nil
}

func getItem(ctx context.Context, q db.DBTX, id int64) (*Item, error) {
	i, err := scanItem(q.QueryRowContext(ctx, `SELECT `+itemCols+` FROM moderation_items WHERE id = ?`, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return i, err
}

// ListInput 是复核列表的筛选。
type ListInput struct {
	Status     string
	Risk       string
	TargetType string
	SinceDays  int
	Page       int
}

// ListResult 是复核列表页。
type ListResult struct {
	Items     []*Item `json:"items"`
	Total     int     `json:"total"`
	Page      int     `json:"page"`
	PageSize  int     `json:"page_size"`
	Enabled   bool    `json:"enabled"`
	Waiting   int     `json:"waiting"`    // AI 还没读的
	Failed    int     `json:"failed"`     // 其中最近一次没看成的
	LastError string  `json:"last_error"` // 最近一次没看成的原因
}

// List 复核列表（规则 202）：默认待复核；「无风险」的不进列表；待复核只显示 AI 已经看过的。
func (s *Service) List(ctx *app.Ctx, in ListInput) (*ListResult, error) {
	if _, err := requireReviewer(ctx); err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	status := in.Status
	if status == "" {
		status = StatusPending
	}
	where := []string{"risk <> 'none'"}
	var args []any
	if in.SinceDays > 0 {
		where = append(where, "created_at >= ?")
		args = append(args, db.FormatUTC(ctx.Now().UTC().Add(-time.Duration(in.SinceDays)*24*time.Hour)))
	}
	where = append(where, "status = ?")
	args = append(args, status)
	if status == StatusPending {
		where = append(where, "checked_at IS NOT NULL")
	}
	if in.Risk != "" {
		where = append(where, "risk = ?")
		args = append(args, in.Risk)
	}
	if in.TargetType != "" {
		where = append(where, "target_type = ?")
		args = append(args, in.TargetType)
	}
	cond := strings.Join(where, " AND ")
	res := &ListResult{Items: []*Item{}, PageSize: PageSize, Page: in.Page, Enabled: s.Enabled(ctx.Context, rd)}
	if res.Page < 1 {
		res.Page = 1
	}
	if err := rd.QueryRowContext(ctx.Context, `SELECT COUNT(*) FROM moderation_items WHERE `+cond, args...).Scan(&res.Total); err != nil {
		return nil, err
	}
	rows, err := rd.QueryContext(ctx.Context, `SELECT `+itemCols+` FROM moderation_items WHERE `+cond+
		` ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?`, append(args, PageSize, (res.Page-1)*PageSize)...)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		i, err := scanItem(rows)
		if err != nil {
			rows.Close()
			return nil, err
		}
		i.FullText = ""
		res.Items = append(res.Items, i)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	// AI 还没读的和没看成的（待办和复核列表用，规则 205）
	if err := rd.QueryRowContext(ctx.Context, `SELECT COUNT(*), COALESCE(SUM(failed_at IS NOT NULL), 0) FROM moderation_items WHERE checked_at IS NULL`).
		Scan(&res.Waiting, &res.Failed); err != nil {
		return nil, err
	}
	if res.Failed > 0 {
		_ = rd.QueryRowContext(ctx.Context, `SELECT last_error FROM moderation_items WHERE checked_at IS NULL AND failed_at IS NOT NULL
			ORDER BY failed_at DESC LIMIT 1`).Scan(&res.LastError)
	}
	return res, nil
}

// Detail 是复核页。
type Detail struct {
	Item          *Item         `json:"item"`
	AuthorFlags   int           `json:"author_flags"`   // 这个作者还有几条别的可疑内容
	AuthorProblem string        `json:"author_problem"` // 不能给作者发信的原因，空串表示可以
	History       []audit.Entry `json:"history"`
}

func authorProblem(ctx context.Context, q db.DBTX, i *Item) (string, error) {
	if i.AuthorID == nil {
		return "这条内容没有作者（系统内容，或作者已注销），不能发信。", nil
	}
	var active int
	var email string
	if err := q.QueryRowContext(ctx, `SELECT is_active, email FROM users WHERE id = ?`, *i.AuthorID).Scan(&active, &email); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return "这条内容没有作者（系统内容，或作者已注销），不能发信。", nil
		}
		return "", err
	}
	if active != 1 {
		return "作者的账号已停用，不能发信。", nil
	}
	if strings.HasSuffix(email, ".invalid") || email == "" {
		return "作者没有邮箱，不能发信。", nil
	}
	return "", nil
}

// Get 复核页。
func (s *Service) Get(ctx *app.Ctx, id int64) (*Detail, error) {
	if _, err := requireReviewer(ctx); err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	i, err := getItem(ctx.Context, rd, id)
	if err != nil {
		return nil, err
	}
	if i == nil {
		return nil, api.NotFound("记录不存在")
	}
	d := &Detail{Item: i}
	if i.AuthorID != nil {
		if err := rd.QueryRowContext(ctx.Context, `SELECT COUNT(*) FROM moderation_items WHERE author_id = ? AND id <> ? AND risk <> 'none'`,
			*i.AuthorID, id).Scan(&d.AuthorFlags); err != nil {
			return nil, err
		}
	}
	if d.AuthorProblem, err = authorProblem(ctx.Context, rd, i); err != nil {
		return nil, err
	}
	if d.History, err = audit.For(ctx.Context, rd, "moderation_item", id); err != nil {
		return nil, err
	}
	return d, nil
}

var handleStatus = map[string]string{"ok": StatusOK, "handled": StatusHandled, "ignored": StatusIgnored}

// Handle 人工处置（规则 202）：标为无问题、已处置或忽略，写复核人、时间、说明，并进操作记录。
func (s *Service) Handle(ctx *app.Ctx, id int64, action, note string) (*Item, error) {
	v, err := requireReviewer(ctx)
	if err != nil {
		return nil, err
	}
	status, ok := handleStatus[action]
	if !ok {
		return nil, api.InvalidFields(map[string][]string{"action": {"处置方式只能是 ok、handled 或 ignored。"}})
	}
	note = strings.TrimSpace(note)
	if utf8.RuneCountInString(note) > NoteMax {
		return nil, api.InvalidFields(map[string][]string{"note": {fmt.Sprintf("说明最多 %d 字。", NoteMax)}})
	}
	now := ctx.Now().UTC()
	var out *Item
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		i, err := getItem(txCtx, tx, id)
		if err != nil {
			return err
		}
		if i == nil {
			return api.NotFound("记录不存在")
		}
		if _, err := tx.ExecContext(txCtx, `UPDATE moderation_items SET status = ?, reviewed_by = ?, reviewed_at = ?, handling_note = ? WHERE id = ?`,
			status, v.ID, db.FormatUTC(now), note, id); err != nil {
			return err
		}
		if err := audit.Record(txCtx, tx, v.ID, "moderation.handle", "moderation_item", id,
			map[string]any{"result": action, "note": note}, now); err != nil {
			return err
		}
		out, err = getItem(txCtx, tx, id)
		return err
	})
	return out, err
}

func (s *Service) reviseURL(i *Item) string {
	switch i.TargetType {
	case TargetNickname, TargetMotto:
		return s.siteURL + "/me/profile/"
	case TargetTeamName, TargetTeamDescription:
		return fmt.Sprintf("%s/teams/%d/manage/", s.siteURL, i.TargetID)
	case TargetApplicationMsg:
		return s.siteURL + "/me/teams/"
	case TargetArticle:
		return fmt.Sprintf("%s/admin/articles/%d/", s.siteURL, i.TargetID)
	case TargetPage:
		return fmt.Sprintf("%s/admin/pages/%d/", s.siteURL, i.TargetID)
	case TargetTournamentDesc:
		return fmt.Sprintf("%s/admin/tournaments/%d/", s.siteURL, i.TargetID)
	case TargetScrimDescription:
		return fmt.Sprintf("%s/admin/scrims/%d/", s.siteURL, i.TargetID)
	case TargetComment:
		if strings.HasPrefix(i.URL, "/") {
			return s.siteURL + i.URL
		}
		return i.URL
	}
	return ""
}

var reviseNouns = map[string]string{TargetArticle: "文章", TargetPage: "页面"}

// AskAuthor 复核页唯一的直接处置：发信要求作者修改（规则 203，v6.17 直接处置只做发信）。
// 说明必填、≤500 字；作者缺失、停用或没邮箱不能发。这条记录算已处置，整段说明留在操作记录里，
// 信里说明之前已经发过几次（设计 10.3）。
func (s *Service) AskAuthor(ctx *app.Ctx, id int64, message string) (*Item, error) {
	v, err := requireReviewer(ctx)
	if err != nil {
		return nil, err
	}
	message = strings.TrimSpace(message)
	if message == "" {
		return nil, api.InvalidFields(map[string][]string{"message": {"写一段说明，告诉作者要改什么。"}})
	}
	if utf8.RuneCountInString(message) > ReviseMaxChars {
		return nil, api.InvalidFields(map[string][]string{"message": {fmt.Sprintf("说明最多 %d 字。", ReviseMaxChars)}})
	}
	now := ctx.Now().UTC()
	var out *Item
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		i, err := getItem(txCtx, tx, id)
		if err != nil {
			return err
		}
		if i == nil {
			return api.NotFound("记录不存在")
		}
		if p, err := authorProblem(txCtx, tx, i); err != nil {
			return err
		} else if p != "" {
			return api.NewErr(http.StatusConflict, "refused", p)
		}
		var before int
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM audit_log WHERE object_type = 'moderation_item' AND object_id = ? AND action = 'moderation.ask_author'`, id).
			Scan(&before); err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `UPDATE moderation_items SET status = 'handled', handling_note = '已发信要求作者修改',
			reviewed_by = ?, reviewed_at = ? WHERE id = ?`, v.ID, db.FormatUTC(now), id); err != nil {
			return err
		}
		if err := audit.Record(txCtx, tx, v.ID, "moderation.ask_author", "moderation_item", id,
			map[string]any{"result": "要求作者修改（已发信）", "note": message}, now); err != nil {
			return err
		}
		var nick, email string
		if err := tx.QueryRowContext(txCtx, `SELECT nickname, email FROM users WHERE id = ?`, *i.AuthorID).Scan(&nick, &email); err != nil {
			return err
		}
		// 复核页的动作，直接发（不过待发信确认）
		_, err = outbox.Send(txCtx, tx, nil, s.siteURL, s.reviseLetter(i, message, before), []mail.Person{{Address: email, Name: nick}}, now)
		if err != nil {
			return err
		}
		out, err = getItem(txCtx, tx, id)
		return err
	})
	return out, err
}

func (s *Service) reviseLetter(i *Item, message string, before int) mail.Letter {
	kind := targetLabels[i.TargetType]
	noun := reviseNouns[i.TargetType]
	if noun == "" {
		noun = kind
	}
	quote := i.Quote
	if quote == "" {
		quote = i.Excerpt
	}
	notice := ""
	if before > 0 {
		notice = fmt.Sprintf("关于这条%s，之前已经发过 %d 次修改提醒，这次可能有修改，请以这封为准。", noun, before)
	}
	l := mail.Letter{
		Subject:    "请修改你的" + noun,
		Lead:       fmt.Sprintf("社区的管理员看过你发布的一条%s，请你按下面的说明修改。", noun),
		Facts:      [][2]string{{"内容类型", kind}, {"内容片段", truncate(quote, 200)}},
		Paragraphs: []string{"管理员的说明：" + message, "改完保存就行，不用回复这封邮件。"},
		Reason:     "你收到这封邮件，是因为你在社区发布的内容需要修改。",
		Notice:     notice,
	}
	if link := s.reviseURL(i); link != "" {
		l.Action = []string{"去修改", link}
	}
	return l
}

// Cleanup 清理已处理的记录（规则 204、230）：状态不再是待复核、复核时间（没有就用创建时间）
// 早于 180 天的；没人处理过的永不删。返回删了几条。
func (s *Service) Cleanup(ctx context.Context, now time.Time) (int, error) {
	cutoff := db.FormatUTC(now.Add(-KeepDays * 24 * time.Hour))
	n := 0
	err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `DELETE FROM moderation_items WHERE status <> 'pending'
			AND ((reviewed_at IS NOT NULL AND reviewed_at < ?) OR (reviewed_at IS NULL AND created_at < ?))`, cutoff, cutoff)
		if err != nil {
			return err
		}
		c, _ := res.RowsAffected()
		n = int(c)
		return nil
	})
	return n, err
}
