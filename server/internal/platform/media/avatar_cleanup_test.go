package media

import (
	"os"
	"path/filepath"
	"testing"
)

func TestAvatarCleanupRemovesOnlyRetiredImageFiles(t *testing.T) {
	root := t.TempDir()
	svc := NewService(nil, filepath.Join(root, "data"), filepath.Join(root, "media"))
	for _, id := range []int64{7, 8} {
		master := svc.MasterPath(id)
		if err := os.MkdirAll(filepath.Dir(master), 0700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(master, []byte("master"), 0600); err != nil {
			t.Fatal(err)
		}
		directory := filepath.Join(root, "media", "r", map[int64]string{7: "7", 8: "8"}[id])
		if err := os.MkdirAll(directory, 0700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(directory, "fill-240x240.webp"), []byte("thumbnail"), 0600); err != nil {
			t.Fatal(err)
		}
	}
	svc.DeleteImageFiles(7)
	if _, err := os.Stat(svc.MasterPath(7)); !os.IsNotExist(err) {
		t.Fatalf("retired master remained: %v", err)
	}
	if _, err := os.Stat(filepath.Join(root, "media", "r", "7")); !os.IsNotExist(err) {
		t.Fatalf("retired thumbnail remained: %v", err)
	}
	if _, err := os.Stat(svc.MasterPath(8)); err != nil {
		t.Fatalf("unrelated master removed: %v", err)
	}
	if _, err := os.Stat(filepath.Join(root, "media", "r", "8", "fill-240x240.webp")); err != nil {
		t.Fatalf("unrelated thumbnail removed: %v", err)
	}
}
