package fonts

import (
	"context"
	"fmt"
	"math"
	"strconv"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

var regionVars = map[string]string{"body": "body", "h1": "h1", "h2": "h2", "h3": "h3", "h4": "h4", "nav": "nav", "button": "button", "numeric": "numeric", "mono": "code"}
var regionSelectors = map[string]string{"body": "body", "h1": "h1", "h2": "h2", "h3": "h3", "h4": "h4, h5, h6", "nav": ".font-nav", "button": ".font-button, .c-btn", "numeric": ".font-numeric", "mono": ".font-code"}

func decimal(value float64) string { return strconv.FormatFloat(value, 'f', -1, 64) }
func elementRegion(name string) bool {
	return name == "body" || name == "h1" || name == "h2" || name == "h3" || name == "h4"
}
func (s *Service) typography(ctx *app.Ctx) (TypographyPage, error) {
	if err := requireSuperuser(ctx); err != nil {
		return TypographyPage{}, err
	}
	return readTypography(ctx.Context, s.d.ReadPool())
}
func validateRegions(regions []Region, fonts []Font) map[string][]string {
	fields := map[string][]string{}
	problem := func(region, field, message string) {
		key := "regions." + region + "." + field
		fields[key] = append(fields[key], message)
		fields["regions"] = append(fields["regions"], regionLabel(region)+"："+message)
	}
	if len(regions) != len(regionOrder) {
		fields["regions"] = []string{"请提交完整的九个排版区域。"}
		return fields
	}
	byID := map[int64]Font{}
	for _, font := range fonts {
		byID[font.ID] = font
	}
	seen := map[string]bool{}
	for _, region := range regions {
		if regionLabel(region.Region) == "" || seen[region.Region] {
			fields["regions"] = append(fields["regions"], "排版区域不正确或重复。")
			continue
		}
		seen[region.Region] = true
		if region.Mode != "system" && region.Mode != "inherit" && region.Mode != "custom" {
			problem(region.Region, "mode", "请选择有效字体来源。")
		}
		if region.Region == "body" && region.Mode == "inherit" {
			problem(region.Region, "mode", "正文区域不能选「跟随正文」。")
		}
		if !validWeight(region.Weight) {
			problem(region.Region, "weight", "字重必须为100至900的整百数。")
		}
		if region.Mode == "custom" {
			if region.FamilyID == nil {
				problem(region.Region, "family_id", "选择「字体库中的字体」时必须指定字体。")
			} else {
				font, exists := byID[*region.FamilyID]
				if !exists || font.Status != "ready" {
					problem(region.Region, "family_id", "字体不存在或未准备好。")
				} else {
					available := false
					for _, weight := range font.Weights {
						if weight == region.Weight {
							available = true
						}
					}
					if !available {
						problem(region.Region, "weight", "这个字体没有处理完成的该字重，请先处理或换一个字重。")
					}
				}
			}
		}
		for _, rangeCheck := range []struct {
			field    string
			value    *float64
			min, max float64
		}{{"size_rem", region.SizeRem, -99.999, 99.999}, {"line_height", region.LineHeight, -99.99, 99.99}, {"letter_spacing_em", region.LetterSpacingEM, -99.999, 99.999}} {
			if rangeCheck.value != nil {
				value := *rangeCheck.value
				if math.IsNaN(value) || math.IsInf(value, 0) || value < rangeCheck.min || value > rangeCheck.max {
					problem(region.Region, rangeCheck.field, "数值超出允许范围。")
				}
			}
		}
	}
	return fields
}
func normalizeRegions(input []Region) []Region {
	byName := map[string]Region{}
	for _, region := range input {
		region.Label = regionLabel(region.Region)
		region.AvailableWeights = []int{}
		region.Slices = 0
		region.Bytes = 0
		if region.Mode != "custom" {
			region.FamilyID = nil
		}
		byName[region.Region] = region
	}
	out := []Region{}
	for _, name := range regionOrder {
		out = append(out, byName[name])
	}
	return out
}
func effectiveID(region Region, bodyID *int64) *int64 {
	if region.Mode == "custom" {
		return region.FamilyID
	}
	if region.Mode == "inherit" {
		return bodyID
	}
	return nil
}
func buildCSS(ctx context.Context, q db.DBTX, regions []Region, fonts []Font) (string, error) {
	byID := map[int64]Font{}
	for _, font := range fonts {
		byID[font.ID] = font
	}
	var bodyID *int64
	for _, region := range regions {
		if region.Region == "body" && region.Mode == "custom" {
			bodyID = region.FamilyID
		}
	}
	var result strings.Builder
	result.WriteString("/* 由「设置 → 排版设置」生成，请勿手工编辑。 */\n")
	emitted := map[string]bool{}
	facesByID := map[int64][]Face{}
	for _, region := range regions {
		family := effectiveID(region, bodyID)
		if family == nil {
			continue
		}
		pair := fmt.Sprintf("%d/%d", *family, region.Weight)
		if emitted[pair] {
			continue
		}
		emitted[pair] = true
		faces, exists := facesByID[*family]
		if !exists {
			var err error
			faces, err = readFaces(ctx, q, *family)
			if err != nil {
				return "", err
			}
			facesByID[*family] = faces
		}
		font, exists := byID[*family]
		if !exists {
			return "", api.Invalid("排版引用了不存在的字体。")
		}
		for _, face := range faces {
			if face.Weight != region.Weight || face.Style != "normal" || face.Status != "ready" {
				continue
			}
			for _, slice := range face.Slices {
				if !cleanEntry(slice.Path) || !strings.HasPrefix(slice.Path, "fonts/") || !strings.HasSuffix(slice.Path, ".woff2") || !validUnicodeRange(slice.UnicodeRange) {
					return "", api.Invalid("已保存的字体分片元数据不正确。")
				}
				result.WriteString("@font-face {\n")
				result.WriteString(fmt.Sprintf("  font-family: %q;\n  font-weight: %d;\n  font-style: normal;\n  font-display: swap;\n  src: url(%q) format(\"woff2\");\n", font.CSSName, face.Weight, "/media/"+slice.Path))
				if slice.UnicodeRange != "" {
					result.WriteString("  unicode-range: " + slice.UnicodeRange + ";\n")
				}
				result.WriteString("}\n")
			}
		}
	}
	variables := []string{}
	rules := []string{}
	for _, region := range regions {
		suffix := regionVars[region.Region]
		fallback := "var(--font-fallback)"
		if region.Region == "mono" {
			fallback = "var(--font-mono-fallback)"
		}
		family := fallback
		if region.Mode == "inherit" {
			family = "var(--font-body)"
		}
		if region.Mode == "custom" && region.FamilyID != nil {
			family = fmt.Sprintf("%q, %s", byID[*region.FamilyID].CSSName, fallback)
		}
		variables = append(variables, "  --font-"+suffix+": "+family+";")
		if region.Region == "numeric" && region.Mode == "custom" {
			variables = append(variables, "  --font-figure: "+family+";")
		}
		declarations := []string{}
		if elementRegion(region.Region) {
			variables = append(variables, fmt.Sprintf("  --font-%s-weight: %d;", suffix, region.Weight))
			if region.SizeRem != nil {
				variables = append(variables, "  --font-"+suffix+"-size: "+decimal(*region.SizeRem)+"rem;")
			}
		} else {
			if region.Mode == "custom" {
				declarations = append(declarations, fmt.Sprintf("  font-weight: %d;", region.Weight))
			}
			if region.SizeRem != nil {
				declarations = append(declarations, "  font-size: "+decimal(*region.SizeRem)+"rem;")
			}
		}
		if region.LineHeight != nil {
			declarations = append(declarations, "  line-height: "+decimal(*region.LineHeight)+";")
		}
		if region.LetterSpacingEM != nil {
			declarations = append(declarations, "  letter-spacing: "+decimal(*region.LetterSpacingEM)+"em;")
		}
		if len(declarations) > 0 {
			rules = append(rules, regionSelectors[region.Region]+" {\n"+strings.Join(declarations, "\n")+"\n}")
		}
	}
	result.WriteString(":root {\n" + strings.Join(variables, "\n") + "\n}\n")
	for _, rule := range rules {
		result.WriteString(rule + "\n")
	}
	return result.String(), nil
}
func (s *Service) patchTypography(ctx *app.Ctx, in PatchTypographyIn) (SaveOut, error) {
	out := SaveOut{Saved: []string{}, Fields: map[string][]string{}, SavedAt: stamp(ctx.Now())}
	if err := requireSuperuser(ctx); err != nil {
		return out, err
	}
	current, err := readTypography(ctx.Context, s.d.ReadPool())
	if err != nil {
		return out, err
	}
	out.Version = current.Version
	if in.BaseVersion != current.Version {
		return out, api.Stale(map[string]any{"version": current.Version, "values": TypographyValues{Regions: current.Regions}})
	}
	if in.Changes.Regions == nil {
		return out, nil
	}
	fields := validateRegions(*in.Changes.Regions, current.Fonts)
	if len(fields) > 0 {
		return out, api.InvalidFields(fields)
	}
	regions := normalizeRegions(*in.Changes.Regions)
	css, err := buildCSS(ctx.Context, s.d.ReadPool(), regions, current.Fonts)
	if err != nil {
		return out, err
	}
	path := "fonts/css/fonts." + digest([]byte(css))[:20] + ".css"
	if err := s.writeBlob(path, []byte(css)); err != nil {
		return out, err
	}
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		latest, err := readTypography(txCtx, tx)
		if err != nil {
			return err
		}
		if latest.Version != in.BaseVersion {
			return api.Stale(map[string]any{"version": latest.Version, "values": TypographyValues{Regions: latest.Regions}})
		}
		if problems := validateRegions(regions, latest.Fonts); len(problems) > 0 {
			return api.InvalidFields(problems)
		}
		for _, region := range regions {
			if _, err := tx.ExecContext(txCtx, `UPDATE typography_rules SET mode=?,family_id=?,weight=?,size_rem=?,line_height=?,letter_spacing_em=? WHERE region=?`, region.Mode, region.FamilyID, region.Weight, region.SizeRem, region.LineHeight, region.LetterSpacingEM, region.Region); err != nil {
				return err
			}
		}
		if _, err := tx.ExecContext(txCtx, `UPDATE typography_state SET version=version+1,css_path=?,generated_at=? WHERE id=1`, "/media/"+path, stamp(ctx.Now())); err != nil {
			return err
		}
		out.Version = latest.Version + 1
		out.Saved = []string{"regions"}
		out.Values = &TypographyValues{Regions: regions}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "typography.update", "typography", 1, map[string]any{"version": out.Version, "css_path": "/media/" + path}, ctx.Now())
	})
	return out, err
}

type PreviewIn struct {
	Regions []Region `json:"regions"`
}
type PreviewOut struct {
	CSSPath string `json:"css_path"`
}

func (s *Service) preview(ctx *app.Ctx, in PreviewIn) (PreviewOut, error) {
	if err := requireSuperuser(ctx); err != nil {
		return PreviewOut{}, err
	}
	fonts, err := readFonts(ctx.Context, s.d.ReadPool())
	if err != nil {
		return PreviewOut{}, err
	}
	if fields := validateRegions(in.Regions, fonts.Fonts); len(fields) > 0 {
		return PreviewOut{}, api.InvalidFields(fields)
	}
	css, err := buildCSS(ctx.Context, s.d.ReadPool(), normalizeRegions(in.Regions), fonts.Fonts)
	if err != nil {
		return PreviewOut{}, err
	}
	css = strings.ReplaceAll(css, ":root {", "#typography-preview {")
	for _, region := range regionOrder {
		selector := regionSelectors[region]
		css = strings.ReplaceAll(css, selector+" {", "#typography-preview "+strings.ReplaceAll(selector, ", ", ", #typography-preview ")+" {")
	}
	// Font families are normally supplied by the main styles package. The scoped
	// preview consumes the draft variables while leaving the rest of admin intact.
	for _, region := range regionOrder {
		selectors := map[string]string{"body": ".p-body", "h1": ".p-h1", "h2": ".p-h2", "h3": ".p-h3", "h4": ".p-h4", "nav": ".p-nav", "button": ".p-button", "numeric": ".p-numeric", "mono": ".p-code"}
		declarations := "font-family: var(--font-" + regionVars[region] + ");"
		for _, setting := range in.Regions {
			if setting.Region == region {
				declarations += fmt.Sprintf(" font-weight: %d;", setting.Weight)
				if setting.SizeRem != nil {
					declarations += " font-size: " + decimal(*setting.SizeRem) + "rem;"
				}
				if setting.LineHeight != nil {
					declarations += " line-height: " + decimal(*setting.LineHeight) + ";"
				}
				if setting.LetterSpacingEM != nil {
					declarations += " letter-spacing: " + decimal(*setting.LetterSpacingEM) + "em;"
				}
			}
		}
		css += "#typography-preview " + selectors[region] + " { " + declarations + " }\n"
	}
	relative := "fonts/css/preview." + digest([]byte(css))[:20] + ".css"
	if err := s.writeBlob(relative, []byte(css)); err != nil {
		return PreviewOut{}, err
	}
	return PreviewOut{CSSPath: "/media/" + relative}, nil
}
