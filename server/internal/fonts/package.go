package fonts

import (
	"archive/zip"
	"bytes"
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path"
	"regexp"
	"strings"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type Manifest struct {
	Version          int    `json:"version"`
	Family           string `json:"family"`
	DisplayName      string `json:"display_name"`
	License          string `json:"license"`
	LicenseConfirmed bool   `json:"license_confirmed"`
	Faces            []Face `json:"faces"`
}
type preparedFont struct {
	manifest          Manifest
	data              map[string][]byte
	source, sourceRef string
}

var unicodeRanges = regexp.MustCompile(`(?i)^U\+[0-9A-F?]{1,6}(?:-[0-9A-F]{1,6})?(?:\s*,\s*U\+[0-9A-F?]{1,6}(?:-[0-9A-F]{1,6})?)*$`)

func validUnicodeRange(value string) bool {
	return value == "" || (len(value) <= 65536 && unicodeRanges.MatchString(value))
}
func validateWOFF2(data []byte) error {
	if len(data) < 48 || string(data[:4]) != "wOF2" {
		return api.Invalid("成品包只接受 WOFF2 字体分片。")
	}
	if uint64(binary.BigEndian.Uint32(data[8:12])) != uint64(len(data)) {
		return api.Invalid("WOFF2 文件长度不正确。")
	}
	if binary.BigEndian.Uint16(data[12:14]) == 0 || binary.BigEndian.Uint16(data[14:16]) != 0 {
		return api.Invalid("WOFF2 文件头不正确。")
	}
	if binary.BigEndian.Uint32(data[16:20]) > 128<<20 {
		return api.Invalid("字体解压后超过大小上限。")
	}
	return nil
}
func cleanEntry(name string) bool {
	return name != "" && !strings.HasPrefix(name, "/") && !strings.Contains(name, `\`) && path.Clean(name) == name && !strings.Contains(name, ":") && name != ".." && !strings.HasPrefix(name, "../")
}
func readZipFile(file *zip.File, limit int64) ([]byte, error) {
	if file.UncompressedSize64 > uint64(limit) {
		return nil, api.Invalid("成品包文件超过大小上限。")
	}
	if file.Mode()&os.ModeSymlink != 0 {
		return nil, api.Invalid("成品包不能包含符号链接。")
	}
	reader, err := file.Open()
	if err != nil {
		return nil, api.Invalid("成品包文件无法打开。")
	}
	defer reader.Close()
	data, err := io.ReadAll(io.LimitReader(reader, limit+1))
	if err != nil {
		return nil, api.Invalid("成品包文件校验失败。")
	}
	if int64(len(data)) > limit {
		return nil, api.Invalid("成品包文件超过大小上限。")
	}
	return data, nil
}
func preparePackage(data []byte) (preparedFont, error) {
	out := preparedFont{data: map[string][]byte{}, source: "package"}
	if len(data) == 0 || len(data) > MaxPackageBytes {
		return out, api.Invalid("成品包大小不正确，最大64MB。")
	}
	archive, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return out, api.Invalid("无法打开字体成品包，请上传 ZIP 文件。")
	}
	if len(archive.File) > MaxSlices+2 {
		return out, api.Invalid("成品包文件数量超过上限。")
	}
	entries := map[string]*zip.File{}
	var total uint64
	for _, file := range archive.File {
		if file.FileInfo().IsDir() {
			continue
		}
		if !cleanEntry(file.Name) {
			return out, api.Invalid("成品包包含不安全的文件路径。")
		}
		if _, exists := entries[file.Name]; exists {
			return out, api.Invalid("成品包包含重复文件名。")
		}
		if file.Mode()&os.ModeSymlink != 0 {
			return out, api.Invalid("成品包不能包含符号链接。")
		}
		total += file.UncompressedSize64
		if total > MaxPackageBytes {
			return out, api.Invalid("成品包解压后超过64MB。")
		}
		entries[file.Name] = file
	}
	manifestFile, exists := entries["manifest.json"]
	if !exists {
		return out, api.Invalid("成品包缺少 manifest.json。")
	}
	raw, err := readZipFile(manifestFile, 1<<20)
	if err != nil {
		return out, err
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&out.manifest); err != nil {
		return out, api.Invalid("成品包清单格式不正确。")
	}
	if decoder.Decode(&struct{}{}) != io.EOF {
		return out, api.Invalid("成品包清单包含额外内容。")
	}
	manifest := &out.manifest
	manifest.Family = strings.TrimSpace(manifest.Family)
	manifest.DisplayName = strings.TrimSpace(manifest.DisplayName)
	if manifest.Version != 1 {
		return out, api.Invalid("不支持此成品包版本。")
	}
	if manifest.Family == "" || utf8.RuneCountInString(manifest.Family) > 120 {
		return out, api.Invalid("字体家族名称不正确。")
	}
	if manifest.DisplayName == "" {
		manifest.DisplayName = manifest.Family
	}
	if utf8.RuneCountInString(manifest.DisplayName) > 64 {
		return out, api.Invalid("字体显示名称不能超过64字。")
	}
	if !manifest.LicenseConfirmed || strings.TrimSpace(manifest.License) == "" {
		return out, api.Invalid("成品包必须注明授权并确认允许网页嵌入。")
	}
	if len(manifest.License) > 10000 {
		return out, api.Invalid("授权说明超过大小上限。")
	}
	if len(manifest.Faces) == 0 || len(manifest.Faces) > 18 {
		return out, api.Invalid("成品包字重数量不正确。")
	}
	faces := map[string]bool{}
	used := map[string]bool{"manifest.json": true}
	count := 0
	for faceIndex := range manifest.Faces {
		face := &manifest.Faces[faceIndex]
		if !validWeight(face.Weight) || (face.Style != "normal" && face.Style != "italic") {
			return out, api.Invalid("字重或字体样式不正确。")
		}
		key := fmt.Sprintf("%d/%s", face.Weight, face.Style)
		if faces[key] {
			return out, api.Invalid("成品包包含重复字重和样式。")
		}
		faces[key] = true
		if len(face.Slices) == 0 {
			return out, api.Invalid("字体字重没有分片。")
		}
		face.Bytes = 0
		for sliceIndex := range face.Slices {
			slice := &face.Slices[sliceIndex]
			count++
			if count > MaxSlices {
				return out, api.Invalid("字体分片数量超过上限。")
			}
			if !cleanEntry(slice.Path) || !strings.HasSuffix(strings.ToLower(slice.Path), ".woff2") {
				return out, api.Invalid("字体分片路径不正确。")
			}
			if used[slice.Path] {
				return out, api.Invalid("同一个分片不能重复引用。")
			}
			used[slice.Path] = true
			if !validUnicodeRange(slice.UnicodeRange) {
				return out, api.Invalid("分片 unicode-range 不正确。")
			}
			file, exists := entries[slice.Path]
			if !exists {
				return out, api.Invalid("成品包缺少清单中列出的分片。")
			}
			bytes, err := readZipFile(file, MaxSliceBytes)
			if err != nil {
				return out, err
			}
			if err := validateWOFF2(bytes); err != nil {
				return out, err
			}
			hash := digest(bytes)
			if !strings.EqualFold(slice.SHA256, hash) || slice.Bytes != int64(len(bytes)) {
				return out, api.Invalid("字体分片的 SHA256 或长度校验失败。")
			}
			face.Bytes += int64(len(bytes))
			out.data[hash] = bytes
			slice.Path = "fonts/objects/" + hash + ".woff2"
			slice.SHA256 = hash
		}
	}
	for name := range entries {
		if !used[name] && name != "LICENSE.txt" {
			return out, api.Invalid("成品包包含清单以外的文件。")
		}
	}
	return out, nil
}
func (s *Service) importFont(ctx *app.Ctx, in ImportIn) (FontDetail, error) {
	if err := requireSuperuser(ctx); err != nil {
		return FontDetail{}, err
	}
	if !in.LicenseConfirmed {
		return FontDetail{}, api.InvalidFields(map[string][]string{"license_confirmed": {"请确认字体允许在本站使用。"}})
	}
	var prepared preparedFont
	var err error
	switch in.Source {
	case "package":
		var bytes []byte
		if in.UploadID > 0 {
			bytes, err = s.assembledUpload(ctx, in.UploadID)
		} else if len(in.PackageBase64) < 900000 {
			bytes, err = base64.StdEncoding.Strict().DecodeString(in.PackageBase64)
		} else {
			err = api.Invalid("较大的成品包请使用分块上传。")
		}
		if err != nil {
			return FontDetail{}, err
		}
		prepared, err = preparePackage(bytes)
	case "google":
		prepared, err = prepareGoogle(ctx.Context, in.Family, in.Weights)
	default:
		return FontDetail{}, api.InvalidFields(map[string][]string{"source": {"请选择成品包或 Google Fonts。"}})
	}
	if err != nil {
		return FontDetail{}, err
	}
	if in.Source == "package" {
		prepared.sourceRef = in.PackageName
	}
	for hash, data := range prepared.data {
		if err := s.writeBlob("fonts/objects/"+hash+".woff2", data); err != nil {
			return FontDetail{}, err
		}
	}
	content, err := json.Marshal(prepared.manifest)
	if err != nil {
		return FontDetail{}, err
	}
	cssName := "owfont-" + digest(content)[:24]
	var id int64
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		err := tx.QueryRowContext(txCtx, `SELECT id FROM font_families WHERE css_name=?`, cssName).Scan(&id)
		if err == nil {
			if in.UploadID > 0 {
				if _, err := readUpload(txCtx, tx, in.UploadID, ctx.Viewer.ID, ctx.Now()); err != nil {
					return err
				}
				_, err := tx.ExecContext(txCtx, `UPDATE font_uploads SET state='consumed' WHERE id=? AND owner_id=?`, in.UploadID, ctx.Viewer.ID)
				return err
			}
			return nil
		}
		if err != sql.ErrNoRows {
			return err
		}
		if in.UploadID > 0 {
			if _, err := readUpload(txCtx, tx, in.UploadID, ctx.Viewer.ID, ctx.Now()); err != nil {
				return err
			}
		}
		result, err := tx.ExecContext(txCtx, `INSERT INTO font_families(family,display_name,css_name,source,source_ref,license,license_confirmed,created_by,created_at) VALUES(?,?,?,?,?,?,1,?,?)`, prepared.manifest.Family, prepared.manifest.DisplayName, cssName, prepared.source, prepared.sourceRef, prepared.manifest.License, ctx.Viewer.ID, stamp(ctx.Now()))
		if err != nil {
			return err
		}
		id, err = result.LastInsertId()
		if err != nil {
			return err
		}
		for _, face := range prepared.manifest.Faces {
			raw, err := json.Marshal(face.Slices)
			if err != nil {
				return err
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO font_faces(family_id,weight,style,slices,bytes) VALUES(?,?,?,?,?)`, id, face.Weight, face.Style, string(raw), face.Bytes); err != nil {
				return err
			}
		}
		if in.UploadID > 0 {
			if _, err := tx.ExecContext(txCtx, `UPDATE font_uploads SET state='consumed' WHERE id=? AND owner_id=?`, in.UploadID, ctx.Viewer.ID); err != nil {
				return err
			}
		}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "font.import", "font", id, map[string]any{"source": prepared.source, "family": prepared.manifest.Family}, ctx.Now())
	})
	if err != nil {
		return FontDetail{}, err
	}
	return readFont(ctx.Context, s.d.ReadPool(), id)
}
func (s *Service) delete(ctx *app.Ctx, id int64) (Result, error) {
	if err := requireSuperuser(ctx); err != nil {
		return Result{}, err
	}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		detail, err := readFont(txCtx, tx, id)
		if err != nil {
			return err
		}
		if !detail.Font.CanDelete {
			return api.InvalidFields(map[string][]string{"__all__": {"字体正在被排版设置使用，不能删除。"}})
		}
		if _, err := tx.ExecContext(txCtx, `DELETE FROM font_families WHERE id=?`, id); err != nil {
			return err
		}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "font.delete", "font", id, map[string]any{"family": detail.Font.Family}, ctx.Now())
	})
	if err != nil {
		return Result{}, err
	}
	// Content-addressed files may be shared and CSS is immutable; do not unlink them here.
	return Result{Result: "deleted"}, nil
}
