package media

import (
	"bytes"
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"os"
	"path/filepath"
	"testing"
)

func TestLegacyInlineRenditionsReachIsolatedMediaAndRetireWithOnlyTheirImage(t *testing.T) {
	d, dir := setupTestDB(t)
	s := NewService(d, filepath.Join(dir, "new-data"), filepath.Join(dir, "new-media"))
	source := filepath.Join(dir, "old-media")
	if err := os.MkdirAll(filepath.Join(source, "images"), 0755); err != nil {
		t.Fatal(err)
	}
	data := createTestImage(32, 20)
	for _, file := range []string{"first.png", "second.png", "orphan.png"} {
		if err := os.WriteFile(filepath.Join(source, "images", file), data, 0644); err != nil {
			t.Fatal(err)
		}
	}
	err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `INSERT INTO images(id,title,file_name,file_size,width,height,created_at) VALUES(701,'First','original_images/a.png',1,32,20,'x'),(702,'Second','original_images/b.png',1,32,20,'x');
   INSERT INTO legacy_image_renditions(image_id,file_name) VALUES(701,'images/first.png'),(702,'images/second.png')`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	for range 2 {
		var rep ImportReport
		if err := s.importLegacyRenditionFiles(context.Background(), source, &rep); err != nil {
			t.Fatal(err)
		}
		if rep.Renditions != 2 {
			t.Fatalf("copied %d", rep.Renditions)
		}
	}
	copied, err := os.ReadFile(filepath.Join(s.mediaDir, "images", "first.png"))
	if err != nil || !bytes.Equal(copied, data) {
		t.Fatalf("inline URL data changed: %v", err)
	}
	if _, err := os.Stat(filepath.Join(s.mediaDir, "images", "orphan.png")); !os.IsNotExist(err) {
		t.Fatal("unassociated old file exposed")
	}
	// Metadata has already been removed atomically by the avatar decision.
	if _, err := d.WritePool().Exec(`DELETE FROM images WHERE id=701`); err != nil {
		t.Fatal(err)
	}
	s.DeleteImageFiles(701)
	if _, err := os.Stat(filepath.Join(s.mediaDir, "images", "first.png")); !os.IsNotExist(err) {
		t.Fatal("retired old avatar URL remained public")
	}
	if _, err := os.Stat(filepath.Join(s.mediaDir, "images", "second.png")); err != nil {
		t.Fatal("unrelated image removed")
	}
	if _, err := os.Stat(filepath.Join(source, "images", "first.png")); err != nil {
		t.Fatal("frozen legacy source changed")
	}
}

func TestLegacyRenditionMappingRejectsTraversalOriginalsAndExternalLinks(t *testing.T) {
	for _, file := range []string{"../outside.png", "images/../a.png", "/images/a.png", "original_images/a.png", "images/a.svg", "images\\a.png"} {
		if LegacyRenditionPath(file) {
			t.Fatalf("unsafe public path accepted: %s", file)
		}
	}
	d, dir := setupTestDB(t)
	s := NewService(d, filepath.Join(dir, "data"), filepath.Join(dir, "media"))
	source := filepath.Join(dir, "legacy")
	if err := os.MkdirAll(filepath.Join(source, "images"), 0755); err != nil {
		t.Fatal(err)
	}
	outside := filepath.Join(dir, "outside.png")
	if err := os.WriteFile(outside, createTestImage(10, 10), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Join(source, "images", "linked.png")); err != nil {
		t.Fatal(err)
	}
	if _, err := d.WritePool().Exec(`INSERT INTO images(id,title,file_name,file_size,width,height,created_at) VALUES(701,'First','original_images/a.png',1,10,10,'x');INSERT INTO legacy_image_renditions(image_id,file_name) VALUES(701,'images/linked.png')`); err != nil {
		t.Fatal(err)
	}
	var rep ImportReport
	if err := s.importLegacyRenditionFiles(context.Background(), source, &rep); err == nil {
		t.Fatal("external source link copied into public media")
	}
}
