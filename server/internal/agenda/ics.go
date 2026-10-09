package agenda

import (
	"strings"
	"time"
)

// 一场活动在日历里占多长（日历里的事件要有结束时间）。
var eventLength = map[string]time.Duration{"内战": 3 * time.Hour, "赛事": 4 * time.Hour}

func escape(text string) string {
	r := strings.NewReplacer(`\`, `\\`, ";", `\;`, ",", `\,`, "\n", `\n`)
	return r.Replace(text)
}

// fold 是 RFC 5545 3.1：一行超过 75 个字节就折到下一行，下一行以空格开头，不拆开一个字。
func fold(line string) string {
	var parts []string
	current, size := "", 0
	for _, ch := range line {
		w := len(string(ch))
		if size+w > 75 {
			parts = append(parts, current)
			current, size = " ", 1
		}
		current += string(ch)
		size += w
	}
	parts = append(parts, current)
	return strings.Join(parts, "\r\n")
}

func stamp(t time.Time) string { return t.UTC().Format("20060102T150405Z") }

// ICS 把一个人的安排写成 iCalendar。没有开始时间的事排不进日历，跳过。
func (s *Service) ICS(nickname string, items []Item, now time.Time) string {
	host := s.siteURL
	if i := strings.Index(host, "://"); i >= 0 {
		host = host[i+3:]
	}
	host = strings.Trim(host, "/")
	if host == "" {
		host = "sjtu-ow"
	}
	lines := []string{
		"BEGIN:VCALENDAR",
		"VERSION:2.0",
		"PRODID:-//SJTU-OW//sjtu-ow//ZH",
		"CALSCALE:GREGORIAN",
		"X-WR-CALNAME:" + escape(nickname+" 的社团安排"),
		"X-WR-TIMEZONE:Asia/Shanghai",
	}
	for _, it := range items {
		if it.When == nil {
			continue
		}
		length := eventLength[it.Kind]
		if length == 0 {
			length = 3 * time.Hour
		}
		url := s.siteURL + it.URL
		lines = append(lines,
			"BEGIN:VEVENT",
			"UID:"+escape(strings.ReplaceAll(strings.Trim(it.URL, "/"), "/", "-"))+"@"+host,
			"DTSTAMP:"+stamp(now),
			"DTSTART:"+stamp(*it.When),
			"DTEND:"+stamp(it.When.Add(length)),
			"SUMMARY:"+escape(it.Kind+"："+it.Title),
			"DESCRIPTION:"+escape(it.Note+"\n"+url),
			"URL:"+url,
			"END:VEVENT",
		)
	}
	lines = append(lines, "END:VCALENDAR")
	for i, l := range lines {
		lines[i] = fold(l)
	}
	return strings.Join(lines, "\r\n") + "\r\n"
}
