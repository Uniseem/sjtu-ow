// sjtuow 是新栈唯一的二进制（12 号文档 5.1）。
package main

import (
	"context"
	"database/sql"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"syscall"

	// 显示和定时用 Asia/Shanghai；不依赖镜像里的时区文件（12 号文档 5.6）
	_ "time/tzdata"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/apigen"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/config"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/idempotency"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/jobs"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
	"github.com/Uniseem/sjtu-ow/server/internal/serve"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	var err error
	switch os.Args[1] {
	case "migrate":
		err = runMigrate()
	case "serve":
		err = runServe()
	case "worker":
		err = runWorker()
	case "apigen":
		err = runApigen()
	case "import":
		err = runImport()
	case "verify-email":
		err = runVerifyEmail()
	default:
		usage()
		os.Exit(2)
	}
	if err != nil {
		fatal(err)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "用法：sjtuow <migrate|serve|worker|apigen|import|verify-email>（后续里程碑会加 reconcile、backup 等）")
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "sjtuow:", err)
	os.Exit(1)
}

func runMigrate() error {
	cfg, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()
	v, err := db.Version(context.Background(), d)
	if err != nil {
		return err
	}
	fmt.Printf("迁移完成：%s 现在在版本 %d\n", filepath.Join(cfg.DataDir, "sjtuow.sqlite3"), v)
	return nil
}

func buildRegistry(acctSvc *accounts.Service) *api.Registry {
	reg := &api.Registry{}
	acctModule := accounts.NewModule(acctSvc)
	acctModule.Routes(reg)
	return reg
}

func runServe() error {
	cfg, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()
	acctSvc := accounts.NewService(d, nil, cfg.SiteURL, auth.NewStore(d, nil), ratelimit.NewEnforcer(d, nil))
	reg := buildRegistry(acctSvc)
	h := serve.Handler(d, cfg.DataDir, reg, viewerOf(d, acctSvc),
		api.WithTrustedProxies(cfg.TrustedProxies),
		api.WithLimiter(ratelimit.NewEnforcer(d, nil)),
		api.WithIdempotency(idempotency.NewStore(d, nil)),
		api.WithSecureCookies(cfg.Prod),
	)
	addr := os.Getenv("SJTUOW_HTTP_ADDR")
	if addr == "" {
		addr = ":8080"
	}
	fmt.Printf("监听 %s\n", addr)
	return http.ListenAndServe(addr, h)
}

func runWorker() error {
	cfg, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()
	w := jobs.New(d, nil)
	w.Handle(outbox.KindLetter, outbox.Handler(smtpFrom(cfg)))
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return w.Run(ctx, 0)
}

func runApigen() error {
	dir := os.Getenv("SJTUOW_APIGEN_DIR")
	if dir == "" {
		dir = filepath.Join("..", "web", "packages", "api", "src", "gen")
	}
	acctSvc := accounts.NewService(nil, nil, "", nil, nil)
	reg := buildRegistry(acctSvc)
	return apigen.Write(dir, reg)
}

func openDB() (*config.Config, *db.DB, error) {
	cfg, err := config.FromEnv()
	if err != nil {
		return nil, nil, err
	}
	if err := os.MkdirAll(cfg.DataDir, 0o755); err != nil {
		return nil, nil, fmt.Errorf("建数据目录 %s：%w", cfg.DataDir, err)
	}
	path := filepath.Join(cfg.DataDir, "sjtuow.sqlite3")
	opts := []db.Option{db.DefaultDev()}
	if cfg.Prod {
		opts = []db.Option{db.DefaultProd()}
	}
	d, err := db.Open(path, opts...)
	if err != nil {
		return nil, nil, err
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		d.Close()
		return nil, nil, err
	}
	return cfg, d, nil
}

func viewerOf(d *db.DB, acctSvc *accounts.Service) api.ViewerResolver {
	store := auth.NewStore(d, nil)
	return func(r *http.Request) *app.Viewer {
		c, err := r.Cookie(auth.CookieName)
		if err != nil {
			return nil
		}
		s, err := store.Lookup(r.Context(), c.Value)
		if err != nil || s == nil {
			return nil
		}
		v, err := acctSvc.BuildViewer(r.Context(), s.UserID)
		if err != nil {
			return nil
		}
		return v
	}
}

func smtpFrom(cfg *config.Config) mail.SMTP {
	port := 587
	if raw := os.Getenv("SMTP_PORT"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil {
			port = n
		}
	}
	return mail.SMTP{
		Host:      os.Getenv("SMTP_HOST"),
		Port:      port,
		Username:  os.Getenv("SMTP_USER"),
		Password:  os.Getenv("SMTP_PASSWORD"),
		FromName:  "SJTU-OW",
		FromAddr:  os.Getenv("SMTP_FROM"),
		Security:  os.Getenv("SMTP_SECURITY"),
		Prefix:    mail.DefaultPrefix,
		Allowlist: cfg.EmailAllowlist,
	}
}

func runImport() error {
	if len(os.Args) < 3 {
		return fmt.Errorf("用法：sjtuow import <legacy-sqlite-db-path>")
	}
	legacyPath := os.Args[2]
	legacyDB, err := sql.Open("sqlite", fmt.Sprintf("file:%s?mode=ro", legacyPath))
	if err != nil {
		return fmt.Errorf("打开旧库失败: %w", err)
	}
	defer legacyDB.Close()

	_, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()

	ctx := context.Background()
	if err := accounts.ImportLegacyAccounts(ctx, d, legacyDB); err != nil {
		return fmt.Errorf("导入账号失败: %w", err)
	}
	fmt.Println("账号域数据导入成功。")
	return nil
}

func runVerifyEmail() error {
	if len(os.Args) < 3 {
		return fmt.Errorf("用法：sjtuow verify-email <email>")
	}
	email := os.Args[2]
	cfg, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()
	acctSvc := accounts.NewService(d, nil, cfg.SiteURL, nil, nil)
	if err := acctSvc.VerifyUserEmailDirectly(context.Background(), email); err != nil {
		return err
	}
	fmt.Printf("用户 %s 邮箱已标记为已验证。\n", email)
	return nil
}
