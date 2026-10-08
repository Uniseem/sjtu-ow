package db

import (
	"context"
	"database/sql"
	"sync/atomic"
)

// DBTX 是 sqlc 生成代码认的那个接口（Exec / Query / QueryRow 的 Context 版）。
// 手写的查询也走它，查询预算测试才能数到。
type DBTX interface {
	ExecContext(context.Context, string, ...any) (sql.Result, error)
	QueryContext(context.Context, string, ...any) (*sql.Rows, error)
	QueryRowContext(context.Context, string, ...any) *sql.Row
}

// Counter 数经过它的 SQL 语句条数。查询预算测试（12 号文档 5.3 的 api.Budget）
// 在跑接口前后各读一次，差值就是这一趟的查询数。
type Counter struct{ n atomic.Int64 }

// Add 记一条。
func (c *Counter) Add() { c.n.Add(1) }

// Count 返回至今数到的语句数。
func (c *Counter) Count() int64 { return c.n.Load() }

// counted 把每一趟语句记到 Counter 上。
type counted struct {
	inner DBTX
	c     *Counter
}

// Counted 返回一个把语句记到 c 上的包装。查询要被预算测试数到，就得经过它。
func (c *Counter) Counted(inner DBTX) DBTX { return counted{inner: inner, c: c} }

func (w counted) ExecContext(ctx context.Context, q string, args ...any) (sql.Result, error) {
	w.c.Add()
	return w.inner.ExecContext(ctx, q, args...)
}

func (w counted) QueryContext(ctx context.Context, q string, args ...any) (*sql.Rows, error) {
	w.c.Add()
	return w.inner.QueryContext(ctx, q, args...)
}

func (w counted) QueryRowContext(ctx context.Context, q string, args ...any) *sql.Row {
	w.c.Add()
	return w.inner.QueryRowContext(ctx, q, args...)
}
