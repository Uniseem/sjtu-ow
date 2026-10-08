// sjtuow 是新栈唯一的二进制（12 号文档 5.1）。222 轮只有 migrate 真实现；
// serve 和 worker 在 M1 后续轮次接上，现在先过一遍配置再明确说没实现，
// 这样「缺必填环境变量拒绝启动」从第一天就是所有子命令的共同行为。
package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	// 显示和定时用 Asia/Shanghai；不依赖镜像里的时区文件（12 号文档 5.6）
	_ "time/tzdata"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/config"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "migrate":
		if err := runMigrate(); err != nil {
			fatal(err)
		}
	case "serve", "worker":
		if _, err := config.FromEnv(); err != nil {
			fatal(err)
		}
		fatal(fmt.Errorf("%s 还没实现（M1 后续轮次）", os.Args[1]))
	default:
		usage()
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "用法：sjtuow <migrate|serve|worker>（后续里程碑会加 import、reconcile、backup 等）")
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "sjtuow:", err)
	os.Exit(1)
}

func runMigrate() error {
	cfg, err := config.FromEnv()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(cfg.DataDir, 0o755); err != nil {
		return fmt.Errorf("建数据目录 %s：%w", cfg.DataDir, err)
	}
	path := filepath.Join(cfg.DataDir, "sjtuow.sqlite3")
	opts := []db.Option{db.DefaultDev()}
	if cfg.Prod {
		opts = []db.Option{db.DefaultProd()}
	}
	d, err := db.Open(path, opts...)
	if err != nil {
		return err
	}
	defer d.Close()
	ctx := context.Background()
	if err := db.Migrate(ctx, d); err != nil {
		return err
	}
	v, err := db.Version(ctx, d)
	if err != nil {
		return err
	}
	fmt.Printf("迁移完成：%s 现在在版本 %d\n", path, v)
	return nil
}
