package content

import (
	"context"
	"fmt"
	"strings"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

var articleFields = map[string]bool{
	"title": true, "summary": true, "body_md": true, "category_id": true, "cover_image_id": true,
	"author_id": true, "comments_enabled": true, "related_tournament_id": true, "slug": true,
	"seo_title": true, "search_description": true, "go_live_at": true, "expire_at": true,
}

func (s *Service) validateArticleChanges(ctx *app.Ctx, changes map[string]any) (map[string][]string, error) {
	return s.validateArticleChangesWithCover(ctx, changes, nil)
}

func (s *Service) validateArticleChangesWithCover(ctx *app.Ctx, changes map[string]any, currentCover *int64) (map[string][]string, error) {
	fields := map[string][]string{}
	for key, value := range changes {
		if !articleFields[key] {
			fields[key] = []string{"这个字段不能修改"}
			continue
		}
		switch key {
		case "title", "summary", "body_md", "slug", "seo_title", "search_description":
			text, ok := value.(string)
			if !ok {
				fields[key] = []string{"格式无效"}
				continue
			}
			limit := 1024 * 1024
			switch key {
			case "title", "slug", "seo_title":
				limit = 255
			case "summary", "search_description":
				limit = 1000
			}
			tooLong := len(text) > limit
			if key != "body_md" {
				tooLong = utf8.RuneCountInString(text) > limit
			}
			if tooLong {
				fields[key] = []string{fmt.Sprintf("内容不超过%d字", limit)}
				continue
			}
			if key == "slug" {
				for _, r := range strings.TrimSpace(text) {
					if !IsSafeRune(r) {
						fields[key] = []string{"网址片段只能包含文字、数字、连字符和下划线"}
						break
					}
				}
			}
			if (key == "slug" || key == "seo_title" || key == "search_description") && !s.canEditScheduleAndSlug(ctx.Viewer) {
				fields[key] = []string{"没有权限修改这个字段"}
			}
		case "author_id":
			if !s.canEditAuthor(ctx.Viewer) {
				fields[key] = []string{"没有权限修改这个字段"}
				continue
			}
			if value == nil {
				continue
			}
			id, ok := toInt64(value)
			if !ok || id <= 0 {
				fields[key] = []string{"作者编号无效"}
				continue
			}
			var found int
			if err := s.store.d.ReadPool().QueryRowContext(ctx.Context, "SELECT COUNT(*) FROM users WHERE id=? AND is_active=1", id).Scan(&found); err != nil {
				return nil, err
			}
			if found != 1 {
				fields[key] = []string{"作者不存在或已停用"}
			}
		case "cover_image_id", "related_tournament_id":
			if value == nil {
				continue
			}
			id, ok := toInt64(value)
			if !ok || id <= 0 {
				fields[key] = []string{"编号无效"}
				continue
			}
			if key == "cover_image_id" {
				allowed, err := media.CanChooseImage(ctx.Context, s.store.d.ReadPool(), ctx.Viewer, id)
				if err != nil {
					return nil, err
				}
				if !allowed && (currentCover == nil || *currentCover != id) {
					fields[key] = []string{"请选择有权限使用的图片"}
				}
				continue
			}
			query := "SELECT COUNT(*) FROM images WHERE id=?"
			if key == "related_tournament_id" {
				query = "SELECT COUNT(*) FROM tournaments WHERE id=?"
			}
			var found int
			if err := s.store.d.ReadPool().QueryRowContext(ctx.Context, query, id).Scan(&found); err != nil {
				return nil, err
			}
			if found != 1 {
				fields[key] = []string{"关联对象不存在"}
			}
		case "category_id":
			if value == nil {
				continue
			}
			id, ok := toInt64(value)
			if !ok || id <= 0 {
				fields[key] = []string{"分类编号无效"}
				continue
			}
			var allowed int
			var exists int
			if err := s.store.d.ReadPool().QueryRowContext(ctx.Context, "SELECT COUNT(*),COALESCE(MAX(allow_submission),0) FROM article_categories WHERE id=?", id).Scan(&exists, &allowed); err != nil {
				return nil, err
			}
			if exists != 1 {
				fields[key] = []string{"分类不存在"}
			} else if s.isPureSubmitter(ctx.Viewer) && allowed != 1 {
				fields[key] = []string{"请选择开放投稿的分类"}
			}
		case "comments_enabled":
			if _, ok := value.(bool); !ok {
				fields[key] = []string{"评论开关格式无效"}
			}
			if s.isPureSubmitter(ctx.Viewer) {
				fields[key] = []string{"没有权限修改这个字段"}
			}
		case "go_live_at", "expire_at":
			if !s.canEditScheduleAndSlug(ctx.Viewer) {
				fields[key] = []string{"没有权限修改这个字段"}
				continue
			}
			if value != nil {
				if _, ok := value.(string); !ok {
					fields[key] = []string{"时间格式无效"}
				}
			}
		}
	}
	return fields, nil
}

func validateCategoryValues(category *Category) error {
	fields := map[string][]string{}
	if utf8.RuneCountInString(category.Name) > 255 {
		fields["name"] = []string{"名称不超过255字"}
	}
	if utf8.RuneCountInString(category.Slug) > 255 {
		fields["slug"] = []string{"网址片段不超过255字"}
	}
	if strings.ContainsAny(category.Slug, "/?#\\\r\n") {
		fields["slug"] = []string{"网址片段不能包含路径或查询字符"}
	}
	if utf8.RuneCountInString(category.Description) > 10000 {
		fields["description"] = []string{"说明不超过10000字"}
	}
	if len(fields) > 0 {
		return api.InvalidFields(fields)
	}
	return nil
}

// Recheck a changed cover under the same writer lock as the revision save.
func coverWriteCheck(viewer *app.Viewer, chosen, previous *int64) func(context.Context, *db.Tx) error {
	return func(ctx context.Context, tx *db.Tx) error {
		if chosen == nil || previous != nil && *chosen == *previous {
			return nil
		}
		allowed, err := media.CanChooseImage(ctx, tx, viewer, *chosen)
		if err != nil {
			return err
		}
		if !allowed {
			return api.Forbidden()
		}
		return nil
	}
}
