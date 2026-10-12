package fonts

import (
	"archive/zip"
	"bytes"
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"io"
	"strings"
)

type DownloadOut struct {
	Filename   string `json:"filename"`
	DataBase64 string `json:"data_base64"`
}

func readFaceByID(ctx context.Context, q db.DBTX, id int64) (int64, Face, error) {
	var family int64
	var face Face
	var raw string
	err := q.QueryRowContext(ctx, `SELECT family_id,id,weight,style,slices,bytes,status,error,glyph_count FROM font_faces WHERE id=?`, id).Scan(&family, &face.ID, &face.Weight, &face.Style, &raw, &face.Bytes, &face.Status, &face.Error, &face.GlyphCount)
	if err == sql.ErrNoRows {
		return 0, face, api.NotFound("字体字重不存在")
	}
	if err != nil {
		return 0, face, err
	}
	if err = json.Unmarshal([]byte(raw), &face.Slices); err != nil {
		return 0, face, err
	}
	return family, face, nil
}
func (s *Service) deleteFace(ctx *app.Ctx, id int64) (FontDetail, error) {
	if err := requireSuperuser(ctx); err != nil {
		return FontDetail{}, err
	}
	var family int64
	paths := []string{}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		var err error
		var face Face
		family, face, err = readFaceByID(txCtx, tx, id)
		if err != nil {
			return err
		}
		regions, err := readRegions(txCtx, tx)
		if err != nil {
			return err
		}
		if usedFacePairs(regions)[facePair{family: family, weight: face.Weight}] {
			return api.Invalid("这个字重正在被排版设置使用，请先在排版设置里换成其他字重。")
		}
		paths = objectPaths([]Face{face})
		if _, err = tx.ExecContext(txCtx, `DELETE FROM font_faces WHERE id=?`, id); err != nil {
			return err
		}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "font.face_delete", "font", family, map[string]any{"face_id": id}, ctx.Now())
	})
	if err != nil {
		return FontDetail{}, err
	}
	if err := s.cleanupBlobPaths(ctx.Context, paths, ctx.Now()); err != nil {
		return FontDetail{}, err
	}
	return readFont(ctx.Context, s.d.ReadPool(), family)
}
func (s *Service) downloadFace(ctx *app.Ctx, id int64) (DownloadOut, error) {
	if err := requireSuperuser(ctx); err != nil {
		return DownloadOut{}, err
	}
	family, face, err := readFaceByID(ctx.Context, s.d.ReadPool(), id)
	if err != nil {
		return DownloadOut{}, err
	}
	detail, err := readFont(ctx.Context, s.d.ReadPool(), family)
	if err != nil {
		return DownloadOut{}, err
	}
	if face.Status != "ready" {
		return DownloadOut{}, api.Invalid("这个字重尚未处理完成。")
	}
	root, err := s.openRoot()
	if err != nil {
		return DownloadOut{}, err
	}
	defer root.Close()
	var buf bytes.Buffer
	archive := zip.NewWriter(&buf)
	defer archive.Close()
	total := int64(0)
	seen := map[string]bool{}
	for index, slice := range face.Slices {
		if !cleanEntry(slice.Path) || !strings.HasPrefix(slice.Path, "fonts/") || !strings.HasSuffix(slice.Path, ".woff2") {
			return DownloadOut{}, api.Invalid("字体分片路径不正确。")
		}
		file, err := root.Open(slice.Path)
		if err != nil {
			return DownloadOut{}, api.Invalid("字体分片无法读取。")
		}
		data, err := io.ReadAll(io.LimitReader(file, MaxSliceBytes+1))
		file.Close()
		if err != nil || len(data) > MaxSliceBytes {
			return DownloadOut{}, api.Invalid("字体分片无法读取。")
		}
		hash := digest(data)
		if hash != slice.SHA256 {
			return DownloadOut{}, api.Invalid("字体分片校验失败。")
		}
		name := "slices/" + hash + ".woff2"
		face.Slices[index].Path = name
		if seen[name] {
			continue
		}
		seen[name] = true
		total += int64(len(data))
		if total > MaxPackageBytes {
			return DownloadOut{}, api.Invalid("字重成品包超过64MB。")
		}
		entry, err := archive.Create(name)
		if err != nil {
			return DownloadOut{}, err
		}
		if _, err = entry.Write(data); err != nil {
			return DownloadOut{}, err
		}
	}
	manifest := Manifest{Version: 1, Family: detail.Font.Family, DisplayName: detail.Font.DisplayName, License: detail.Font.License, LicenseConfirmed: true, Faces: []Face{face}}
	entry, err := archive.Create("manifest.json")
	if err != nil {
		return DownloadOut{}, err
	}
	if err = json.NewEncoder(entry).Encode(manifest); err != nil {
		return DownloadOut{}, err
	}
	if err = archive.Close(); err != nil {
		return DownloadOut{}, err
	}
	return DownloadOut{Filename: fmt.Sprintf("font-%d-%d-%s.zip", family, face.Weight, face.Style), DataBase64: base64.StdEncoding.EncodeToString(buf.Bytes())}, nil
}

func (s *Service) libraryCSS(ctx context.Context) (string, error) {
	fonts, err := readFonts(ctx, s.d.ReadPool())
	if err != nil {
		return "", err
	}
	var result strings.Builder
	for _, font := range fonts.Fonts {
		faces, err := readFaces(ctx, s.d.ReadPool(), font.ID)
		if err != nil {
			return "", err
		}
		for _, face := range faces {
			if face.Status != "ready" {
				continue
			}
			for _, slice := range face.Slices {
				if !cleanEntry(slice.Path) || !strings.HasPrefix(slice.Path, "fonts/") || !strings.HasSuffix(slice.Path, ".woff2") || !validUnicodeRange(slice.UnicodeRange) {
					return "", api.Invalid("字体分片元数据不正确。")
				}
				result.WriteString(fmt.Sprintf("@font-face{font-family:%q;font-weight:%d;font-style:%s;font-display:swap;src:url(%q) format(\"woff2\");", font.CSSName, face.Weight, face.Style, "/media/"+slice.Path))
				if slice.UnicodeRange != "" {
					result.WriteString("unicode-range:" + slice.UnicodeRange + ";")
				}
				result.WriteString("}\n")
			}
			result.WriteString(fmt.Sprintf(".font-preview-%d-%d-%s{font-family:%q;font-weight:%d;font-style:%s}\n", font.ID, face.Weight, face.Style, font.CSSName, face.Weight, face.Style))
		}
		result.WriteString(fmt.Sprintf(".font-preview-%d{font-family:%q}\n", font.ID, font.CSSName))
	}
	return result.String(), nil
}

// Old is_face_in_use checks an effective (family,weight) pair, including inherited
// body families. The old gate intentionally treats normal/italic as the same
// weight pair, so deleting an unused weight need not delete its whole family.
type facePair struct {
	family int64
	weight int
}

func usedFacePairs(regions []Region) map[facePair]bool {
	var bodyID *int64
	for _, region := range regions {
		if region.Region == "body" && region.Mode == "custom" {
			bodyID = region.FamilyID
		}
	}
	used := map[facePair]bool{}
	for _, region := range regions {
		if family := effectiveID(region, bodyID); family != nil {
			used[facePair{family: *family, weight: region.Weight}] = true
		}
	}
	return used
}
