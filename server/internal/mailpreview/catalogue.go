// Package mailpreview renders fictional specimens through the production letter.
// It neither opens a business database nor calls an SMTP/outbox interface.
package mailpreview

import (
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

const sampleRoot = "https://example.invalid"
const teamName = "交大龙骑"
const tournamentName = "2026 秋季校内杯"
const scrimName = "国庆特别场 · 6v6 怀旧"
const memberName = "小天使"
const captainName = "七月流火"

var specimenDate = time.Date(2026, time.October, 3, 6, 20, 0, 0, time.UTC)

type Sample struct {
	Key    string
	Group  string
	Title  string
	To     string
	Name   string
	Source string
	Letter mail.Letter
}

func sampleURL(path string) string { return sampleRoot + path }
func specimen(key, group, title, to, name, source string, letter mail.Letter) Sample {
	return Sample{Key: key, Group: group, Title: title, To: to, Name: name, Source: source, Letter: letter}
}
func repeat(letter mail.Letter, noun string, before string) mail.Letter {
	letter.Notice = "关于" + noun + "「" + tournamentName + "」，之前已经发过 " + before + " 次邮件，这次可能有修改，请以这封为准。"
	return letter
}
func teamReason() string {
	return "你收到这封邮件，是因为你是战队「" + teamName + "」的队长。"
}
func applicationReason() string {
	return "你收到这封邮件，是因为你申请过加入「" + teamName + "」。"
}
func registrationReason() string {
	return "你收到这封邮件，是因为你报名了「" + tournamentName + "」。"
}
func activityReason() string {
	return "你收到这封邮件，是因为你在社区开着「活动通知」。"
}
func scrimReason() string {
	return "你收到这封邮件，是因为你报名了内战「" + scrimName + "」。"
}
func registrationFacts() [][2]string {
	return [][2]string{{"赛事", tournamentName}, {"队伍", teamName}}
}

// Catalogue follows core/email_samples.py's keys. Additional real Go variants
// are explicit entries, so updating a subject never silently invents a type.
func Catalogue() []Sample {
	result := []Sample{}
	result = append(result, accountSamples()...)
	result = append(result, teamSamples()...)
	result = append(result, tournamentSamples()...)
	result = append(result, scrimSamples()...)
	result = append(result, announcementSamples()...)
	result = append(result, moderationSamples()...)
	result = append(result, specimen("smtp", "后台", "SMTP 测试邮件", "操作的管理员", "管理员", "server/internal/settings/settings.go", mail.Letter{
		Subject: "SMTP 测试邮件", Lead: "这是一封来自网站后台的测试邮件。你能读到它，说明 SMTP 配置可用。",
		Paragraphs: []string{"正式的通知邮件也是这个样子：先说结论，再列要点，最后落款。"},
	}))
	return result
}

func Find(key string) (Sample, bool) {
	for _, sample := range Catalogue() {
		if sample.Key == key {
			return sample, true
		}
	}
	return Sample{}, false
}

func plainSubject(letter mail.Letter) string { return strings.TrimSpace(letter.Subject) }
