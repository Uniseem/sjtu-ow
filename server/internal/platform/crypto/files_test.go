package crypto

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestFileTokensInteroperateWithFieldFernet(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	source := filepath.Join(root, "source")
	encrypted := filepath.Join(root, "encrypted")
	result := filepath.Join(root, "result")
	for _, size := range []int{0, 1, 15, 16, 17, 65535, 65536, 65537, 131073} {
		data := bytes.Repeat([]byte{0x00, 0x7f, 0x80, 0xff}, size/4+1)[:size]
		if err := os.WriteFile(source, data, 0600); err != nil {
			t.Fatal(err)
		}
		if err := EncryptFile(ctx, "test-only-backup-key", source, encrypted); err != nil {
			t.Fatal(err)
		}
		token, err := os.ReadFile(encrypted)
		if err != nil {
			t.Fatal(err)
		}
		decoded, err := Decrypt("test-only-backup-key", string(token))
		if err != nil || !bytes.Equal([]byte(decoded), data) {
			t.Fatalf("stream token compatibility size=%d: %v", size, err)
		}
		if err := DecryptFile(ctx, "test-only-backup-key", encrypted, result); err != nil {
			t.Fatal(err)
		}
		roundtrip, err := os.ReadFile(result)
		if err != nil || !bytes.Equal(roundtrip, data) {
			t.Fatalf("roundtrip size=%d: %v", size, err)
		}
		if size > 0 {
			legacy, err := Encrypt("test-only-backup-key", string(data))
			if err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(encrypted, []byte(legacy), 0600); err != nil {
				t.Fatal(err)
			}
			if err := DecryptFile(ctx, "test-only-backup-key", encrypted, result); err != nil {
				t.Fatal(err)
			}
			roundtrip, _ := os.ReadFile(result)
			if !bytes.Equal(roundtrip, data) {
				t.Fatalf("legacy token size=%d", size)
			}
		}
	}
}
func TestInvalidFileTokenNeverReplacesTarget(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	source := filepath.Join(root, "source")
	encrypted := filepath.Join(root, "encrypted")
	target := filepath.Join(root, "target")
	if err := os.WriteFile(source, []byte("private archive"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := EncryptFile(ctx, "test-only-key", source, encrypted); err != nil {
		t.Fatal(err)
	}
	valid, err := os.ReadFile(encrypted)
	if err != nil {
		t.Fatal(err)
	}
	damaged := append([]byte{}, valid...)
	damaged[len(damaged)/2] ^= 1
	for _, fixture := range []struct {
		key   string
		token []byte
	}{{"wrong-test-key", valid}, {"test-only-key", damaged}, {"test-only-key", valid[:len(valid)-10]}, {"test-only-key", []byte("not a token")}} {
		if err := os.WriteFile(target, []byte("keep existing"), 0600); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(encrypted, fixture.token, 0600); err != nil {
			t.Fatal(err)
		}
		if err := DecryptFile(ctx, fixture.key, encrypted, target); err == nil {
			t.Fatal("bad token accepted")
		}
		actual, _ := os.ReadFile(target)
		if string(actual) != "keep existing" {
			t.Fatal("existing target replaced")
		}
	}
	entries, _ := os.ReadDir(root)
	for _, entry := range entries {
		if entry.Name()[0] == '.' {
			t.Fatalf("staging leaked: %s", entry.Name())
		}
	}
}
func TestEncryptionRequiresKeyAndHonorsCancellation(t *testing.T) {
	root := t.TempDir()
	source := filepath.Join(root, "source")
	target := filepath.Join(root, "encrypted")
	if err := os.WriteFile(source, []byte("archive"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := EncryptFile(context.Background(), "", source, target); err == nil {
		t.Fatal("missing key accepted")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := EncryptFile(ctx, "test-only-key", source, target); err == nil {
		t.Fatal("cancel ignored")
	}
	if _, err := os.Stat(target); !os.IsNotExist(err) {
		t.Fatal("canceled archive published")
	}
}
