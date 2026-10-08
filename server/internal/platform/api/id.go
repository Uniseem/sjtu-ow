package api

import (
	"regexp"
	"strconv"
)

// ID 是路径里的编号：一律按 [0-9]{1,18} 解析（照搬现行站 <id:pk> 和 as_id()，
// 12 号文档 5.3；最多 18 位，乱填直接 404，不让它变成数据库错误）。
type ID int64

var idPattern = regexp.MustCompile(`^[0-9]{1,18}$`)

// ParseID 解析一个路径参数；不合法返回 false。
func ParseID(s string) (ID, bool) {
	if !idPattern.MatchString(s) {
		return 0, false
	}
	n, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	return ID(n), true
}
