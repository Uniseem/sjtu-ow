package media

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"image"
	"os"
	"path"
	"path/filepath"
	"strings"
)

func LegacyRenditionPath(file string) bool {
	if strings.ContainsAny(file, "\\\x00") || path.Clean(file) != file || !strings.HasPrefix(file, "images/") {
		return false
	}
	switch strings.ToLower(path.Ext(file)) {
	case ".jpg", ".jpeg", ".png", ".webp", ".gif":
		return true
	}
	return false
}

func (s *Service) renditionManifest(id int64) string { return s.MasterPath(id) + ".legacy.json" }

// Copy only validated renditions recorded by the importer into the isolated
// new media volume. A private per-image manifest survives metadata deletion so
// avatar moderation/account deletion can remove the old public URLs too.
func (s *Service) importLegacyRenditionFiles(ctx context.Context, source string, rep *ImportReport) error {
	rows, err := s.db.ReadPool().QueryContext(ctx, `SELECT image_id,file_name FROM legacy_image_renditions ORDER BY image_id,file_name`)
	if err != nil {
		return err
	}
	type item struct {
		id   int64
		file string
	}
	var items []item
	for rows.Next() {
		var entry item
		if err := rows.Scan(&entry.id, &entry.file); err != nil {
			rows.Close()
			return err
		}
		items = append(items, entry)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	rows.Close()
	manifests := map[int64][]string{}
	sourceRoot, err := filepath.EvalSymlinks(source)
	if err != nil {
		return err
	}
	for _, entry := range items {
		if err := ctx.Err(); err != nil {
			return err
		}
		if !LegacyRenditionPath(entry.file) {
			return fmt.Errorf("旧缩略图路径无效，图片编号%d", entry.id)
		}
		src, ok := within(sourceRoot, entry.file)
		if !ok {
			return fmt.Errorf("旧缩略图路径越界，图片编号%d", entry.id)
		}
		info, err := os.Lstat(src)
		if os.IsNotExist(err) {
			rep.Missing = append(rep.Missing, fmt.Sprintf("%d 旧缩略图缺失", entry.id))
			continue
		}
		if err != nil {
			return err
		}
		resolved, err := filepath.EvalSymlinks(src)
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() || !strings.HasPrefix(resolved, sourceRoot+string(filepath.Separator)) {
			return fmt.Errorf("旧缩略图不是本站普通文件，图片编号%d", entry.id)
		}
		data, err := readLimited(src)
		if err != nil {
			return err
		}
		if _, format, err := image.DecodeConfig(bytes.NewReader(data)); err != nil || (format != "jpeg" && format != "png" && format != "webp" && format != "gif") {
			return fmt.Errorf("旧缩略图内容无效，图片编号%d", entry.id)
		}
		dst, ok := within(s.mediaDir, entry.file)
		if !ok {
			return fmt.Errorf("旧缩略图目标越界，图片编号%d", entry.id)
		}
		if err := os.MkdirAll(filepath.Dir(dst), 0755); err != nil {
			return err
		}
		existing, readErr := os.ReadFile(dst)
		if !bytes.Equal(existing, data) || readErr != nil {
			// Atomic replacement prevents a half-written public image after interruption.
			tmp, err := os.CreateTemp(filepath.Dir(dst), ".rendition-*")
			if err != nil {
				return err
			}
			name := tmp.Name()
			if _, err = tmp.Write(data); err == nil {
				err = tmp.Chmod(0644)
			}
			closeErr := tmp.Close()
			if err == nil {
				err = closeErr
			}
			if err == nil {
				err = os.Rename(name, dst)
			}
			if err != nil {
				os.Remove(name)
				return err
			}
		}
		manifests[entry.id] = append(manifests[entry.id], entry.file)
		rep.Renditions++
	}
	for id, files := range manifests {
		data, err := json.Marshal(files)
		if err != nil {
			return err
		}
		manifest := s.renditionManifest(id)
		if err := os.MkdirAll(filepath.Dir(manifest), 0700); err != nil {
			return err
		}
		if err := os.WriteFile(manifest+".tmp", data, 0600); err != nil {
			return err
		}
		if err := os.Rename(manifest+".tmp", manifest); err != nil {
			return err
		}
	}
	return nil
}

func (s *Service) deleteLegacyRenditionFiles(id int64) {
	manifest := s.renditionManifest(id)
	data, err := os.ReadFile(manifest)
	if err != nil || len(data) > 1<<20 {
		return
	}
	var files []string
	if json.Unmarshal(data, &files) != nil {
		return
	}
	for _, file := range files {
		if !LegacyRenditionPath(file) {
			continue
		}
		target, ok := within(s.mediaDir, file)
		if ok {
			_ = os.Remove(target)
		}
	}
	_ = os.Remove(manifest)
}
