package media

import (
	"bytes"
	"context"
	"database/sql"
	"errors"
	"fmt"
	"image"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/gen2brain/webp"
	"golang.org/x/image/draw"
	_ "golang.org/x/image/webp"
)

// AllowedSpecs 是允许生成的缩略图规格白名单（12 号文档 5.13）。
var AllowedSpecs = map[string]struct {
	Mode string // "fill" 或 "max"
	W    int
	H    int
}{
	"fill-88x88":     {Mode: "fill", W: 88, H: 88},
	"fill-176x176":   {Mode: "fill", W: 176, H: 176},
	"fill-288x288":   {Mode: "fill", W: 288, H: 288},
	"fill-400x400":   {Mode: "fill", W: 400, H: 400},
	"fill-960x540":   {Mode: "fill", W: 960, H: 540},
	"fill-1280x720":  {Mode: "fill", W: 1280, H: 720},
	"fill-2400x1200": {Mode: "fill", W: 2400, H: 1200},
	"fill-2400x640":  {Mode: "fill", W: 2400, H: 640},
	"fill-2400x1350": {Mode: "fill", W: 2400, H: 1350},
	"max-1600x1600":  {Mode: "max", W: 1600, H: 1600},
	"fill-1200x630":  {Mode: "fill", W: 1200, H: 630},
}

const (
	MaxFileSize    = 10 * 1024 * 1024 // 10MB 单文件上限
	MaxPixels      = 40_000_000       // 4000 万像素上限
	MasterLongSide = 2560             // 母版最长边上限
)

// Image 表示媒体图片记录。
type Image struct {
	ID           int64     `json:"id"`
	CollectionID *int64    `json:"collection_id"`
	Title        string    `json:"title"`
	FileName     string    `json:"file_name"`
	FileSize     int64     `json:"file_size"`
	Width        int       `json:"width"`
	Height       int       `json:"height"`
	UploaderID   *int64    `json:"uploader_id"`
	CreatedAt    time.Time `json:"created_at"`
	Version      int64     `json:"version"`
}

// Collection 表示图片集合。
type Collection struct {
	ID        int64     `json:"id"`
	Name      string    `json:"name"`
	Key       string    `json:"key"`
	CreatedAt time.Time `json:"created_at"`
}

// Service 提供图片处理与存储。
type Service struct {
	db       *db.DB
	dataDir  string // data 卷，保存 originals/<id>.webp
	mediaDir string // media 卷，保存 r/<id>/<spec>.webp
	sem      sync.Mutex
}

// NewService 创建媒体服务。
func NewService(database *db.DB, dataDir, mediaDir string) *Service {
	_ = os.MkdirAll(filepath.Join(dataDir, "originals"), 0o755)
	_ = os.MkdirAll(filepath.Join(mediaDir, "r"), 0o755)
	return &Service{
		db:       database,
		dataDir:  dataDir,
		mediaDir: mediaDir,
	}
}

// MasterPath 返回母版图片物理路径。
func (s *Service) MasterPath(id int64) string {
	return filepath.Join(s.dataDir, "originals", fmt.Sprintf("%d.webp", id))
}

// ThumbnailPath 返回缩略图物理路径。
func (s *Service) ThumbnailPath(id int64, spec string) string {
	return filepath.Join(s.mediaDir, "r", strconv.FormatInt(id, 10), fmt.Sprintf("%s.webp", spec))
}

// UploadInput 上传图片参数。
type UploadInput struct {
	Title         string
	FileName      string
	CollectionKey string
	Reader        io.Reader
	FileSize      int64
}

// Upload 处理图片上传流水线（12 号文档 5.13）。
func (s *Service) Upload(ctx *app.Ctx, in UploadInput) (*Image, error) {
	if in.FileSize > MaxFileSize {
		return nil, api.Invalid("图片大小不能超过 10MB")
	}

	// 读取到内存进行格式和尺寸探测
	data, err := io.ReadAll(io.LimitReader(in.Reader, MaxFileSize+1))
	if err != nil {
		return nil, errors.New("读取上传数据失败")
	}
	if int64(len(data)) > MaxFileSize {
		return nil, api.Invalid("图片大小不能超过 10MB")
	}

	// 1. 文件头嗅探尺寸与格式，不完整解码
	cfg, format, err := image.DecodeConfig(bytes.NewReader(data))
	if err != nil {
		return nil, api.Invalid("不支持的图片格式或文件已损坏")
	}
	if format != "jpeg" && format != "png" && format != "webp" {
		return nil, api.Invalid("仅支持 JPG、PNG 或 WebP 格式图片")
	}
	if cfg.Width <= 0 || cfg.Height <= 0 {
		return nil, api.Invalid("无效的图片尺寸")
	}
	if int64(cfg.Width)*int64(cfg.Height) > MaxPixels {
		return nil, api.Invalid("图片像素超过 4000 万像素上限")
	}
	if cfg.Width < 10 || cfg.Height < 10 {
		return nil, api.Invalid("图片尺寸过小（最少 10x10 像素）")
	}

	// 2. 信号量里完整解码并编码母版
	s.sem.Lock()
	defer s.sem.Unlock()

	img, _, err := image.Decode(bytes.NewReader(data))
	if err != nil {
		return nil, api.Invalid("图片数据解析失败")
	}

	// 长边缩放到 MasterLongSide
	w, h := img.Bounds().Dx(), img.Bounds().Dy()
	if w > MasterLongSide || h > MasterLongSide {
		if w >= h {
			h = h * MasterLongSide / w
			w = MasterLongSide
		} else {
			w = w * MasterLongSide / h
			h = MasterLongSide
		}
		scaled := image.NewRGBA(image.Rect(0, 0, w, h))
		draw.CatmullRom.Scale(scaled, scaled.Bounds(), img, img.Bounds(), draw.Src, nil)
		img = scaled
	}

	// 编码为 WebP 母版（quality 90, method 2）
	var masterBuf bytes.Buffer
	if err := webp.Encode(&masterBuf, img, webp.Options{Quality: 90, Method: 2}); err != nil {
		return nil, errors.New("母版转码失败")
	}

	// 3. 查 collection ID
	var collectionID *int64
	if in.CollectionKey != "" {
		var colID int64
		err := s.db.ReadPool().QueryRowContext(ctx.Context, `SELECT id FROM image_collections WHERE key = ?`, in.CollectionKey).Scan(&colID)
		if err == nil {
			collectionID = &colID
		}
	}

	title := in.Title
	if title == "" {
		title = in.FileName
	}
	if title == "" {
		title = "未命名图片"
	}

	var uploaderID *int64
	if ctx.Viewer != nil && ctx.Viewer.ID > 0 {
		uid := ctx.Viewer.ID
		uploaderID = &uid
	}

	now := ctx.Now().UTC().Format(time.RFC3339Nano)
	masterBytes := masterBuf.Bytes()
	var imgRecord Image

	// 4. 插入数据库
	err = s.db.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `
			INSERT INTO images (collection_id, title, file_name, file_size, width, height, uploader_id, created_at, version)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
		`, collectionID, title, in.FileName, len(masterBytes), w, h, uploaderID, now)
		if err != nil {
			return err
		}
		id, err := res.LastInsertId()
		if err != nil {
			return err
		}
		imgRecord = Image{
			ID:           id,
			CollectionID: collectionID,
			Title:        title,
			FileName:     in.FileName,
			FileSize:     int64(len(masterBytes)),
			Width:        w,
			Height:       h,
			UploaderID:   uploaderID,
			CreatedAt:    ctx.Now().UTC(),
			Version:      1,
		}
		return nil
	})
	if err != nil {
		return nil, fmt.Errorf("保存图片信息失败: %w", err)
	}

	// 5. 写入母版文件（原子重命名）
	targetPath := s.MasterPath(imgRecord.ID)
	tmpPath := targetPath + ".tmp"
	if err := os.WriteFile(tmpPath, masterBytes, 0o644); err != nil {
		return nil, errors.New("写入母版失败")
	}
	if err := os.Rename(tmpPath, targetPath); err != nil {
		return nil, errors.New("保存母版失败")
	}

	return &imgRecord, nil
}

// GetImageByID 获取图片信息。
func (s *Service) GetImageByID(ctx context.Context, id int64) (*Image, error) {
	var img Image
	var colID, upID sql.NullInt64
	var createdAt string
	err := s.db.ReadPool().QueryRowContext(ctx, `
		SELECT id, collection_id, title, file_name, file_size, width, height, uploader_id, created_at, version
		FROM images WHERE id = ?
	`, id).Scan(&img.ID, &colID, &img.Title, &img.FileName, &img.FileSize, &img.Width, &img.Height, &upID, &createdAt, &img.Version)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, api.NotFound("图片不存在")
		}
		return nil, errors.New("查询图片失败")
	}
	if colID.Valid {
		img.CollectionID = &colID.Int64
	}
	if upID.Valid {
		img.UploaderID = &upID.Int64
	}
	t, _ := time.Parse(time.RFC3339Nano, createdAt)
	img.CreatedAt = t
	return &img, nil
}

// RenderThumbnail 在信号量中生成缩略图（若已存在直接返回）。
func (s *Service) RenderThumbnail(ctx context.Context, id int64, spec string) (string, error) {
	specConfig, ok := AllowedSpecs[spec]
	if !ok {
		return "", api.Invalid("不支持的图片规格")
	}

	thumbPath := s.ThumbnailPath(id, spec)
	if _, err := os.Stat(thumbPath); err == nil {
		return thumbPath, nil
	}

	masterPath := s.MasterPath(id)
	masterFile, err := os.Open(masterPath)
	if err != nil {
		return "", api.NotFound("原图不存在")
	}
	defer masterFile.Close()

	s.sem.Lock()
	defer s.sem.Unlock()

	// 再次检查，避免排队期间其他协程已生成
	if _, err := os.Stat(thumbPath); err == nil {
		return thumbPath, nil
	}

	masterImg, err := webp.Decode(masterFile)
	if err != nil {
		return "", errors.New("解析原图失败")
	}

	var dst *image.RGBA
	targetW, targetH := specConfig.W, specConfig.H

	if specConfig.Mode == "fill" {
		// 居中裁剪并缩放
		sb := masterImg.Bounds()
		cw, ch := sb.Dx(), sb.Dy()
		if cw*targetH > ch*targetW {
			cw = ch * targetW / targetH
		} else {
			ch = cw * targetH / targetW
		}
		crop := image.Rect(sb.Min.X+(sb.Dx()-cw)/2, sb.Min.Y+(sb.Dy()-ch)/2, 0, 0)
		crop.Max = image.Pt(crop.Min.X+cw, crop.Min.Y+ch)
		dst = image.NewRGBA(image.Rect(0, 0, targetW, targetH))
		draw.CatmullRom.Scale(dst, dst.Bounds(), masterImg, crop, draw.Src, nil)
	} else {
		// max 模式按比例适应
		sb := masterImg.Bounds()
		w, h := sb.Dx(), sb.Dy()
		if w*targetH > h*targetW {
			targetH = h * targetW / w
		} else {
			targetW = w * targetH / h
		}
		if targetW < 1 {
			targetW = 1
		}
		if targetH < 1 {
			targetH = 1
		}
		dst = image.NewRGBA(image.Rect(0, 0, targetW, targetH))
		draw.CatmullRom.Scale(dst, dst.Bounds(), masterImg, sb, draw.Src, nil)
	}

	var thumbBuf bytes.Buffer
	if err := webp.Encode(&thumbBuf, dst, webp.Options{Quality: 80, Method: 2}); err != nil {
		return "", errors.New("生成缩略图失败")
	}

	dir := filepath.Dir(thumbPath)
	_ = os.MkdirAll(dir, 0o755)

	tmpPath := thumbPath + ".tmp"
	if err := os.WriteFile(tmpPath, thumbBuf.Bytes(), 0o644); err != nil {
		return "", errors.New("保存缩略图失败")
	}
	if err := os.Rename(tmpPath, thumbPath); err != nil {
		return "", errors.New("保存缩略图失败")
	}

	return thumbPath, nil
}

// DeleteImage 删除图片及其母版和缩略图。
func (s *Service) DeleteImage(ctx *app.Ctx, id int64) error {
	// 检查是否有引用（例如文章封面）
	var refCount int
	err := s.db.ReadPool().QueryRowContext(ctx.Context, `SELECT COUNT(*) FROM articles WHERE cover_image_id = ?`, id).Scan(&refCount)
	if err != nil {
		return errors.New("检查图片引用失败")
	}
	if refCount > 0 {
		return api.Invalid(fmt.Sprintf("该图片正被 %d 篇文章作为封面使用，无法删除", refCount))
	}

	err = s.db.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `DELETE FROM images WHERE id = ?`, id)
		if err != nil {
			return err
		}
		affected, _ := res.RowsAffected()
		if affected == 0 {
			return api.NotFound("图片不存在")
		}
		return nil
	})
	if err != nil {
		return err
	}

	// 删除文件
	_ = os.Remove(s.MasterPath(id))
	_ = os.RemoveAll(filepath.Join(s.mediaDir, "r", strconv.FormatInt(id, 10)))
	return nil
}
