package fonts

import (
	"context"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

const MaxPackageBytes = 64 << 20
const MaxSliceBytes = 8 << 20
const MaxSlices = 1024
const ChunkBytes = 128 << 10

type Service struct {
	d         *db.DB
	mediaDir  string
	uploadDir string
}

func NewService(d *db.DB, mediaDir string, uploadDir string) *Service {
	return &Service{d: d, mediaDir: mediaDir, uploadDir: uploadDir}
}

type Module struct{ svc *Service }

func NewModule(svc *Service) *Module { return &Module{svc: svc} }
func requireSuperuser(ctx *app.Ctx) error {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return api.Unauthorized("要先登录")
	}
	if !ctx.Viewer.Superuser {
		return api.Forbidden()
	}
	return nil
}

type Slice struct {
	Path         string `json:"path"`
	UnicodeRange string `json:"unicode_range"`
	SHA256       string `json:"sha256"`
	Bytes        int64  `json:"bytes"`
}
type Face struct {
	Status string  `json:"status,omitempty"`
	Error  string  `json:"error,omitempty"`
	Weight int     `json:"weight"`
	Style  string  `json:"style"`
	Slices []Slice `json:"slices"`
	Bytes  int64   `json:"bytes"`
}
type Font struct {
	ID          int64    `json:"id"`
	Family      string   `json:"family"`
	DisplayName string   `json:"display_name"`
	Source      string   `json:"source"`
	License     string   `json:"license"`
	Weights     []int    `json:"weights"`
	Status      string   `json:"status"`
	Bytes       int64    `json:"bytes"`
	Slices      int      `json:"slices"`
	Error       string   `json:"error"`
	UsedBy      []string `json:"used_by"`
	CreatedAt   string   `json:"created_at"`
	CanDelete   bool     `json:"can_delete"`
	CSSName     string   `json:"-"`
}
type FontList struct {
	Fonts []Font `json:"fonts"`
}
type FaceStats struct {
	Style  string `json:"style"`
	Status string `json:"status"`
	Error  string `json:"error"`
	Weight int    `json:"weight"`
	Files  int    `json:"files"`
	Bytes  int64  `json:"bytes"`
}
type FontDetail struct {
	Font   Font        `json:"font"`
	Slices []FaceStats `json:"slices"`
}
type ImportIn struct {
	Source           string `json:"source"`
	Family           string `json:"family,omitempty"`
	Weights          []int  `json:"weights,omitempty"`
	PackageName      string `json:"package_name,omitempty"`
	PackageBase64    string `json:"package_base64,omitempty"`
	UploadID         int64  `json:"upload_id,omitempty"`
	LicenseConfirmed bool   `json:"license_confirmed"`
}
type IDIn struct {
	ID api.ID `path:"id"`
}
type Result struct {
	Result string `json:"result"`
}

type Region struct {
	Region           string   `json:"region"`
	Label            string   `json:"label"`
	Mode             string   `json:"mode"`
	FamilyID         *int64   `json:"family_id"`
	Weight           int      `json:"weight"`
	SizeRem          *float64 `json:"size_rem"`
	LineHeight       *float64 `json:"line_height"`
	LetterSpacingEM  *float64 `json:"letter_spacing_em"`
	AvailableWeights []int    `json:"available_weights"`
	Slices           int      `json:"slices"`
	Bytes            int64    `json:"bytes"`
}
type TypographyValues struct {
	Regions []Region `json:"regions"`
}
type TypographyPage struct {
	Version     int64    `json:"version"`
	Regions     []Region `json:"regions"`
	Fonts       []Font   `json:"fonts"`
	Warnings    []string `json:"warnings"`
	CSSPath     string   `json:"css_path"`
	GeneratedAt *string  `json:"generated_at"`
}
type TypographyChanges struct {
	Regions *[]Region `json:"regions,omitempty"`
}
type PatchTypographyIn struct {
	BaseVersion int64             `json:"base_version"`
	Changes     TypographyChanges `json:"changes"`
}
type SaveOut struct {
	Values  *TypographyValues   `json:"values,omitempty"`
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	SavedAt string              `json:"saved_at"`
}

var regionOrder = []string{"body", "h1", "h2", "h3", "h4", "nav", "button", "numeric", "mono"}
var regionLabels = map[string]string{"body": "正文", "h1": "一级标题", "h2": "二级标题", "h3": "三级标题", "h4": "四级标题", "nav": "导航栏", "button": "按钮", "numeric": "数字与数据", "mono": "游戏 ID 与代码"}

func regionLabel(name string) string { return regionLabels[name] }
func validWeight(weight int) bool    { return weight >= 100 && weight <= 900 && weight%100 == 0 }
func stamp(at time.Time) string      { return db.FormatUTC(at.UTC()) }
func (s *Service) list(ctx *app.Ctx) (FontList, error) {
	if err := requireSuperuser(ctx); err != nil {
		return FontList{}, err
	}
	return readFonts(ctx.Context, s.d.ReadPool())
}
func (s *Service) detail(ctx *app.Ctx, id int64) (FontDetail, error) {
	if err := requireSuperuser(ctx); err != nil {
		return FontDetail{}, err
	}
	return readFont(ctx.Context, s.d.ReadPool(), id)
}

// CSSPointer lets the public page projector consume a generated same-origin stylesheet.
// No privileged font metadata or source references are exposed by this read.
func (s *Service) CSSPointer(ctx context.Context) (string, error) {
	var path string
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT css_path FROM typography_state WHERE id = 1`).Scan(&path)
	return path, err
}
