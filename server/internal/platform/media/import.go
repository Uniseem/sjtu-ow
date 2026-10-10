package media

import (
	"bytes"
	"context"
	"fmt"
	"image"
	_ "image/gif" // 旧库里可能有 GIF；导入时取第一帧
	"io"
	"os"
	"path/filepath"
	"strings"
)

// maxLegacyFile 旧原图的大小上限。新上传是 10 MB；旧图是当年过 core/uploads.py 的，
// 放宽一些，真正的护栏是像素上限 MaxPixels。
const maxLegacyFile = 64 << 20

// ImportReport 是 ImportLegacyMasters 的结果。Missing、Failed 列出图片编号和原因，
// 命令行原样打印，不吞（frontend-migration 263 发现 content 的导入把错误全吞了）。
type ImportReport struct {
	Made    int
	Skipped int
	Missing []string
	Failed  []string
}

// ImportLegacyMasters 把旧站（Wagtail）的原图过新管线做成母版：images 表里每一行，
// 母版还没有的，到 legacyMediaDir 下按 file_name（如 original_images/a.jpg）找原文件，
// 查像素、完整解码、长边缩到 2560、重新编码成 WebP（不带 EXIF、GPS），写进
// data/originals/<id>.webp（design-next 第 6 节「图片」）。已有母版的跳过，可以重复跑。
// 不开写事务：只读表、只写文件。
func (s *Service) ImportLegacyMasters(ctx context.Context, legacyMediaDir string) (ImportReport, error) {
	var rep ImportReport
	root, err := filepath.Abs(legacyMediaDir)
	if err != nil {
		return rep, err
	}
	rows, err := s.db.ReadPool().QueryContext(ctx, `SELECT id, file_name FROM images ORDER BY id`)
	if err != nil {
		return rep, err
	}
	type row struct {
		id   int64
		file string
	}
	var all []row
	for rows.Next() {
		var r row
		if err := rows.Scan(&r.id, &r.file); err != nil {
			_ = rows.Close()
			return rep, err
		}
		all = append(all, r)
	}
	if err := rows.Close(); err != nil {
		return rep, err
	}
	for _, r := range all {
		if err := ctx.Err(); err != nil {
			return rep, err
		}
		if _, err := os.Stat(s.MasterPath(r.id)); err == nil {
			rep.Skipped++
			continue
		}
		path, ok := within(root, r.file)
		if !ok {
			rep.Failed = append(rep.Failed, fmt.Sprintf("%d %s：文件名越出了媒体目录", r.id, r.file))
			continue
		}
		data, err := readLimited(path)
		if os.IsNotExist(err) {
			rep.Missing = append(rep.Missing, fmt.Sprintf("%d %s", r.id, r.file))
			continue
		}
		if err != nil {
			rep.Failed = append(rep.Failed, fmt.Sprintf("%d %s：%v", r.id, r.file, err))
			continue
		}
		cfg, _, err := image.DecodeConfig(bytes.NewReader(data))
		if err != nil {
			rep.Failed = append(rep.Failed, fmt.Sprintf("%d %s：读不出图头", r.id, r.file))
			continue
		}
		if int64(cfg.Width)*int64(cfg.Height) > MaxPixels {
			rep.Failed = append(rep.Failed, fmt.Sprintf("%d %s：超过 4000 万像素", r.id, r.file))
			continue
		}
		s.sem.Lock()
		master, _, _, err := encodeMaster(data)
		s.sem.Unlock()
		if err != nil {
			rep.Failed = append(rep.Failed, fmt.Sprintf("%d %s：%v", r.id, r.file, err))
			continue
		}
		if err := s.writeMaster(r.id, master); err != nil {
			rep.Failed = append(rep.Failed, fmt.Sprintf("%d %s：%v", r.id, r.file, err))
			continue
		}
		rep.Made++
	}
	return rep, nil
}

// within 把库里的相对文件名接到媒体目录下；绝对路径、`..` 越出目录的一律不认。
func within(root, rel string) (string, bool) {
	if rel == "" || filepath.IsAbs(rel) || strings.Contains(rel, "\x00") {
		return "", false
	}
	full := filepath.Join(root, filepath.FromSlash(rel))
	if full != root && !strings.HasPrefix(full, root+string(filepath.Separator)) {
		return "", false
	}
	return full, true
}

func readLimited(path string) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, maxLegacyFile+1))
	if err != nil {
		return nil, err
	}
	if len(data) > maxLegacyFile {
		return nil, fmt.Errorf("超过 %d MB", maxLegacyFile>>20)
	}
	return data, nil
}
