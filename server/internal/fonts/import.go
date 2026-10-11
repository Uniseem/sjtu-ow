package fonts

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type ImportReport struct {
	Families int
	Faces    int
	Slices   int
	Regions  int
	Bytes    int64
}
type legacyFont struct {
	id                                                                  int64
	name, cssName, source, sourceRef, licenseType, licenseNote, created string
	confirmed                                                           bool
	actor                                                               *int64
}
type legacyFace struct {
	id, family           int64
	weight               int
	style, status, error string
	slices               []Slice
	bytes                int64
}

func hasLegacyTable(ctx context.Context, legacy *sql.DB, name string) (bool, error) {
	var count int
	err := legacy.QueryRowContext(ctx, `SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?`, name).Scan(&count)
	return count > 0, err
}
func readLegacyBytes(root *os.Root, name string) ([]byte, error) {
	if !cleanEntry(name) || !strings.HasPrefix(name, "fonts/") || !strings.HasSuffix(strings.ToLower(name), ".woff2") {
		return nil, fmt.Errorf("旧字体分片路径不正确: %s", name)
	}
	file, err := root.Open(name)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, MaxSliceBytes+1))
	if err != nil {
		return nil, err
	}
	if len(data) > MaxSliceBytes {
		return nil, fmt.Errorf("旧字体分片超过大小上限")
	}
	if err := validateWOFF2(data); err != nil {
		return nil, err
	}
	return data, nil
}

// ImportLegacyFonts keeps Django identifiers, CSS names, selected faces and all
// nine typography values. It opens legacy files through a read-only bounded root;
// no Python processing, source download, or mutation of the old library occurs.
func ImportLegacyFonts(ctx context.Context, d *db.DB, legacy *sql.DB, legacyMedia, mediaDir string) (ImportReport, error) {
	report := ImportReport{}
	exists, err := hasLegacyTable(ctx, legacy, "core_fontfamily")
	if err != nil || !exists {
		return report, err
	}
	families := []legacyFont{}
	rows, err := legacy.QueryContext(ctx, `SELECT id,name,css_name,source,source_ref,license_type,license_note,license_confirmed,created_by_id,created_at FROM core_fontfamily ORDER BY id`)
	if err != nil {
		return report, err
	}
	for rows.Next() {
		var font legacyFont
		if err := rows.Scan(&font.id, &font.name, &font.cssName, &font.source, &font.sourceRef, &font.licenseType, &font.licenseNote, &font.confirmed, &font.actor, &font.created); err != nil {
			rows.Close()
			return report, err
		}
		families = append(families, font)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return report, err
	}
	faces := []legacyFace{}
	rows, err = legacy.QueryContext(ctx, `SELECT id,family_id,weight,style,status,error,slices FROM core_fontface ORDER BY id`)
	if err != nil {
		return report, err
	}
	// Legacy slice JSON has only path/unicode_range. Integrity fields are rebuilt
	// from the actual unchanged WOFF2 bytes before anything is put into the new DB.
	for rows.Next() {
		var face legacyFace
		var raw string
		if err := rows.Scan(&face.id, &face.family, &face.weight, &face.style, &face.status, &face.error, &raw); err != nil {
			rows.Close()
			return report, err
		}
		if err := json.Unmarshal([]byte(raw), &face.slices); err != nil {
			rows.Close()
			return report, fmt.Errorf("旧字体%d清单无法读取: %w", face.id, err)
		}
		faces = append(faces, face)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return report, err
	}
	rules := []Region{}
	if exists, err := hasLegacyTable(ctx, legacy, "core_typographyrule"); err != nil {
		return report, err
	} else if exists {
		rows, err = legacy.QueryContext(ctx, `SELECT region,mode,family_id,weight,size_rem,line_height,letter_spacing_em FROM core_typographyrule`)
		if err != nil {
			return report, err
		}
		for rows.Next() {
			var region Region
			if err := rows.Scan(&region.Region, &region.Mode, &region.FamilyID, &region.Weight, &region.SizeRem, &region.LineHeight, &region.LetterSpacingEM); err != nil {
				rows.Close()
				return report, err
			}
			if regionLabel(region.Region) == "" {
				rows.Close()
				return report, fmt.Errorf("旧排版区域无法识别: %s", region.Region)
			}
			rules = append(rules, region)
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return report, err
		}
	}
	var root *os.Root
	for _, face := range faces {
		if face.status == "ready" && len(face.slices) > 0 {
			root, err = os.OpenRoot(legacyMedia)
			if err != nil {
				return report, err
			}
			break
		}
	}
	if root != nil {
		defer root.Close()
	}
	service := NewService(d, mediaDir, "")
	for i := range faces {
		face := &faces[i]
		if face.status != "ready" {
			continue
		}
		if len(face.slices) == 0 {
			return report, fmt.Errorf("旧字体%d标记可用但没有分片", face.id)
		}
		for j := range face.slices {
			slice := &face.slices[j]
			if !validUnicodeRange(slice.UnicodeRange) {
				return report, fmt.Errorf("旧字体%d unicode-range不正确", face.id)
			}
			data, err := readLegacyBytes(root, slice.Path)
			if err != nil {
				return report, fmt.Errorf("复制旧字体%d: %w", face.id, err)
			}
			hash := digest(data)
			slice.Path = "fonts/objects/" + hash + ".woff2"
			slice.SHA256 = hash
			slice.Bytes = int64(len(data))
			if err := service.writeBlob(slice.Path, data); err != nil {
				return report, err
			}
			face.bytes += slice.Bytes
			report.Bytes += slice.Bytes
			report.Slices++
		}
	}
	now := time.Now().UTC()
	err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		for _, font := range families {
			created, err := db.ParseUTC(font.created)
			if err != nil {
				created = now
			}
			license := font.licenseType
			if font.licenseNote != "" {
				license += " · " + font.licenseNote
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO font_families(id,family,display_name,css_name,source,source_ref,license,license_confirmed,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET family=excluded.family,display_name=excluded.display_name,css_name=excluded.css_name,source=excluded.source,source_ref=excluded.source_ref,license=excluded.license,license_confirmed=excluded.license_confirmed`, font.id, font.name, font.name, font.cssName, font.source, font.sourceRef, license, font.confirmed, font.actor, stamp(created)); err != nil {
				return err
			}
			report.Families++
		}
		for _, face := range faces {
			raw, err := json.Marshal(face.slices)
			if err != nil {
				return err
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO font_faces(id,family_id,weight,style,slices,bytes,status,error) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET family_id=excluded.family_id,weight=excluded.weight,style=excluded.style,slices=excluded.slices,bytes=excluded.bytes,status=excluded.status,error=excluded.error`, face.id, face.family, face.weight, face.style, string(raw), face.bytes, face.status, face.error); err != nil {
				return err
			}
			report.Faces++
		}
		for _, region := range rules {
			if _, err := tx.ExecContext(txCtx, `UPDATE typography_rules SET mode=?,family_id=?,weight=?,size_rem=?,line_height=?,letter_spacing_em=? WHERE region=?`, region.Mode, region.FamilyID, region.Weight, region.SizeRem, region.LineHeight, region.LetterSpacingEM, region.Region); err != nil {
				return err
			}
			report.Regions++
		}
		return nil
	})
	if err != nil {
		return report, err
	}
	// Generate only after the import transaction releases the single writer lock.
	page, err := readTypography(ctx, d.ReadPool())
	if err != nil {
		return report, err
	}
	css, err := buildCSS(ctx, d.ReadPool(), page.Regions, page.Fonts)
	if err != nil {
		return report, err
	}
	relative := "fonts/css/fonts." + digest([]byte(css))[:20] + ".css"
	if err := service.writeBlob(relative, []byte(css)); err != nil {
		return report, err
	}
	err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `UPDATE typography_state SET version=version+1,css_path=?,generated_at=? WHERE id=1`, "/media/"+relative, stamp(now))
		return err
	})
	return report, err
}
