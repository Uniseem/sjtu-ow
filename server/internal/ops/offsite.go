package ops

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/crypto"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/storage"
)

var backupName = regexp.MustCompile(`^(?:sjtuow|sjtu-ow)-([0-9]{8}-[0-9]{6})\.tar\.gz(?:\.enc)?$`)

type BackupStatus struct {
	FinishedAt   time.Time `json:"finished_at"`
	Archive      string    `json:"archive"`
	Size         int64     `json:"size"`
	Offsite      string    `json:"offsite"`
	Error        string    `json:"error,omitempty"`
	PruneWarning string    `json:"prune_warning,omitempty"`
}
type OffsiteOptions struct {
	ArchivePath   string
	EncryptionKey string
	Config        storage.Config
	Enabled       bool
	Skip          bool
	RetentionDays int
	Now           time.Time
}

// CompleteBackup records a local success separately from offsite delivery.
// Upload failure keeps the local archive and emits a failed status; cleanup
// only visits timestamp-named archives immediately within this site's prefix.
func CompleteBackup(ctx context.Context, options OffsiteOptions) (*BackupStatus, error) {
	now := options.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	info, err := os.Stat(options.ArchivePath)
	if err != nil {
		return nil, err
	}
	status := &BackupStatus{FinishedAt: now, Archive: filepath.Base(options.ArchivePath), Size: info.Size(), Offsite: "off"}
	root := filepath.Dir(options.ArchivePath)
	var operationErr error
	if options.Enabled {
		status.Offsite = "skipped"
		if !options.Skip {
			status.Offsite = "failed"
			operationErr = uploadBackup(ctx, options)
			if operationErr != nil {
				status.Error = operationErr.Error()
			} else {
				status.Offsite = "uploaded"
				if options.RetentionDays > 0 {
					client, err := storage.New(options.Config, nil)
					if err != nil {
						status.PruneWarning = err.Error()
					} else if _, err := pruneOffsite(ctx, client, options.Config.Prefix, now.Add(-time.Duration(options.RetentionDays)*24*time.Hour)); err != nil {
						status.PruneWarning = err.Error()
					}
				}
			}
		}
	}
	if options.RetentionDays > 0 {
		if _, err := PruneLocalBackups(root, now.Add(-time.Duration(options.RetentionDays)*24*time.Hour), options.ArchivePath); err != nil {
			if status.PruneWarning != "" {
				status.PruneWarning += "；"
			}
			status.PruneWarning += err.Error()
		}
	}
	if err := WriteBackupStatus(root, *status); err != nil {
		return status, fmt.Errorf("备份已生成，但状态未能保存：%w", err)
	}
	if operationErr != nil {
		return status, fmt.Errorf("本地备份已生成，但异地上传失败：%w", operationErr)
	}
	return status, nil
}
func uploadBackup(ctx context.Context, options OffsiteOptions) error {
	client, err := storage.New(options.Config, nil)
	if err != nil {
		return err
	}
	if options.EncryptionKey == "" {
		return errors.New("没有设置 BACKUP_ENCRYPTION_KEY，不能上传未加密的备份。")
	}
	root := filepath.Dir(options.ArchivePath)
	temporary, err := os.CreateTemp(root, ".sjtuow-offsite-*")
	if err != nil {
		return err
	}
	encrypted := temporary.Name()
	if err := temporary.Close(); err != nil {
		os.Remove(encrypted)
		return err
	}
	defer os.Remove(encrypted)
	if err := crypto.EncryptFile(ctx, options.EncryptionKey, options.ArchivePath, encrypted); err != nil {
		return err
	}
	file, err := os.Open(encrypted)
	if err != nil {
		return err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return err
	}
	prefix, err := storage.NormalizePrefix(options.Config.Prefix)
	if err != nil {
		return err
	}
	key := prefix + filepath.Base(options.ArchivePath) + ".enc"
	return client.PutFile(ctx, key, file, info.Size())
}
func backupTime(name string) (time.Time, bool) {
	matches := backupName.FindStringSubmatch(name)
	if len(matches) != 2 {
		return time.Time{}, false
	}
	stamp, err := time.Parse("20060102-150405", matches[1])
	if strings.HasPrefix(name, "sjtu-ow-") {
		zone, zoneErr := time.LoadLocation("Asia/Shanghai")
		if zoneErr != nil {
			return time.Time{}, false
		}
		stamp, err = time.ParseInLocation("20060102-150405", matches[1], zone)
	}
	return stamp, err == nil
}
func PruneLocalBackups(root string, cutoff time.Time, preserve string) (int, error) {
	entries, err := os.ReadDir(root)
	if err != nil {
		return 0, err
	}
	removed := 0
	preserved, _ := filepath.Abs(preserve)
	for _, entry := range entries {
		if entry.IsDir() || entry.Type()&os.ModeSymlink != 0 {
			continue
		}
		if strings.HasSuffix(entry.Name(), ".enc") {
			continue
		}
		stamp, valid := backupTime(entry.Name())
		if !valid || !stamp.Before(cutoff) {
			continue
		}
		path := filepath.Join(root, entry.Name())
		absolute, _ := filepath.Abs(path)
		if absolute == preserved {
			continue
		}
		info, err := entry.Info()
		if err != nil {
			return removed, err
		}
		if !info.Mode().IsRegular() {
			continue
		}
		if err := os.Remove(path); err != nil {
			return removed, fmt.Errorf("清理本地旧备份失败：%w", err)
		}
		removed++
	}
	return removed, nil
}
func pruneOffsite(ctx context.Context, client *storage.Client, rawPrefix string, cutoff time.Time) (int, error) {
	prefix, err := storage.NormalizePrefix(rawPrefix)
	if err != nil {
		return 0, err
	}
	next := ""
	seen := map[string]bool{}
	removed := 0
	for pageNumber := 0; pageNumber < 1000; pageNumber++ {
		if err := ctx.Err(); err != nil {
			return removed, err
		}
		page, err := client.List(ctx, prefix, next)
		if err != nil {
			return removed, err
		}
		for _, object := range page.Items {
			if !strings.HasPrefix(object.Key, prefix) {
				continue
			}
			name := strings.TrimPrefix(object.Key, prefix)
			// A nested object is outside this site's immediate backup directory.
			if strings.Contains(name, "/") || !strings.HasSuffix(name, ".tar.gz.enc") {
				continue
			}
			stamp, valid := backupTime(name)
			if !valid || !stamp.Before(cutoff) {
				continue
			}
			if err := client.Delete(ctx, object.Key); err != nil {
				return removed, err
			}
			removed++
		}
		if page.Next == "" {
			return removed, nil
		}
		if seen[page.Next] {
			return removed, errors.New("对象存储返回重复分页标识，已停止清理。")
		}
		seen[page.Next] = true
		next = page.Next
	}
	return removed, errors.New("对象存储分页过多，已停止清理。")
}
func WriteBackupStatus(root string, status BackupStatus) error {
	data, err := json.MarshalIndent(status, "", "  ")
	if err != nil {
		return err
	}
	file, err := os.CreateTemp(root, ".backup-status-*")
	if err != nil {
		return err
	}
	name := file.Name()
	defer os.Remove(name)
	defer file.Close()
	if err := file.Chmod(0600); err != nil {
		return err
	}
	if _, err := file.Write(append(data, '\n')); err != nil {
		return err
	}
	if err := file.Sync(); err != nil {
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	return os.Rename(name, filepath.Join(root, "last-backup.json"))
}
func ReadBackupStatus(root string) (*BackupStatus, error) {
	data, err := os.ReadFile(filepath.Join(root, "last-backup.json"))
	if err != nil {
		return nil, err
	}
	if len(data) > 64*1024 {
		return nil, errors.New("备份状态文件过大。")
	}
	var status BackupStatus
	if err := json.Unmarshal(data, &status); err != nil {
		return nil, err
	}
	if status.FinishedAt.IsZero() {
		return nil, errors.New("备份完成时间缺失。")
	}
	return &status, nil
}
