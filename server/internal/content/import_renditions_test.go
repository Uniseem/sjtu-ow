package content

import (
	"context"
	"testing"
)

func TestLegacyRenditionImporterRetainsAssociationsWithoutResurrectingOrphans(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	old := newLegacyContentDB(t)
	if _, err := d.WritePool().Exec(`INSERT INTO images(id,title,file_name,file_size,width,height,created_at) VALUES(701,'First','original_images/a.png',1,10,10,'x')`); err != nil {
		t.Fatal(err)
	}
	if _, err := old.Exec(`CREATE TABLE wagtailimages_rendition(id INTEGER PRIMARY KEY,image_id INTEGER,file TEXT);INSERT INTO wagtailimages_rendition VALUES(1,701,'images/first.png'),(2,9999,'images/orphan.png')`); err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := importLegacyRenditions(ctx, d, old); err != nil {
			t.Fatal(err)
		}
	}
	var count int
	if err := d.ReadPool().QueryRow(`SELECT COUNT(*) FROM legacy_image_renditions`).Scan(&count); err != nil || count != 1 {
		t.Fatalf("associations=%d err=%v", count, err)
	}
	if _, err := old.Exec(`INSERT INTO wagtailimages_rendition VALUES(3,701,'../outside.png')`); err != nil {
		t.Fatal(err)
	}
	if err := importLegacyRenditions(ctx, d, old); err == nil {
		t.Fatal("unsafe mapping accepted")
	}
}
