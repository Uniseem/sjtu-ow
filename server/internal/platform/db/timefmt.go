package db

import "time"

// 库里的时间一律 UTC 文本 YYYY-MM-DDTHH:MM:SS.ffffffZ（12 号文档 5.6）：
// 字典序和时间序一致，命令行里也看得懂。显示和定时另显式转 Asia/Shanghai。
const utcLayout = "2006-01-02T15:04:05.000000"

// FormatUTC 把时间转成库里的 UTC 文本（微秒六位，结尾字面 Z）。
func FormatUTC(t time.Time) string {
	return t.UTC().Format(utcLayout) + "Z"
}

// ParseUTC 解析库里的时间文本。别的合理写法（别的时区偏移、没有微秒）也认，
// 因为导入旧库时会遇到。
func ParseUTC(s string) (time.Time, error) {
	for _, layout := range []string{utcLayout + "Z07:00", utcLayout, "2006-01-02T15:04:05Z07:00"} {
		if t, err := time.Parse(layout, s); err == nil {
			return t.UTC(), nil
		}
	}
	return time.Time{}, errParseUTC{s}
}

type errParseUTC struct{ s string }

func (e errParseUTC) Error() string { return "不是库里存的时间格式：" + e.s }
