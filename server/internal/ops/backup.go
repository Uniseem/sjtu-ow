package ops

import (
	"archive/tar"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Manifest 描述备份元数据（12 号文档 466–474）。
type Manifest struct {
	CreatedAt        string `json:"created_at"`
	SchemaVersion    int64  `json:"schema_version"`
	DatabaseChecksum string `json:"database_checksum"`
	DatabaseSize     int64  `json:"database_size"`
	MediaFilesCount  int    `json:"media_files_count"`
}

// BackupOptions 备份参数。
type BackupOptions struct {
	DataDir  string
	MediaDir string
	OutPath  string
}

// Backup 执行热备份并生成 .tar.gz 归档文件（原子快照、零锁表、合并 WAL）。
func Backup(ctx context.Context, d *db.DB, opts BackupOptions) (*Manifest, error) {
	if d == nil {
		return nil, fmt.Errorf("数据库连接为空")
	}

	dataDir := opts.DataDir
	if dataDir == "" {
		dataDir = "data"
	}
	mediaDir := opts.MediaDir
	if mediaDir == "" {
		mediaDir = filepath.Join(dataDir, "media")
	}

	tmpDir, err := os.MkdirTemp(dataDir, ".staging-backup-*")
	if err != nil {
		// 回退到系统临时目录
		tmpDir, err = os.MkdirTemp("", "sjtuow-backup-*")
		if err != nil {
			return nil, fmt.Errorf("创建临时目录失败: %w", err)
		}
	}
	defer os.RemoveAll(tmpDir)

	tempDB := filepath.Join(tmpDir, "sjtuow.sqlite3")

	// 1. 使用 VACUUM INTO 进行原子热备份（零锁表、合并 WAL、紧凑存储）
	escapedPath := strings.ReplaceAll(tempDB, "'", "''")
	_, err = d.WritePool().ExecContext(ctx, fmt.Sprintf("VACUUM INTO '%s'", escapedPath))
	if err != nil {
		return nil, fmt.Errorf("执行 VACUUM INTO 备份失败: %w", err)
	}

	// 2. 计算 SQLite 备份哈希与大小
	dbFile, err := os.Open(tempDB)
	if err != nil {
		return nil, err
	}
	h := sha256.New()
	dbSize, err := io.Copy(h, dbFile)
	dbFile.Close()
	if err != nil {
		return nil, err
	}
	dbChecksum := hex.EncodeToString(h.Sum(nil))

	// 3. 读取数据库版本
	schemaVer, err := db.Version(ctx, d)
	if err != nil {
		schemaVer = 0
	}

	// 4. 统计媒体与原始图片文件
	originalsDir := filepath.Join(dataDir, "originals")
	mediaCount := 0
	countFiles := func(dir string) {
		if _, err := os.Stat(dir); err == nil {
			_ = filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
				if err == nil && !info.IsDir() {
					mediaCount++
				}
				return nil
			})
		}
	}
	countFiles(originalsDir)
	countFiles(mediaDir)

	now := time.Now().In(time.FixedZone("CST", 8*3600)).Format(time.RFC3339)
	manifest := &Manifest{
		CreatedAt:        now,
		SchemaVersion:    schemaVer,
		DatabaseChecksum: dbChecksum,
		DatabaseSize:     dbSize,
		MediaFilesCount:  mediaCount,
	}

	// 5. 写入目标 .tar.gz（遵循 09-1：写临时文件、fsync、再改名）
	var outWriter io.Writer
	var targetFile *os.File
	var tempOutPath string
	isStdout := opts.OutPath == "-" || opts.OutPath == ""

	if isStdout {
		outWriter = os.Stdout
	} else {
		if err := os.MkdirAll(filepath.Dir(opts.OutPath), 0755); err != nil {
			return nil, err
		}
		tempOutPath = opts.OutPath + fmt.Sprintf(".tmp-%d", time.Now().UnixNano())
		f, err := os.Create(tempOutPath)
		if err != nil {
			return nil, fmt.Errorf("创建输出文件失败: %w", err)
		}
		targetFile = f
		outWriter = f
	}

	gw := gzip.NewWriter(outWriter)
	tw := tar.NewWriter(gw)

	// 写入 manifest.json
	manifestBytes, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		_ = gw.Close()
		if targetFile != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
		}
		return nil, err
	}
	if err := writeTarEntry(tw, "manifest.json", manifestBytes, 0644); err != nil {
		_ = gw.Close()
		if targetFile != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
		}
		return nil, err
	}

	// 写入 sjtuow.sqlite3
	dbData, err := os.ReadFile(tempDB)
	if err != nil {
		_ = gw.Close()
		if targetFile != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
		}
		return nil, err
	}
	if err := writeTarEntry(tw, "sjtuow.sqlite3", dbData, 0644); err != nil {
		_ = gw.Close()
		if targetFile != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
		}
		return nil, err
	}

	// 打包目录工具函数
	packDir := func(baseDir, prefix string) error {
		if _, err := os.Stat(baseDir); os.IsNotExist(err) {
			return nil
		}
		return filepath.Walk(baseDir, func(path string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() {
				return nil
			}
			rel, err := filepath.Rel(baseDir, path)
			if err != nil {
				return nil
			}
			entryName := filepath.ToSlash(filepath.Join(prefix, rel))
			data, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			return writeTarEntry(tw, entryName, data, 0644)
		})
	}

	// 写入 originals/ 与 media/
	if err := packDir(originalsDir, "originals"); err != nil {
		_ = gw.Close()
		if targetFile != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
		}
		return nil, fmt.Errorf("打包 originals 目录失败: %w", err)
	}
	if err := packDir(mediaDir, "media"); err != nil {
		_ = gw.Close()
		if targetFile != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
		}
		return nil, fmt.Errorf("打包 media 目录失败: %w", err)
	}

	// 关闭 tar 与 gzip
	if err := tw.Close(); err != nil {
		if targetFile != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
		}
		return nil, err
	}
	if err := gw.Close(); err != nil {
		if targetFile != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
		}
		return nil, err
	}

	// 对非 stdout 文件进行 fsync 并原子重命名
	if targetFile != nil {
		if err := targetFile.Sync(); err != nil {
			_ = targetFile.Close()
			_ = os.Remove(tempOutPath)
			return nil, fmt.Errorf("fsync 失败: %w", err)
		}
		if err := targetFile.Close(); err != nil {
			_ = os.Remove(tempOutPath)
			return nil, err
		}
		if err := os.Rename(tempOutPath, opts.OutPath); err != nil {
			_ = os.Remove(tempOutPath)
			return nil, fmt.Errorf("原子重命名失败: %w", err)
		}
	}

	return manifest, nil
}

func writeTarEntry(tw *tar.Writer, name string, content []byte, mode int64) error {
	hdr := &tar.Header{
		Name:    name,
		Mode:    mode,
		Size:    int64(len(content)),
		ModTime: time.Now(),
	}
	if err := tw.WriteHeader(hdr); err != nil {
		return err
	}
	_, err := tw.Write(content)
	return err
}

// safeJoin 防目录遍历工具。
func safeJoin(base, rel string) (string, error) {
	cleanRel := filepath.Clean(rel)
	if strings.HasPrefix(cleanRel, "..") || filepath.IsAbs(cleanRel) {
		return "", fmt.Errorf("非法路径越界: %s", rel)
	}
	return filepath.Join(base, cleanRel), nil
}
