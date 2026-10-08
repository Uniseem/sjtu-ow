package auth

import (
	"bytes"
	"compress/gzip"
	"io"
	"strings"
	"sync"
	"unicode"

	_ "embed"
)

//go:embed common-passwords.txt.gz
var commonPasswordsGZ []byte

// Django 的 UserAttributeSimilarityValidator 默认阈值。
const maxSimilarity = 0.7

var (
	commonOnce sync.Once
	commonSet  map[string]struct{}
)

// Validate 按 Django 那四条校验密码，返回要给用户看的说明（空切片表示通过）。
// 邮箱和昵称用来做「太像」的比较；空着就跳过那一项。
func Validate(password, email, nickname string) []string {
	var msgs []string
	if len([]rune(password)) < 8 {
		msgs = append(msgs, "密码太短。密码必须包含至少 8 个字符。")
	}
	if password != "" && allDigits(password) {
		msgs = append(msgs, "密码完全是数字。")
	}
	if isCommon(strings.ToLower(strings.TrimSpace(password))) {
		msgs = append(msgs, "密码过于常见。")
	}
	if tooSimilar(password, email) {
		msgs = append(msgs, "密码与邮箱太相似。")
	}
	if tooSimilar(password, nickname) {
		msgs = append(msgs, "密码与昵称太相似。")
	}
	return msgs
}

func allDigits(s string) bool {
	for _, r := range s {
		if !unicode.IsDigit(r) {
			return false
		}
	}
	return true
}

func isCommon(password string) bool {
	commonOnce.Do(func() {
		commonSet = map[string]struct{}{}
		r, err := gzip.NewReader(bytes.NewReader(commonPasswordsGZ))
		if err != nil {
			panic("常见密码表读不出来：" + err.Error())
		}
		body, err := io.ReadAll(r)
		if err != nil {
			panic("常见密码表读不出来：" + err.Error())
		}
		for _, line := range strings.Split(string(body), "\n") {
			line = strings.TrimSpace(line)
			if line != "" {
				commonSet[line] = struct{}{}
			}
		}
	})
	_, ok := commonSet[password]
	return ok
}

// tooSimilar 是 Django 的 quick_ratio：把属性按非单词字符切开，任一段和密码的
// 字符多重集重合度 ≥ 0.7 就算太像。比较不区分大小写。
func tooSimilar(password, value string) bool {
	if value == "" || password == "" {
		return false
	}
	pwd := []rune(strings.ToLower(password))
	value = strings.ToLower(value)
	parts := append(splitWords(value), value)
	for _, part := range parts {
		if part == "" {
			continue
		}
		if quickRatio(pwd, []rune(part)) >= maxSimilarity {
			return true
		}
	}
	return false
}

func splitWords(s string) []string {
	return strings.FieldsFunc(s, func(r rune) bool {
		return r != '_' && !unicode.IsLetter(r) && !unicode.IsDigit(r)
	})
}

func quickRatio(a, b []rune) float64 {
	count := make(map[rune]int, len(b))
	for _, r := range b {
		count[r]++
	}
	matches := 0
	for _, r := range a {
		if count[r] > 0 {
			count[r]--
			matches++
		}
	}
	length := len(a) + len(b)
	if length == 0 {
		return 1
	}
	return 2 * float64(matches) / float64(length)
}
