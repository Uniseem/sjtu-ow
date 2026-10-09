package ops

import (
	"archive/tar"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "modernc.org/sqlite"
)

// RestoreOptions 恢复参数（12 号文档 473、09-5）。
type RestoreOptions struct {
	ArchivePath string
	DataDir     string
	MediaDir    string
	Apply       bool // 默认 false（只演练校验，--yes 才真正替换）
}

// RestoreResult 恢复与校验结果。
type RestoreResult struct {
	Manifest      *Manifest
	IntegrityOK   bool
	FKCheckOK     bool
	FilesRestored int
	DryRun        bool
}

// Restore 解包并恢复数据，包含校验和核验与 PRAGMA integrity_check。
func Restore(ctx context.Context, opts RestoreOptions) (*RestoreResult, error) {
	dataDir := opts.DataDir
	if dataDir == "" {
		dataDir = "data"
	}
	mediaDir := opts.MediaDir
	if mediaDir == "" {
		mediaDir = filepath.Join(dataDir, "media")
	}

	if err := os.MkdirAll(dataDir, 0755); err != nil {
		return nil, fmt.Errorf("创建数据目录失败: %w", err)
	}

	// 09-5：在 data 卷里的私有临时目录（0700）解包，不落 /tmp
	stagingDir, err := os.MkdirTemp(dataDir, ".staging-restore-*")
	if err != nil {
		return nil, fmt.Errorf("创建私有解包目录失败: %w", err)
	}
	_ = os.Chmod(stagingDir, 0700)
	defer os.RemoveAll(stagingDir)

	// 1. 打开归档（支持文件路径或 stdin）
	var inReader io.Reader
	var closeIn func() error = func() error { return nil }

	if opts.ArchivePath == "-" || opts.ArchivePath == "" {
		inReader = os.Stdin
	} else {
		f, err := os.Open(opts.ArchivePath)
		if err != nil {
			return nil, fmt.Errorf("打开备份归档文件失败: %w", err)
		}
		inReader = f
		closeIn = f.Close
	}
	defer closeIn()

	gr, err := gzip.NewReader(inReader)
	if err != nil {
		return nil, fmt.Errorf("解压 gzip 失败: %w", err)
	}
	defer gr.Close()

	tr := tar.NewReader(gr)
	filesCount := 0

	// 2. 解包文件并防目录遍历
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("读取归档条目失败: %w", err)
		}

		targetPath, err := safeJoin(stagingDir, hdr.Name)
		if err != nil {
			return nil, fmt.Errorf("归档条目路径非法: %w", err)
		}

		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(targetPath, 0755); err != nil {
				return nil, err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(targetPath), 0755); err != nil {
				return nil, err
			}
			f, err := os.OpenFile(targetPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
			if err != nil {
				return nil, fmt.Errorf("写入解包文件失败: %w", err)
			}
			if _, err := io.Copy(f, tr); err != nil {
				f.Close()
				return nil, err
			}
			f.Close()
			filesCount++
		}
	}

	// 3. 校验 manifest.json
	manifestPath := filepath.Join(stagingDir, "manifest.json")
	manifestData, err := os.ReadFile(manifestPath)
	if err != nil {
		return nil, fmt.Errorf("备份归档缺少 manifest.json: %w", err)
	}
	var manifest Manifest
	if err := json.Unmarshal(manifestData, &manifest); err != nil {
		return nil, fmt.Errorf("解析 manifest.json 失败: %w", err)
	}

	// 4. 校验 SQLite 文件与哈希
	stagingDB := filepath.Join(stagingDir, "sjtuow.sqlite3")
	dbFile, err := os.Open(stagingDB)
	if err != nil {
		return nil, fmt.Errorf("备份归档缺少 sjtuow.sqlite3: %w", err)
	}
	h := sha256.New()
	if _, err := io.Copy(h, dbFile); err != nil {
		dbFile.Close()
		return nil, err
	}
	dbFile.Close()

	actualChecksum := hex.EncodeToString(h.Sum(nil))
	if !strings.EqualFold(actualChecksum, manifest.DatabaseChecksum) {
		return nil, fmt.Errorf("数据库 SHA256 校验和不匹配: 期望 %s, 实际 %s", manifest.DatabaseChecksum, actualChecksum)
	}

	// 5. 校验数据库完整性（PRAGMA integrity_check）
	dbConn, err := sql.Open("sqlite", fmt.Sprintf("file:%s?mode=ro", stagingDB))
	if err != nil {
		return nil, fmt.Errorf("打开解包数据库失败: %w", err)
	}
	var integrityResult string
	err = dbConn.QueryRowContext(ctx, "PRAGMA integrity_check;").Scan(&integrityResult)
	if err != nil || integrityResult != "ok" {
		dbConn.Close()
		return nil, fmt.Errorf("PRAGMA integrity_check 校验失败: %s (err: %v)", integrityResult, err)
	}

	// 校验外键完整性（PRAGMA foreign_key_check）
	fkRows, err := dbConn.QueryContext(ctx, "PRAGMA foreign_key_check;")
	fkOK := true
	if err == nil {
		if fkRows.Next() {
			fkOK = false
		}
		fkRows.Close()
	}
	dbConn.Close()

	result := &RestoreResult{
		Manifest:      &manifest,
		IntegrityOK:   true,
		FKCheckOK:     fkOK,
		FilesRestored: filesCount,
		DryRun:        !opts.Apply,
	}

	// 6. 如果只演练（--yes 未提供），直接返回校验成功
	if !opts.Apply {
		return result, nil
	}

	// 7. 真正替换（Atomic Swap）
	targetDB := filepath.Join(dataDir, "sjtuow.sqlite3")
	if _, err := os.Stat(targetDB); err == nil {
		// 清理旧 WAL 和 SHM
		_ = os.Remove(targetDB + "-wal")
		_ = os.Remove(targetDB + "-shm")
		// 备份旧库文件
		backupOld := fmt.Sprintf("%s.bak-%s", targetDB, time.Now().Format("20060102150405"))
		_ = os.Rename(targetDB, backupOld)
	}

	// 移动 SQLite 文件
	if err := copyOrMoveFile(stagingDB, targetDB); err != nil {
		return nil, fmt.Errorf("还原数据库文件失败: %w", err)
	}

	// 移动 originals 目录
	stagingOriginals := filepath.Join(stagingDir, "originals")
	targetOriginals := filepath.Join(dataDir, "originals")
	if _, err := os.Stat(stagingOriginals); err == nil {
		if err := copyDir(stagingOriginals, targetOriginals); err != nil {
			return nil, fmt.Errorf("还原 originals 目录失败: %w", err)
		}
	}

	// 移动 media 目录
	stagingMedia := filepath.Join(stagingDir, "media")
	if _, err := os.Stat(stagingMedia); err == nil {
		if err := copyDir(stagingMedia, mediaDir); err != nil {
			return nil, fmt.Errorf("还原 media 目录失败: %w", err)
		}
	}

	return result, nil
}

func copyOrMoveFile(src, dst string) error {
	if err := os.Rename(src, dst); err == nil {
		return nil
	}
	// 跨盘复制回退
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	if err := os.MkdirAll(filepath.Dir(dst), 0755); err != nil {
		return err
	}
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	return out.Sync()
}

func copyDir(srcDir, dstDir string) error {
	if err := os.MkdirAll(dstDir, 0755); err != nil {
		return err
	}
	return filepath.Walk(srcDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(srcDir, path)
		if err != nil {
			return err
		}
		target := filepath.Join(dstDir, rel)
		if info.IsDir() {
			return os.MkdirAll(target, 0755)
		}
		return copyOrMoveFile(path, target)
	})
}
