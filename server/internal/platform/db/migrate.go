package db

import (
	"context"
	"fmt"
	"io/fs"

	"github.com/pressly/goose/v3"

	dbmigrations "github.com/Uniseem/sjtu-ow/server/db"
)

// Migrate 把嵌在二进制里的迁移应用到最新。跑过一遍再跑是无操作。
// 用写池（goose 要建自己的版本表）；这是管理操作，不走 WriteTx。
func Migrate(ctx context.Context, d *DB) error {
	p, err := newProvider(d)
	if err != nil {
		return err
	}
	if _, err := p.Up(ctx); err != nil {
		return fmt.Errorf("应用迁移：%w", err)
	}
	return nil
}

// Version 返回当前迁移版本（还没迁移过就是 0）。
func Version(ctx context.Context, d *DB) (int64, error) {
	p, err := newProvider(d)
	if err != nil {
		return 0, err
	}
	v, err := p.GetDBVersion(ctx)
	if err != nil {
		return 0, fmt.Errorf("读迁移版本：%w", err)
	}
	return v, nil
}

func newProvider(d *DB) (*goose.Provider, error) {
	fsys, err := fs.Sub(dbmigrations.FS, "migrations")
	if err != nil {
		return nil, fmt.Errorf("嵌入的迁移目录：%w", err)
	}
	p, err := goose.NewProvider(goose.DialectSQLite3, d.write, fsys)
	if err != nil {
		return nil, fmt.Errorf("建迁移器：%w", err)
	}
	return p, nil
}
