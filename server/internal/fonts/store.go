package fonts

import (
	"context"
	"database/sql"
	"encoding/json"
	"sort"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func readFonts(ctx context.Context, q db.DBTX) (FontList, error) {
	out := FontList{Fonts: []Font{}, FacesCSSURL: "/api/admin/fonts/faces.css"}
	rows, err := q.QueryContext(ctx, `SELECT f.id,f.family,f.display_name,f.css_name,f.source,f.license,f.status,f.error,f.created_at,f.source_ref,f.license_type,f.license_note,COALESCE(u.nickname,'—') FROM font_families f LEFT JOIN users u ON u.id=f.created_by ORDER BY f.display_name,f.id`)
	if err != nil {
		return out, err
	}
	index := map[int64]int{}
	for rows.Next() {
		var font Font
		font.Weights, font.UsedBy = []int{}, []string{}
		if err := rows.Scan(&font.ID, &font.Family, &font.DisplayName, &font.CSSName, &font.Source, &font.License, &font.Status, &font.Error, &font.CreatedAt, &font.SourceRef, &font.LicenseType, &font.LicenseNote, &font.CreatedByName); err != nil {
			rows.Close()
			return out, err
		}
		index[font.ID] = len(out.Fonts)
		out.Fonts = append(out.Fonts, font)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return out, err
	}
	rows, err = q.QueryContext(ctx, `SELECT family_id,weight,style,slices,bytes FROM font_faces WHERE status='ready' ORDER BY family_id,weight,style`)
	if err != nil {
		return out, err
	}
	for rows.Next() {
		var id int64
		var weight int
		var style, raw string
		var bytes int64
		if err := rows.Scan(&id, &weight, &style, &raw, &bytes); err != nil {
			rows.Close()
			return out, err
		}
		var slices []Slice
		if err := json.Unmarshal([]byte(raw), &slices); err != nil {
			rows.Close()
			return out, err
		}
		if position, ok := index[id]; ok {
			font := &out.Fonts[position]
			if style == "normal" {
				font.Weights = append(font.Weights, weight)
			}
			font.Bytes += bytes
			font.Slices += len(slices)
		}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return out, err
	}
	regions, err := readRegions(ctx, q)
	if err != nil {
		return out, err
	}
	var bodyID *int64
	for _, region := range regions {
		if region.Region == "body" && region.Mode == "custom" {
			bodyID = region.FamilyID
		}
	}
	for _, region := range regions {
		family := region.FamilyID
		if region.Mode == "inherit" {
			family = bodyID
		}
		if region.Mode == "system" || family == nil {
			continue
		}
		if position, ok := index[*family]; ok {
			out.Fonts[position].UsedBy = append(out.Fonts[position].UsedBy, regionLabel(region.Region))
		}
	}
	for i := range out.Fonts {
		if len(out.Fonts[i].Weights) == 0 {
			out.Fonts[i].Status = "unavailable"
		}
		out.Fonts[i].CanDelete = len(out.Fonts[i].UsedBy) == 0
		sort.Ints(out.Fonts[i].Weights)
	}
	return out, nil
}
func readFaces(ctx context.Context, q db.DBTX, id int64) ([]Face, error) {
	rows, err := q.QueryContext(ctx, `SELECT id,weight,style,slices,bytes,status,error,glyph_count FROM font_faces WHERE family_id=? ORDER BY weight,style`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Face{}
	for rows.Next() {
		var face Face
		var raw string
		if err := rows.Scan(&face.ID, &face.Weight, &face.Style, &raw, &face.Bytes, &face.Status, &face.Error, &face.GlyphCount); err != nil {
			return nil, err
		}
		if err := json.Unmarshal([]byte(raw), &face.Slices); err != nil {
			return nil, err
		}
		out = append(out, face)
	}
	return out, rows.Err()
}
func readFont(ctx context.Context, q db.DBTX, id int64) (FontDetail, error) {
	out := FontDetail{Slices: []FaceStats{}, FacesCSSURL: "/api/admin/fonts/faces.css"}
	all, err := readFonts(ctx, q)
	if err != nil {
		return out, err
	}
	found := false
	for _, font := range all.Fonts {
		if font.ID == id {
			out.Font = font
			found = true
			break
		}
	}
	if !found {
		return out, api.NotFound("字体不存在")
	}
	faces, err := readFaces(ctx, q, id)
	if err != nil {
		return out, err
	}
	regions, err := readRegions(ctx, q)
	if err != nil {
		return out, err
	}
	used := usedFacePairs(regions)
	for _, face := range faces {
		out.Slices = append(out.Slices, FaceStats{GlyphCount: face.GlyphCount, ID: face.ID, CanDelete: !used[facePair{family: id, weight: face.Weight}], Style: face.Style, Status: face.Status, Error: face.Error, Weight: face.Weight, Files: len(face.Slices), Bytes: face.Bytes})
	}
	return out, nil
}
func readRegions(ctx context.Context, q db.DBTX) ([]Region, error) {
	rows, err := q.QueryContext(ctx, `SELECT region,mode,family_id,weight,size_rem,line_height,letter_spacing_em FROM typography_rules`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	byName := map[string]Region{}
	for rows.Next() {
		var region Region
		region.AvailableWeights = []int{}
		if err := rows.Scan(&region.Region, &region.Mode, &region.FamilyID, &region.Weight, &region.SizeRem, &region.LineHeight, &region.LetterSpacingEM); err != nil {
			return nil, err
		}
		region.Label = regionLabel(region.Region)
		byName[region.Region] = region
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	out := []Region{}
	for _, name := range regionOrder {
		if region, ok := byName[name]; ok {
			out = append(out, region)
		}
	}
	return out, nil
}
func readTypography(ctx context.Context, q db.DBTX) (TypographyPage, error) {
	out := TypographyPage{Regions: []Region{}, Fonts: []Font{}, Warnings: []string{}}
	err := q.QueryRowContext(ctx, `SELECT version,css_path,generated_at FROM typography_state WHERE id=1`).Scan(&out.Version, &out.CSSPath, &out.GeneratedAt)
	if err == sql.ErrNoRows {
		return out, api.NotFound("排版设置不存在")
	}
	if err != nil {
		return out, err
	}
	if out.Regions, err = readRegions(ctx, q); err != nil {
		return out, err
	}
	list, err := readFonts(ctx, q)
	if err != nil {
		return out, err
	}
	out.Fonts = list.Fonts
	byID := map[int64]Font{}
	for _, font := range list.Fonts {
		byID[font.ID] = font
	}
	var bodyID *int64
	for _, region := range out.Regions {
		if region.Region == "body" && region.Mode == "custom" {
			bodyID = region.FamilyID
		}
	}
	for i := range out.Regions {
		region := &out.Regions[i]
		family := region.FamilyID
		if region.Mode == "inherit" {
			family = bodyID
		}
		if region.Mode == "system" || family == nil {
			region.AvailableWeights = []int{100, 200, 300, 400, 500, 600, 700, 800, 900}
			continue
		}
		font, ok := byID[*family]
		if !ok {
			out.Warnings = append(out.Warnings, region.Label+"选择的字体不存在。")
			continue
		}
		region.AvailableWeights = append([]int{}, font.Weights...)
		region.Bytes = font.Bytes
		region.Slices = font.Slices
	}
	return out, nil
}
