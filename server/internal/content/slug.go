package content

import (
	"context"
	"fmt"
	"regexp"
	"strings"
	"unicode"
)

// ReservedSlugs 是不能作为文章/页面 slug 的系统保留词（规则 59）。
var ReservedSlugs = map[string]struct{}{
	"admin":       {},
	"wagtail":     {},
	"accounts":    {},
	"comments":    {},
	"documents":   {},
	"me":          {},
	"api":         {},
	"auth":        {},
	"scrims":      {},
	"tournaments": {},
	"teams":       {},
	"members":     {},
	"news":        {},
	"search":      {},
	"static":      {},
	"media":       {},
	"sitemap.xml": {},
	"robots.txt":  {},
}

var nonSlugChars = regexp.MustCompile(`[^\p{L}\p{N}\-_]+`)

// Slugify 将标题转换为 URL 友好的 unicode slug（规则 58–59）。
// 截断到 60 字符；若为空则返回 "article"；若为保留词则追加 "-article"。
func Slugify(title string) string {
	slug := strings.TrimSpace(strings.ToLower(title))
	slug = nonSlugChars.ReplaceAllString(slug, "-")
	slug = strings.Trim(slug, "-_")

	runes := []rune(slug)
	if len(runes) > 60 {
		runes = runes[:60]
		slug = strings.Trim(string(runes), "-_")
	}

	if slug == "" {
		slug = "article"
	}

	// 检查保留词
	if _, ok := ReservedSlugs[slug]; ok {
		slug = slug + "-article"
	}

	return slug
}

// ResolveUniqueSlug 确保 slug 在指定页面类型下全局唯一。若冲突则追加 -2, -3...
func (s *Store) ResolveUniqueSlug(ctx context.Context, kind, baseSlug string, pageID int64) (string, error) {
	candidate := baseSlug
	if _, ok := ReservedSlugs[candidate]; ok {
		candidate = candidate + "-article"
	}

	for i := 1; i <= 1000; i++ {
		available, err := s.CheckSlugAvailable(ctx, kind, candidate, pageID)
		if err != nil {
			return "", err
		}
		if available {
			return candidate, nil
		}
		candidate = fmt.Sprintf("%s-%d", baseSlug, i+1)
	}

	return "", fmt.Errorf("无法为 %q 生成唯一的 slug", baseSlug)
}

// IsSafeRune 报字符是否合法用于 slug。
func IsSafeRune(r rune) bool {
	return unicode.IsLetter(r) || unicode.IsDigit(r) || r == '-' || r == '_'
}
