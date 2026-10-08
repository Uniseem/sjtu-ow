// Package dbmigrations 收着 goose 的迁移文件，嵌进二进制（12 号文档 5.1）。
// 加迁移就是往 migrations/ 放一个新的 SQL 文件，不用改这个包。
package dbmigrations

import "embed"

//go:embed migrations/*.sql
var FS embed.FS
