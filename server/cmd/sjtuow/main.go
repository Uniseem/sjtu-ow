// sjtuow 是新栈唯一的二进制（12 号文档 5.1）。
package main

import (
	"bufio"
	"context"
	"database/sql"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	// 显示和定时用 Asia/Shanghai；不依赖镜像里的时区文件（12 号文档 5.6）
	_ "time/tzdata"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/activity"
	"github.com/Uniseem/sjtu-ow/server/internal/agenda"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/comments"
	"github.com/Uniseem/sjtu-ow/server/internal/content"
	"github.com/Uniseem/sjtu-ow/server/internal/manual"
	"github.com/Uniseem/sjtu-ow/server/internal/members"
	"github.com/Uniseem/sjtu-ow/server/internal/moderation"
	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/ops"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/apigen"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/config"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/idempotency"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/jobs"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
	"github.com/Uniseem/sjtu-ow/server/internal/scrims"
	"github.com/Uniseem/sjtu-ow/server/internal/search"
	"github.com/Uniseem/sjtu-ow/server/internal/serve"
	"github.com/Uniseem/sjtu-ow/server/internal/settings"
	"github.com/Uniseem/sjtu-ow/server/internal/teams"
	"github.com/Uniseem/sjtu-ow/server/internal/todo"
	"github.com/Uniseem/sjtu-ow/server/internal/tournaments"
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
	case "backup":
		err = runBackup()
	case "restore":
		err = runRestore()
	case "createsuperuser":
		err = runCreateSuperuser()
	case "reconcile":
		err = runReconcile()
	case "rulecheck":
		err = runRulecheck()
	case "parity":
		err = runParity()
	default:
		usage()
		os.Exit(2)
	}
	if err != nil {
		fatal(err)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "用法：sjtuow <migrate|serve|worker|apigen|import|verify-email|backup|restore|createsuperuser|reconcile|rulecheck|parity>")
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

func buildRegistry(
	acctSvc *accounts.Service,
	contentSvc *content.Service,
	commentsSvc *comments.Service,
	searchSvc *search.Service,
	mediaSvc *media.Service,
	teamsSvc *teams.Service,
	membersSvc *members.Service,
	tournamentsSvc *tournaments.Service,
	scrimsSvc *scrims.Service,
	moderationSvc *moderation.Service,
	notifySvc *notify.Service,
	agendaSvc *agenda.Service,
	settingsSvc *settings.Service,
	auditMod *audit.Module,
	activitySvc *activity.Service,
	manualMod *manual.Module,
	todoSvc *todo.Service,
) *api.Registry {
	reg := &api.Registry{}
	if acctSvc != nil {
		accounts.NewModule(acctSvc).Routes(reg)
	}
	if contentSvc != nil {
		content.NewModule(contentSvc).Routes(reg)
	}
	if commentsSvc != nil {
		comments.NewModule(commentsSvc).Routes(reg)
	}
	if searchSvc != nil {
		search.NewModule(searchSvc).Routes(reg)
	}
	if mediaSvc != nil {
		media.NewModule(mediaSvc).Routes(reg)
	}
	if teamsSvc != nil {
		teams.NewModule(teamsSvc).Routes(reg)
	}
	if membersSvc != nil {
		members.NewModule(membersSvc).Routes(reg)
	}
	if tournamentsSvc != nil {
		tournaments.NewModule(tournamentsSvc).Routes(reg)
	}
	if scrimsSvc != nil {
		scrims.NewModule(scrimsSvc).Routes(reg)
	}
	if moderationSvc != nil {
		moderation.NewModule(moderationSvc).Routes(reg)
	}
	if notifySvc != nil {
		notify.NewModule(notifySvc).Routes(reg)
	}
	if agendaSvc != nil {
		agenda.NewModule(agendaSvc).Routes(reg)
	}
	if settingsSvc != nil {
		settings.NewModule(settingsSvc).Routes(reg)
	}
	if auditMod != nil {
		auditMod.Routes(reg)
	}
	if activitySvc != nil {
		activity.NewModule(activitySvc).Routes(reg)
	}
	if manualMod != nil {
		manualMod.Routes(reg)
	}
	if todoSvc != nil {
		todo.NewModule(todoSvc).Routes(reg)
	}
	return reg
}

func runServe() error {
	cfg, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()
	acctSvc := accounts.NewService(d, nil, cfg.SiteURL, auth.NewStore(d, nil), ratelimit.NewEnforcer(d, nil))
	contentStore := content.NewStore(d)
	contentSvc := content.NewService(contentStore, cfg.SiteURL)
	commentsStore := comments.NewStore(d)
	commentsSvc := comments.NewService(commentsStore)
	searchSvc := search.NewService(d)
	mediaSvc := media.NewService(d, cfg.DataDir, cfg.MediaDir)
	acctSvc.SetMedia(mediaSvc)
	teamsSvc := teams.NewService(d, cfg.SiteURL, ratelimit.NewEnforcer(d, nil), mediaSvc)
	membersSvc := members.NewService(d)
	tournamentsSvc := newTournaments(d, cfg.SiteURL, acctSvc, teamsSvc)
	scrimsSvc := newScrims(d, cfg.SiteURL, acctSvc)
	moderationSvc := moderation.NewService(d, cfg.SiteURL)
	// 各域改了内容就送审（规则 186）；开关没开或没配好时 Submit 什么都不做
	acctSvc.SetModeration(moderationSvc)
	commentsSvc.SetModeration(moderationSvc)
	contentSvc.SetModeration(moderationSvc)
	scrimsSvc.SetModeration(moderationSvc)
	teamsSvc.SetModeration(moderationSvc)
	tournamentsSvc.SetModeration(moderationSvc)
	notifySvc := newNotify(d, cfg, contentSvc, tournamentsSvc, scrimsSvc)
	agendaSvc := agenda.NewService(d, cfg.SiteURL, cfg.SigningKey)
	settingsSvc := settings.NewService(d, cfg.SiteURL, cfg.FieldEncryptionKey)
	auditMod := audit.NewModule(d)
	activitySvc := activity.NewService(d, cfg.SiteURL)
	manualMod := manual.NewModule()
	todoSvc := todo.NewService(d)

	reg := buildRegistry(acctSvc, contentSvc, commentsSvc, searchSvc, mediaSvc, teamsSvc, membersSvc, tournamentsSvc, scrimsSvc, moderationSvc, notifySvc, agendaSvc, settingsSvc, auditMod, activitySvc, manualMod, todoSvc)
	h := serve.Handler(d, cfg.DataDir, reg, viewerOf(d, acctSvc),
		api.WithTrustedProxies(cfg.TrustedProxies),
		api.WithLimiter(ratelimit.NewEnforcer(d, nil)),
		api.WithIdempotency(idempotency.NewStore(d, nil)),
		api.WithSecureCookies(cfg.Prod),
		api.WithLetters(d, cfg.SiteURL),
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
	// 每天 04:00 的夜任务：战队的申请提醒和自动关闭（规则 94、95）。后面的里程碑往里加。
	acctSvc := accounts.NewService(d, nil, cfg.SiteURL, auth.NewStore(d, nil), nil)
	teamsSvc := teams.NewService(d, cfg.SiteURL, nil, nil)
	tournamentsSvc := newTournaments(d, cfg.SiteURL, acctSvc, teamsSvc)
	contentSvc := content.NewService(content.NewStore(d), cfg.SiteURL)
	scrimsSvc := newScrims(d, cfg.SiteURL, acctSvc)
	notifySvc := newNotify(d, cfg, contentSvc, tournamentsSvc, scrimsSvc)
	w.Handle(notify.JobDeliver, notifySvc.Deliver())
	// 每 30 秒：文章定时上线和到期撤下（规则 54–57）、赛事开赛提醒（规则 138–140）。
	w.OnSchedule(jobs.SchedPublish, func(ctx context.Context, _ *db.DB, now time.Time) error {
		if err := contentSvc.CheckScheduledWorker(ctx, now); err != nil {
			return fmt.Errorf("定时发布：%w", err)
		}
		if _, err := tournamentsSvc.SendDueReminders(ctx, now); err != nil {
			return fmt.Errorf("赛事提醒：%w", err)
		}
		if err := scrimsSvc.Tick(ctx, now); err != nil {
			return fmt.Errorf("内战自动结束与提醒：%w", err)
		}
		return nil
	})
	w.OnSchedule(jobs.SchedCleanup, func(ctx context.Context, _ *db.DB, now time.Time) error {
		if _, err := teamsSvc.RemindCaptains(ctx, now); err != nil {
			return fmt.Errorf("提醒队长：%w", err)
		}
		if _, err := teamsSvc.CloseStaleApplications(ctx, now); err != nil {
			return fmt.Errorf("关闭过期申请：%w", err)
		}
		if _, err := moderation.NewService(d, cfg.SiteURL).Cleanup(ctx, now); err != nil {
			return fmt.Errorf("清理审核记录：%w", err)
		}
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			_, err := notify.CleanupHeld(txCtx, tx, now)
			return err
		}); err != nil {
			return fmt.Errorf("清理待发信：%w", err)
		}
		return nil
	})
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
	contentSvc := content.NewService(content.NewStore(nil), "")
	commentsSvc := comments.NewService(comments.NewStore(nil))
	searchSvc := search.NewService(nil)
	mediaSvc := media.NewService(nil, "", "")
	teamsSvc := teams.NewService(nil, "", nil, nil)
	membersSvc := members.NewService(nil)
	tournamentsSvc := tournaments.NewService(nil, "")
	scrimsSvc := scrims.NewService(nil, "")
	moderationSvc := moderation.NewService(nil, "")
	notifySvc := notify.NewService(nil, "", "", nil)
	agendaSvc := agenda.NewService(nil, "", "")
	settingsSvc := settings.NewService(nil, "", "")
	auditMod := audit.NewModule(nil)
	activitySvc := activity.NewService(nil, "")
	manualMod := manual.NewModule()
	todoSvc := todo.NewService(nil)
	reg := buildRegistry(acctSvc, contentSvc, commentsSvc, searchSvc, mediaSvc, teamsSvc, membersSvc, tournamentsSvc, scrimsSvc, moderationSvc, notifySvc, agendaSvc, settingsSvc, auditMod, activitySvc, manualMod, todoSvc)
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

// newNotify 造通知服务并挂上三类能被「通知全体成员」的内容。
func newNotify(d *db.DB, cfg *config.Config, contentSvc *content.Service, tournamentsSvc *tournaments.Service, scrimsSvc *scrims.Service) *notify.Service {
	ready := func() bool {
		smtp := smtpFrom(cfg)
		return smtp.Host != "" && smtp.FromAddr != ""
	}
	n := notify.NewService(d, cfg.SiteURL, cfg.SigningKey, ready)
	n.Register(contentSvc.AnnounceKind())
	n.Register(tournamentsSvc.AnnounceKind())
	n.Register(scrimsSvc.AnnounceKind())
	return n
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

	cfg, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()

	ctx := context.Background()
	if err := accounts.ImportLegacyAccounts(ctx, d, legacyDB); err != nil {
		return fmt.Errorf("导入账号失败: %w", err)
	}
	fmt.Println("账号域数据导入成功。")
	if err := content.ImportLegacyContent(ctx, d, legacyDB, cfg.SiteURL); err != nil {
		return fmt.Errorf("导入内容域失败: %w", err)
	}
	fmt.Println("内容域数据导入成功。")
	if err := teams.ImportLegacyTeams(ctx, d, legacyDB); err != nil {
		return fmt.Errorf("导入战队失败: %w", err)
	}
	fmt.Println("战队数据导入成功。")
	if err := members.ImportLegacyGroups(ctx, d, legacyDB); err != nil {
		return fmt.Errorf("导入成员分组失败: %w", err)
	}
	fmt.Println("成员分组数据导入成功。")
	if err := tournaments.ImportLegacyTournaments(ctx, d, legacyDB); err != nil {
		return fmt.Errorf("导入赛事失败: %w", err)
	}
	fmt.Println("赛事数据导入成功。")
	if err := scrims.ImportLegacyScrims(ctx, d, legacyDB); err != nil {
		return fmt.Errorf("导入内战失败: %w", err)
	}
	fmt.Println("内战数据导入成功。")
	if err := moderation.ImportLegacyModeration(ctx, d, legacyDB); err != nil {
		return fmt.Errorf("导入审核记录失败: %w", err)
	}
	fmt.Println("审核记录导入成功。")
	if err := settings.ImportLegacySettings(ctx, d, legacyDB); err != nil {
		return fmt.Errorf("导入全站设置失败: %w", err)
	}
	fmt.Println("全站设置数据导入成功。")
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

// newTournaments 造赛事服务并接上它依赖的两头：用户的 can_use（账号域）和战队的解散拦截（赛事域）。
func newTournaments(d *db.DB, siteURL string, acctSvc *accounts.Service, teamsSvc *teams.Service) *tournaments.Service {
	svc := tournaments.NewService(d, siteURL)
	svc.SetViewerBuilder(acctSvc.BuildViewer)
	teamsSvc.SetRosterGuard(rosterGuard{})
	return svc
}

// rosterGuard 把赛事域的两个查询接到战队服务的 RosterGuard 上（战队包不引用赛事包）。
type rosterGuard struct{}

func (rosterGuard) LiveRegistrations(ctx context.Context, q db.DBTX, teamID int64) ([]string, error) {
	return tournaments.LiveRegistrations(ctx, q, teamID)
}

func (rosterGuard) EntriesStillListing(ctx context.Context, q db.DBTX, teamID, userID int64) ([]teams.ListedEntry, error) {
	rows, err := tournaments.EntriesStillListing(ctx, q, teamID, userID)
	if err != nil {
		return nil, err
	}
	out := make([]teams.ListedEntry, 0, len(rows))
	for _, r := range rows {
		out = append(out, teams.ListedEntry{Title: r.Title, ClosesAt: r.ClosesAt, DetailURL: r.DetailURL})
	}
	return out, nil
}

// newScrims 造内战服务并接上用户的 can_use（账号域）。
func newScrims(d *db.DB, siteURL string, acctSvc *accounts.Service) *scrims.Service {
	svc := scrims.NewService(d, siteURL)
	svc.SetViewerBuilder(acctSvc.BuildViewer)
	return svc
}

func runBackup() error {
	cfg, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()

	fs := flag.NewFlagSet("backup", flag.ContinueOnError)
	outPath := fs.String("out", "", "输出备份文件路径（默认为 data/backups/sjtuow-<timestamp>.tar.gz，- 为标准输出）")
	if err := fs.Parse(os.Args[2:]); err != nil {
		return err
	}

	targetOut := *outPath
	if targetOut == "" {
		targetOut = filepath.Join(cfg.DataDir, "backups", fmt.Sprintf("sjtuow-%s.tar.gz", time.Now().Format("20060102-150405")))
	}

	manifest, err := ops.Backup(context.Background(), d, ops.BackupOptions{
		DataDir:  cfg.DataDir,
		MediaDir: cfg.MediaDir,
		OutPath:  targetOut,
	})
	if err != nil {
		return err
	}
	if targetOut != "-" {
		fmt.Printf("备份完成：%s (大小: %d 字节, 媒体文件: %d 个, 库校验和: %s)\n",
			targetOut, manifest.DatabaseSize, manifest.MediaFilesCount, manifest.DatabaseChecksum)
	}
	return nil
}

func runRestore() error {
	cfg, err := config.FromEnv()
	if err != nil {
		return err
	}

	fs := flag.NewFlagSet("restore", flag.ContinueOnError)
	yes := fs.Bool("yes", false, "确认真正恢复替换现有数据（默认只演练校验）")
	archive := fs.String("archive", "", "备份归档文件路径")
	if err := fs.Parse(os.Args[2:]); err != nil {
		return err
	}

	archivePath := *archive
	if archivePath == "" && len(fs.Args()) > 0 {
		archivePath = fs.Arg(0)
	}
	if archivePath == "" {
		return fmt.Errorf("用法：sjtuow restore <archive.tar.gz> [--yes]")
	}

	res, err := ops.Restore(context.Background(), ops.RestoreOptions{
		ArchivePath: archivePath,
		DataDir:     cfg.DataDir,
		MediaDir:    cfg.MediaDir,
		Apply:       *yes,
	})
	if err != nil {
		return err
	}

	if res.DryRun {
		fmt.Printf("演练成功：归档完整有效 (数据库校验和: %s, 媒体文件: %d 个)。未执行任何替换。\n如需真正还原，请追加 --yes 参数。\n",
			res.Manifest.DatabaseChecksum, res.Manifest.MediaFilesCount)
	} else {
		fmt.Printf("恢复完成：已还原至 %s (数据库校验和: %s, 恢复文件: %d 个)\n",
			cfg.DataDir, res.Manifest.DatabaseChecksum, res.FilesRestored)
	}
	return nil
}

func runCreateSuperuser() error {
	_, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()

	fs := flag.NewFlagSet("createsuperuser", flag.ContinueOnError)
	email := fs.String("email", "", "超级管理员邮箱")
	nickname := fs.String("nickname", "", "昵称（默认：超级管理员）")
	password := fs.String("password", "", "登录密码")
	isSJTU := fs.Bool("is-sjtu", true, "是否交大校内人员")
	if err := fs.Parse(os.Args[2:]); err != nil {
		return err
	}

	targetEmail := strings.TrimSpace(*email)
	targetNickname := strings.TrimSpace(*nickname)
	targetPassword := strings.TrimSpace(*password)

	reader := bufio.NewReader(os.Stdin)
	if targetEmail == "" {
		fmt.Print("邮箱: ")
		line, _ := reader.ReadString('\n')
		targetEmail = strings.TrimSpace(line)
	}
	if targetNickname == "" {
		fmt.Print("昵称 (默认: 超级管理员): ")
		line, _ := reader.ReadString('\n')
		targetNickname = strings.TrimSpace(line)
		if targetNickname == "" {
			targetNickname = "超级管理员"
		}
	}
	if targetPassword == "" {
		fmt.Print("密码: ")
		line, _ := reader.ReadString('\n')
		targetPassword = strings.TrimSpace(line)
	}

	err = ops.CreateSuperuser(context.Background(), d, ops.SuperuserOptions{
		Email:    targetEmail,
		Nickname: targetNickname,
		Password: targetPassword,
		IsSJTU:   *isSJTU,
	})
	if err != nil {
		return err
	}
	fmt.Printf("超级管理员 %s 创建成功。\n", targetEmail)
	return nil
}

func runReconcile() error {
	_, d, err := openDB()
	if err != nil {
		return err
	}
	defer d.Close()

	legacyPath := ""
	if len(os.Args) >= 3 {
		legacyPath = os.Args[2]
	}

	res, err := ops.Reconcile(context.Background(), d, legacyPath)
	if err != nil {
		return err
	}
	fmt.Print(res.FormatReport())
	if !res.IntegrityOK || !res.FKCheckOK {
		return fmt.Errorf("数据库一致性检查未完全通过")
	}
	return nil
}

func runRulecheck() error {
	fs := flag.NewFlagSet("rulecheck", flag.ContinueOnError)
	docPath := fs.String("doc", "", "业务规则契约文档路径（默认查找 docs/rewrite-research/05-business-rules.md）")
	repoDir := fs.String("repo", "", "代码仓库根目录（默认向上查找含有 AGENTS.md 的目录）")
	if err := fs.Parse(os.Args[2:]); err != nil {
		return err
	}

	targetRepo := *repoDir
	if targetRepo == "" {
		targetRepo = findRepoRoot()
	}

	targetDoc := *docPath
	if targetDoc == "" {
		targetDoc = filepath.Join(targetRepo, "docs/rewrite-research/05-business-rules.md")
	}

	res, err := ops.RuleCheck(targetDoc, targetRepo)
	if err != nil {
		return err
	}
	fmt.Print(res.FormatReport())
	return nil
}

func runParity() error {
	fs := flag.NewFlagSet("parity", flag.ContinueOnError)
	newURL := fs.String("new-url", "", "新站前端或后端地址（例如 http://127.0.0.1:4000）")
	legacyURL := fs.String("legacy-url", "", "旧站访问地址（例如 http://127.0.0.1:22887）")
	mediaDir := fs.String("media-dir", "", "本地 media 目录路径（例如 /srv/sjtu-ow/data/media）")
	signingKey := fs.String("signing-key", "", "站点签名密钥（默认使用环境变量 SIGNING_KEY）")
	jsonOutput := fs.Bool("json", false, "以 JSON 格式输出审计结果")
	checkRoutes := fs.Bool("routes", false, "执行端点路由对拍")
	checkMedia := fs.Bool("media", false, "执行图片媒体可达性核对")

	if err := fs.Parse(os.Args[2:]); err != nil {
		return err
	}

	key := *signingKey
	if key == "" {
		key = os.Getenv("SIGNING_KEY")
	}

	var d *db.DB
	if cfg, dbConn, err := openDB(); err == nil {
		d = dbConn
		defer d.Close()
		if key == "" {
			key = cfg.SigningKey
		}
		if *mediaDir == "" {
			*mediaDir = filepath.Join(cfg.DataDir, "media")
		}
	}

	opts := ops.ParityOptions{
		NewBaseURL:      *newURL,
		LegacyBaseURL:   *legacyURL,
		MediaDir:        *mediaDir,
		SigningKey:      key,
		CheckRoutes:     *checkRoutes || *newURL != "",
		CheckMedia:      *checkMedia || *mediaDir != "",
		CheckSignatures: true,
		CheckPasswords:  true,
		CheckArticles:   true,
	}

	checker := ops.NewParityChecker(opts, d)
	res, err := checker.Run(context.Background())
	if err != nil {
		return err
	}

	if *jsonOutput {
		jsonStr, err := res.ToJSON()
		if err != nil {
			return err
		}
		fmt.Println(jsonStr)
	} else {
		fmt.Print(res.FormatReport())
	}

	if !res.OverallOK {
		return fmt.Errorf("新旧对拍与兼容性核验未完全通过")
	}
	return nil
}

func findRepoRoot() string {
	dir, err := os.Getwd()
	if err != nil {
		return "."
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, "AGENTS.md")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return "."
		}
		dir = parent
	}
}
