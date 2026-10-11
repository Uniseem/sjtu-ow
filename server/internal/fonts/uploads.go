package fonts

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/base64"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type BeginUploadIn struct {
	Name             string `json:"name"`
	TotalBytes       int64  `json:"total_bytes"`
	LicenseConfirmed bool   `json:"license_confirmed"`
}
type UploadOut struct {
	ID         int64  `json:"id"`
	TotalBytes int64  `json:"total_bytes"`
	ChunkSize  int    `json:"chunk_size"`
	ExpiresAt  string `json:"expires_at"`
}
type UploadChunkIn struct {
	ID         api.ID `path:"id"`
	Offset     int64  `json:"offset"`
	DataBase64 string `json:"data_base64"`
}
type upload struct {
	id      int64
	token   string
	owner   int64
	name    string
	total   int64
	expires string
}

func readUpload(ctx context.Context, q db.DBTX, id, owner int64, now time.Time) (upload, error) {
	var result upload
	var state string
	err := q.QueryRowContext(ctx, `SELECT id,token,owner_id,name,total_bytes,expires_at,state FROM font_uploads WHERE id=? AND owner_id=?`, id, owner).Scan(&result.id, &result.token, &result.owner, &result.name, &result.total, &result.expires, &state)
	if err == sql.ErrNoRows {
		return result, api.NotFound("上传记录不存在")
	}
	if err != nil {
		return result, err
	}
	expires, err := db.ParseUTC(result.expires)
	if err != nil {
		return result, err
	}
	if !now.Before(expires) || state != "open" {
		return result, api.Invalid("字体上传已过期或已完成，请重新上传。")
	}
	return result, nil
}
func uploadResponse(value upload) UploadOut {
	return UploadOut{ID: value.id, TotalBytes: value.total, ChunkSize: ChunkBytes, ExpiresAt: value.expires}
}
func (s *Service) uploadRoot() (*os.Root, error) {
	directory := s.uploadDir
	if directory == "" {
		directory = filepath.Join(filepath.Dir(s.mediaDir), "fontuploads")
	}
	if err := os.MkdirAll(directory, 0700); err != nil {
		return nil, err
	}
	return os.OpenRoot(directory)
}
func (s *Service) beginUpload(ctx *app.Ctx, in BeginUploadIn) (UploadOut, error) {
	if err := requireSuperuser(ctx); err != nil {
		return UploadOut{}, err
	}
	if !in.LicenseConfirmed {
		return UploadOut{}, api.InvalidFields(map[string][]string{"license_confirmed": {"请确认允许本站网页嵌入。"}})
	}
	if in.TotalBytes < 1 || in.TotalBytes > MaxPackageBytes {
		return UploadOut{}, api.Invalid("成品包大小不正确，最大64MB。")
	}
	if len(in.Name) > 200 || path.Base(in.Name) != in.Name {
		return UploadOut{}, api.Invalid("成品包文件名不正确。")
	}
	token, err := randomToken()
	if err != nil {
		return UploadOut{}, err
	}
	value := upload{token: token, owner: ctx.Viewer.ID, name: in.Name, total: in.TotalBytes, expires: stamp(ctx.Now().Add(time.Hour))}
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		var count int
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM font_uploads WHERE owner_id=? AND state='open' AND expires_at>?`, value.owner, stamp(ctx.Now())).Scan(&count); err != nil {
			return err
		}
		if count >= 3 {
			return api.Invalid("同时最多上传3份成品包，请等待已打开的上传记录过期。")
		}
		result, err := tx.ExecContext(txCtx, `INSERT INTO font_uploads(owner_id,token,name,total_bytes,created_at,expires_at) VALUES(?,?,?,?,?,?)`, value.owner, value.token, value.name, value.total, stamp(ctx.Now()), value.expires)
		if err != nil {
			return err
		}
		value.id, err = result.LastInsertId()
		return err
	})
	return uploadResponse(value), err
}
func (s *Service) uploadChunk(ctx *app.Ctx, in UploadChunkIn) (UploadOut, error) {
	if err := requireSuperuser(ctx); err != nil {
		return UploadOut{}, err
	}
	value, err := readUpload(ctx.Context, s.d.ReadPool(), int64(in.ID), ctx.Viewer.ID, ctx.Now())
	if err != nil {
		return UploadOut{}, err
	}
	if in.Offset < 0 || in.Offset >= value.total || in.Offset%ChunkBytes != 0 {
		return UploadOut{}, api.Invalid("分块位置不正确。")
	}
	if len(in.DataBase64) > base64.StdEncoding.EncodedLen(ChunkBytes) {
		return UploadOut{}, api.Invalid("字体分块超过128KB。")
	}
	data, err := base64.StdEncoding.Strict().DecodeString(in.DataBase64)
	if err != nil {
		return UploadOut{}, api.Invalid("字体分块编码不正确。")
	}
	expected := int64(ChunkBytes)
	if remaining := value.total - in.Offset; remaining < expected {
		expected = remaining
	}
	if int64(len(data)) != expected {
		return UploadOut{}, api.Invalid("字体分块长度不正确。")
	}
	root, err := s.uploadRoot()
	if err != nil {
		return UploadOut{}, err
	}
	defer root.Close()
	if err := root.MkdirAll(value.token, 0700); err != nil {
		return UploadOut{}, err
	}
	relative := fmt.Sprintf("%s/%d.chunk", value.token, in.Offset)
	// Publish the completed chunk through an exclusive hard link. Readers never
	// see a partially written file, and concurrent retries cannot overwrite bytes.
	token, err := randomToken()
	if err != nil {
		return UploadOut{}, err
	}
	temporary := relative + ".tmp-" + token
	file, err := root.OpenFile(temporary, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return UploadOut{}, err
	}
	defer root.Remove(temporary)
	if _, err := file.Write(data); err != nil {
		file.Close()
		return UploadOut{}, err
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return UploadOut{}, err
	}
	if err := file.Close(); err != nil {
		return UploadOut{}, err
	}
	err = root.Link(temporary, relative)
	if os.IsExist(err) {
		existing, err := root.Open(relative)
		if err != nil {
			return UploadOut{}, err
		}
		defer existing.Close()
		bytesBefore, err := io.ReadAll(io.LimitReader(existing, ChunkBytes+1))
		if err != nil {
			return UploadOut{}, err
		}
		if !bytes.Equal(bytesBefore, data) {
			return UploadOut{}, api.Invalid("这个位置已有不同的分块，请重新开始上传。")
		}
	} else if err != nil {
		return UploadOut{}, err
	}

	return uploadResponse(value), nil
}
func (s *Service) assembledUpload(ctx *app.Ctx, id int64) ([]byte, error) {
	value, err := readUpload(ctx.Context, s.d.ReadPool(), id, ctx.Viewer.ID, ctx.Now())
	if err != nil {
		return nil, err
	}
	root, err := s.uploadRoot()
	if err != nil {
		return nil, err
	}
	defer root.Close()
	buffer := bytes.NewBuffer(make([]byte, 0, int(value.total)))
	for offset := int64(0); offset < value.total; offset += ChunkBytes {
		relative := fmt.Sprintf("%s/%d.chunk", value.token, offset)
		file, err := root.Open(relative)
		if os.IsNotExist(err) {
			return nil, api.Invalid("字体成品包尚未上传完整，请继续上传。")
		}
		if err != nil {
			return nil, err
		}
		data, err := io.ReadAll(io.LimitReader(file, ChunkBytes+1))
		file.Close()
		if err != nil {
			return nil, err
		}
		expected := int64(ChunkBytes)
		if remaining := value.total - offset; remaining < expected {
			expected = remaining
		}
		if int64(len(data)) != expected {
			return nil, api.Invalid("字体成品包分块长度不正确，请重新上传。")
		}
		buffer.Write(data)
	}
	return buffer.Bytes(), nil
}

// CleanupExpired removes private staging data belonging only to this font module.
// Call it from the existing daily maintenance job; it never traverses media or backups.
func (s *Service) CleanupExpired(ctx context.Context, now time.Time) (int, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT id,token FROM font_uploads WHERE expires_at<=? OR state='consumed'`, stamp(now))
	if err != nil {
		return 0, err
	}
	values := []upload{}
	for rows.Next() {
		var value upload
		if err := rows.Scan(&value.id, &value.token); err != nil {
			rows.Close()
			return 0, err
		}
		values = append(values, value)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	root, err := s.uploadRoot()
	if err != nil {
		return 0, err
	}
	defer root.Close()
	count := 0
	for _, value := range values {
		if len(value.token) != 48 {
			continue
		}
		if err := root.RemoveAll(value.token); err != nil {
			return count, err
		}
		if err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			_, err := tx.ExecContext(txCtx, `DELETE FROM font_uploads WHERE id=? AND (expires_at<=? OR state='consumed')`, value.id, stamp(now))
			return err
		}); err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}
