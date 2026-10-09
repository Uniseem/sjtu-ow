package ops

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	_ "modernc.org/sqlite"
)

func setupTestDB(t *testing.T) (*db.DB, string) {
	t.Helper()
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "sjtuow.sqlite3")

	d, err := db.Open(dbPath, db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("初始化测试数据库失败: %v", err)
	}
	t.Cleanup(func() { d.Close() })

	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatalf("数据库迁移失败: %v", err)
	}
	return d, dir
}

func TestBackupAndRestore(t *testing.T) {
	ctx := context.Background()
	d, srcDir := setupTestDB(t)

	// 准备媒体与母版图片测试文件
	originalsDir := filepath.Join(srcDir, "originals")
	mediaDir := filepath.Join(srcDir, "media")
	_ = os.MkdirAll(originalsDir, 0755)
	_ = os.MkdirAll(mediaDir, 0755)

	if err := os.WriteFile(filepath.Join(originalsDir, "1.webp"), []byte("dummy-original-1"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(mediaDir, "thumb.webp"), []byte("dummy-thumb"), 0644); err != nil {
		t.Fatal(err)
	}

	// 插入测试用户
	err := CreateSuperuser(ctx, d, SuperuserOptions{
		Email:    "Admin@SJTU.edu.cn",
		Nickname: "测试站长",
		Password: "Correct-Horse-Battery-Staple-2026!",
		IsSJTU:   true,
	})
	if err != nil {
		t.Fatalf("创建初始超管失败: %v", err)
	}

	backupTar := filepath.Join(t.TempDir(), "backup.tar.gz")

	// 1. 执行备份
	manifest, err := Backup(ctx, d, BackupOptions{
		DataDir:  srcDir,
		MediaDir: mediaDir,
		OutPath:  backupTar,
	})
	if err != nil {
		t.Fatalf("备份失败: %v", err)
	}
	if manifest.MediaFilesCount != 2 {
		t.Errorf("预期媒体文件 2 个，实际 %d", manifest.MediaFilesCount)
	}
	if manifest.DatabaseChecksum == "" {
		t.Errorf("manifest 数据库校验和为空")
	}

	// 2. 演练恢复 (Dry Run)
	restoreTargetDir := t.TempDir()
	dryRunRes, err := Restore(ctx, RestoreOptions{
		ArchivePath: backupTar,
		DataDir:     restoreTargetDir,
		Apply:       false,
	})
	if err != nil {
		t.Fatalf("演练恢复失败: %v", err)
	}
	if !dryRunRes.DryRun || !dryRunRes.IntegrityOK {
		t.Errorf("演练结果异常: %+v", dryRunRes)
	}
	// 演练不应在目标目录生成实际数据库
	if _, err := os.Stat(filepath.Join(restoreTargetDir, "sjtuow.sqlite3")); !os.IsNotExist(err) {
		t.Errorf("演练模式下不应生成实际目标数据库")
	}

	// 3. 真正恢复 (Apply = true)
	applyRes, err := Restore(ctx, RestoreOptions{
		ArchivePath: backupTar,
		DataDir:     restoreTargetDir,
		Apply:       true,
	})
	if err != nil {
		t.Fatalf("真实恢复失败: %v", err)
	}
	if applyRes.DryRun || !applyRes.IntegrityOK {
		t.Errorf("恢复结果异常: %+v", applyRes)
	}

	// 验证恢复后的数据库和文件
	restoredDBPath := filepath.Join(restoreTargetDir, "sjtuow.sqlite3")
	if _, err := os.Stat(restoredDBPath); err != nil {
		t.Fatalf("恢复后数据库文件不存在: %v", err)
	}

	restoredConn, err := sql.Open("sqlite", fmt.Sprintf("file:%s?mode=ro", restoredDBPath))
	if err != nil {
		t.Fatalf("打开恢复后数据库失败: %v", err)
	}
	defer restoredConn.Close()

	var count int
	if err := restoredConn.QueryRow("SELECT count(*) FROM users WHERE email_norm = 'admin@sjtu.edu.cn'").Scan(&count); err != nil || count != 1 {
		t.Errorf("恢复后未找到对应超管记录: %v (count=%d)", err, count)
	}

	origContent, err := os.ReadFile(filepath.Join(restoreTargetDir, "originals", "1.webp"))
	if err != nil || string(origContent) != "dummy-original-1" {
		t.Errorf("恢复后 originals 内容不匹配: %s", string(origContent))
	}
}

func TestCreateSuperuser(t *testing.T) {
	ctx := context.Background()
	d, _ := setupTestDB(t)

	// 弱密码拦截测试
	err := CreateSuperuser(ctx, d, SuperuserOptions{
		Email:    "weak@example.com",
		Nickname: "弱密码管理员",
		Password: "123",
	})
	if err == nil {
		t.Errorf("弱密码应被拦截")
	}

	// 正常创建
	err = CreateSuperuser(ctx, d, SuperuserOptions{
		Email:    "Super@Example.com",
		Nickname: "大管家",
		Password: "Valid-Secure-Password-987!",
		IsSJTU:   true,
	})
	if err != nil {
		t.Fatalf("创建超管失败: %v", err)
	}

	// 重复邮箱拦截测试
	err = CreateSuperuser(ctx, d, SuperuserOptions{
		Email:    "super@example.com",
		Nickname: "重复",
		Password: "Valid-Secure-Password-987!",
	})
	if err == nil {
		t.Errorf("重复邮箱应被拦截")
	}

	// 验证字段属性
	var isSuper, isActive, isSJTU int
	var verifiedAt sql.NullString
	err = d.ReadPool().QueryRowContext(ctx, "SELECT is_superuser, is_active, is_sjtu, email_verified_at FROM users WHERE email_norm = 'super@example.com'").
		Scan(&isSuper, &isActive, &isSJTU, &verifiedAt)
	if err != nil {
		t.Fatalf("查询创建的超管失败: %v", err)
	}
	if isSuper != 1 || isActive != 1 || isSJTU != 1 || !verifiedAt.Valid {
		t.Errorf("超管字段状态不合规: super=%d, active=%d, sjtu=%d, verified=%v", isSuper, isActive, isSJTU, verifiedAt)
	}
}

func TestReconcile(t *testing.T) {
	ctx := context.Background()
	d, _ := setupTestDB(t)

	res, err := Reconcile(ctx, d, "")
	if err != nil {
		t.Fatalf("自检 Reconcile 失败: %v", err)
	}
	if !res.IntegrityOK || !res.FKCheckOK {
		t.Errorf("自检报告不合规: %+v", res)
	}
	report := res.FormatReport()
	if report == "" {
		t.Errorf("生成对账报告为空")
	}
}
