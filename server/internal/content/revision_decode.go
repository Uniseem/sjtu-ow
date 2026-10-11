package content

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Imported Wagtail revisions keep their original JSON. Read aliases at the
// domain boundary without rewriting or dropping historical source material.
func revisionObject(content string) (map[string]json.RawMessage, error) {
	var object map[string]json.RawMessage
	if err := json.Unmarshal([]byte(content), &object); err != nil {
		return nil, fmt.Errorf("修订不是有效JSON: %w", err)
	}
	if object == nil {
		return nil, fmt.Errorf("修订内容不是对象")
	}
	return object, nil
}

func revisionField(object map[string]json.RawMessage, names ...string) (json.RawMessage, bool) {
	for _, name := range names {
		if value, ok := object[name]; ok {
			return value, true
		}
	}
	return nil, false
}

func revisionText(object map[string]json.RawMessage, target *string, names ...string) error {
	raw, present := revisionField(object, names...)
	if !present {
		return nil
	}
	var text string
	if err := json.Unmarshal(raw, &text); err != nil {
		return fmt.Errorf("修订字段%s不是文本", names[0])
	}
	*target = text
	return nil
}

func revisionID(object map[string]json.RawMessage, target **int64, names ...string) error {
	raw, present := revisionField(object, names...)
	if !present {
		return nil
	}
	if string(raw) == "null" {
		*target = nil
		return nil
	}
	var id int64
	if err := json.Unmarshal(raw, &id); err != nil || id <= 0 {
		return fmt.Errorf("修订字段%s的编号无效", names[0])
	}
	*target = &id
	return nil
}

func revisionTime(object map[string]json.RawMessage, target **time.Time, name string) error {
	raw, present := revisionField(object, name)
	if !present {
		return nil
	}
	if string(raw) == "null" {
		*target = nil
		return nil
	}
	var text string
	if err := json.Unmarshal(raw, &text); err != nil {
		return fmt.Errorf("修订字段%s的时间无效", name)
	}
	if strings.TrimSpace(text) == "" {
		*target = nil
		return nil
	}
	parsed, err := db.ParseUTC(text)
	if err != nil {
		return fmt.Errorf("修订字段%s的时间无效: %w", name, err)
	}
	*target = &parsed
	return nil
}

func readArticleRevisionContent(content string, fallback ArticleRevisionContent) (ArticleRevisionContent, error) {
	result := fallback
	object, err := revisionObject(content)
	if err != nil {
		return result, err
	}
	fields := []struct {
		target *string
		names  []string
	}{
		{&result.Title, []string{"title"}},
		{&result.Slug, []string{"slug"}},
		{&result.Summary, []string{"summary"}},
		{&result.BodyMD, []string{"body_md", "body"}},
		{&result.SeoTitle, []string{"seo_title"}},
		{&result.SearchDescription, []string{"search_description"}},
	}
	for _, field := range fields {
		if err := revisionText(object, field.target, field.names...); err != nil {
			return result, err
		}
	}
	ids := []struct {
		target **int64
		names  []string
	}{
		{&result.CategoryID, []string{"category_id", "category"}},
		{&result.CoverImageID, []string{"cover_image_id", "cover_image"}},
		{&result.AuthorID, []string{"author_id", "author"}},
		{&result.RelatedTournamentID, []string{"related_tournament_id", "related_tournament"}},
	}
	for _, field := range ids {
		if err := revisionID(object, field.target, field.names...); err != nil {
			return result, err
		}
	}
	if raw, present := revisionField(object, "comments_enabled"); present {
		if err := json.Unmarshal(raw, &result.CommentsEnabled); err != nil {
			return result, fmt.Errorf("修订字段comments_enabled不是布尔值")
		}
	}
	if err := revisionTime(object, &result.GoLiveAt, "go_live_at"); err != nil {
		return result, err
	}
	if err := revisionTime(object, &result.ExpireAt, "expire_at"); err != nil {
		return result, err
	}
	return result, nil
}

func readPlainRevisionContent(content string, fallback PlainPageDraft) (PlainPageDraft, error) {
	result := fallback
	object, err := revisionObject(content)
	if err != nil {
		return result, err
	}
	fields := []struct {
		target *string
		names  []string
	}{
		{&result.Title, []string{"title"}},
		{&result.BodyMD, []string{"body_md", "body"}},
		{&result.SeoTitle, []string{"seo_title"}},
		{&result.SearchDescription, []string{"search_description"}},
	}
	for _, field := range fields {
		if err := revisionText(object, field.target, field.names...); err != nil {
			return result, err
		}
	}
	return result, nil
}

func readNewsRevisionContent(content string, fallback NewsDraft) (NewsDraft, error) {
	result := fallback
	object, err := revisionObject(content)
	if err != nil {
		return result, err
	}
	if err := revisionText(object, &result.IntroMD, "intro_md", "intro"); err != nil {
		return result, err
	}
	return result, nil
}
