package ops

import (
	"context"
	"encoding/json"
	"encoding/xml"
	"errors"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/storage"
)

type offsiteTestTransport func(*http.Request) (*http.Response, error)

func (f offsiteTestTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	return f(request)
}

func offsiteTestResponse(request *http.Request, status int, body string) *http.Response {
	return &http.Response{StatusCode: status, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(body)), Request: request}
}

func offsiteTestClient(t *testing.T, transport http.RoundTripper) *storage.Client {
	t.Helper()
	client, err := storage.New(storage.Config{Endpoint: "https://storage.example.invalid", Region: "auto", Bucket: "site-backups", Prefix: "this-site/backups", AccessKeyID: "test-key-id", SecretAccessKey: "test-secret-not-production"}, transport)
	if err != nil {
		t.Fatal(err)
	}
	return client
}

func offsiteTestFile(t *testing.T, root, name string) string {
	t.Helper()
	path := filepath.Join(root, name)
	if err := os.WriteFile(path, []byte("local backup archive bytes"), 0600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestCompleteBackupStatusDistinguishesOffSkippedAndFailedWithoutLosingLocalArchive(t *testing.T) {
	for _, mode := range []string{"disabled", "explicit skip", "upload configuration fails"} {
		t.Run(mode, func(t *testing.T) {
			root := t.TempDir()
			archive := offsiteTestFile(t, root, "sjtuow-20261011-100000.tar.gz")
			before, err := os.ReadFile(archive)
			if err != nil {
				t.Fatal(err)
			}
			now := time.Date(2026, 10, 11, 10, 0, 0, 0, time.UTC)
			options := OffsiteOptions{ArchivePath: archive, Now: now, Enabled: mode != "disabled", Skip: mode == "explicit skip"}
			status, operationErr := CompleteBackup(context.Background(), options)
			if status == nil {
				t.Fatalf("local success lost its status: %v", operationErr)
			}
			want := "off"
			if mode == "explicit skip" {
				want = "skipped"
			}
			if mode == "upload configuration fails" {
				want = "failed"
			}
			if status.Offsite != want || status.Archive != filepath.Base(archive) || status.Size != int64(len(before)) || !status.FinishedAt.Equal(now) {
				t.Fatalf("wrong local/offsite state: %+v", status)
			}
			if (operationErr != nil) != (want == "failed") {
				t.Fatalf("success/failure semantics disagree: %+v %v", status, operationErr)
			}
			if want == "failed" && status.Error == "" {
				t.Fatal("failed offsite operation reported no reason")
			}
			after, err := os.ReadFile(archive)
			if err != nil || !reflect.DeepEqual(after, before) {
				t.Fatal("offsite failure or skip altered local archive")
			}
			stored, err := ReadBackupStatus(root)
			if err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(stored, status) {
				t.Fatalf("persisted status differs from returned outcome: %+v / %+v", stored, status)
			}
			entries, err := os.ReadDir(root)
			if err != nil {
				t.Fatal(err)
			}
			for _, entry := range entries {
				if strings.HasPrefix(entry.Name(), ".sjtuow-offsite-") {
					t.Fatal("staging ciphertext remained after failed upload")
				}
			}
		})
	}
}

func TestBackupStatusIsPrivateAtomicAndRejectsInvalidDocuments(t *testing.T) {
	root := t.TempDir()
	status := BackupStatus{FinishedAt: time.Date(2026, 10, 11, 10, 0, 0, 0, time.UTC), Archive: "sjtuow-20261011-100000.tar.gz", Size: 123, Offsite: "uploaded", PruneWarning: "保留范围内的旧备份稍后清理"}
	if err := WriteBackupStatus(root, status); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(root, "last-backup.json")
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0600 {
		t.Fatalf("backup status permissions=%o", info.Mode().Perm())
	}
	status.Size = 456
	if err := WriteBackupStatus(root, status); err != nil {
		t.Fatal(err)
	}
	loaded, err := ReadBackupStatus(root)
	if err != nil || loaded.Size != 456 {
		t.Fatalf("replacement did not yield complete latest document: %+v %v", loaded, err)
	}
	entries, err := os.ReadDir(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || entries[0].Name() != "last-backup.json" {
		t.Fatalf("atomic-write temp files survived: %v", entries)
	}
	for _, bad := range []string{"{", `{"offsite":"uploaded"}`, strings.Repeat(" ", 64*1024+1)} {
		if err := os.WriteFile(path, []byte(bad), 0600); err != nil {
			t.Fatal(err)
		}
		if _, err := ReadBackupStatus(root); err == nil {
			t.Fatal("invalid backup state accepted as successful backup")
		}
	}
}

func TestPruneLocalOnlyDeletesImmediateNamedPlainArchives(t *testing.T) {
	root := t.TempDir()
	cutoff := time.Date(2026, 10, 1, 0, 0, 0, 0, time.UTC)
	old := offsiteTestFile(t, root, "sjtuow-20260901-000000.tar.gz")
	oldShanghai := offsiteTestFile(t, root, "sjtu-ow-20260901-080000.tar.gz")
	preserved := offsiteTestFile(t, root, "sjtuow-20260801-000000.tar.gz")
	kept := []string{
		"sjtuow-20261201-000000.tar.gz",
		"sjtuow-20261301-000000.tar.gz",
		"other-site-20260101-000000.tar.gz",
		"sjtuow-20260101-000000.tar.gz.enc",
		"manual.tar.gz",
		"notes.txt",
	}
	for _, name := range kept {
		offsiteTestFile(t, root, name)
	}
	directory := filepath.Join(root, "sjtuow-20260102-000000.tar.gz")
	if err := os.Mkdir(directory, 0700); err != nil {
		t.Fatal(err)
	}
	nested := offsiteTestFile(t, directory, "sjtuow-20260103-000000.tar.gz")
	outside := offsiteTestFile(t, t.TempDir(), "outside.tar.gz")
	link := filepath.Join(root, "sjtuow-20260104-000000.tar.gz")
	if err := os.Symlink(outside, link); err != nil {
		t.Fatal(err)
	}
	count, err := PruneLocalBackups(root, cutoff, preserved)
	if err != nil {
		t.Fatal(err)
	}
	if count != 2 {
		t.Fatalf("deleted %d files, expected only two old immediate archives", count)
	}
	for _, path := range []string{old, oldShanghai} {
		if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("owned old archive not removed: %s %v", path, err)
		}
	}
	for _, path := range append([]string{preserved, nested, outside, link}, func() []string {
		paths := []string{}
		for _, name := range kept {
			paths = append(paths, filepath.Join(root, name))
		}
		return paths
	}()...) {
		if _, err := os.Lstat(path); err != nil {
			t.Fatalf("prune crossed naming/directory/symlink boundary: %s %v", path, err)
		}
	}
}

func TestLegacyBackupTimestampUsesShanghaiWhileGoNamesUseUTC(t *testing.T) {
	legacy, ok := backupTime("sjtu-ow-20261011-080000.tar.gz.enc")
	if !ok {
		t.Fatal("legacy timestamp not recognized")
	}
	modern, ok := backupTime("sjtuow-20261011-000000.tar.gz.enc")
	if !ok || !legacy.Equal(modern) {
		t.Fatalf("same instant interpreted in different zones: %s %s", legacy, modern)
	}
	for _, name := range []string{"sjtuow-20261301-000000.tar.gz", "sjtuow-20261011-256000.tar.gz", "other-20261011-000000.tar.gz", "sjtuow-20261011-000000.tar.gz.enc.extra"} {
		if _, ok := backupTime(name); ok {
			t.Fatalf("unowned or invalid timestamp accepted: %s", name)
		}
	}
}

type offsiteListDocument struct {
	XMLName   xml.Name         `xml:"ListBucketResult"`
	Items     []storage.Object `xml:"Contents"`
	Next      string           `xml:"NextContinuationToken,omitempty"`
	Truncated bool             `xml:"IsTruncated"`
}

func TestPruneOffsiteOnlyDeletesOwnedEncryptedImmediateObjects(t *testing.T) {
	const prefix = "this-site/backups/"
	objects := []storage.Object{
		{Key: prefix + "sjtuow-20260901-000000.tar.gz.enc"},
		{Key: prefix + "sjtu-ow-20260901-080000.tar.gz.enc"},
		{Key: prefix + "nested/sjtuow-20260101-000000.tar.gz.enc"},
		{Key: "neighbor-site/backups/sjtuow-20260101-000000.tar.gz.enc"},
		{Key: "this-site/backups-extra/sjtuow-20260101-000000.tar.gz.enc"},
		{Key: prefix + "manual.tar.gz.enc"},
		{Key: prefix + "sjtuow-20261301-000000.tar.gz.enc"},
		{Key: prefix + "sjtuow-20261201-000000.tar.gz.enc", LastModified: time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)},
		{Key: prefix + "sjtuow-20260101-000000.tar.gz"},
		{Key: prefix + ".sjtuow-storage-test-temporary"},
	}
	deleted := []string{}
	lists := 0
	client := offsiteTestClient(t, offsiteTestTransport(func(request *http.Request) (*http.Response, error) {
		if request.Method == http.MethodDelete {
			deleted = append(deleted, strings.TrimPrefix(request.URL.Path, "/site-backups/"))
			return offsiteTestResponse(request, 204, ""), nil
		}
		if request.Method != http.MethodGet || request.URL.Query().Get("list-type") != "2" {
			t.Fatal("prune did not use scoped S3 listing")
		}
		if request.URL.Query().Get("prefix") != prefix {
			t.Fatal("prune listed outside the site's immediate prefix")
		}
		lists++
		page := offsiteListDocument{Items: objects[:3], Next: "a+b/=token", Truncated: true}
		if lists == 2 {
			if request.URL.Query().Get("continuation-token") != "a+b/=token" || !strings.Contains(request.URL.RawQuery, "continuation-token=a%2Bb%2F%3Dtoken") {
				t.Fatal("pagination token was not encoded literally")
			}
			page = offsiteListDocument{Items: objects[3:]}
		}
		if lists > 2 {
			t.Fatal("unexpected third listing")
		}
		body, err := xml.Marshal(page)
		if err != nil {
			return nil, err
		}
		return offsiteTestResponse(request, 200, string(body)), nil
	}))
	count, err := pruneOffsite(context.Background(), client, "this-site/backups", time.Date(2026, 10, 1, 0, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	sort.Strings(deleted)
	want := []string{prefix + "sjtu-ow-20260901-080000.tar.gz.enc", prefix + "sjtuow-20260901-000000.tar.gz.enc"}
	sort.Strings(want)
	if count != 2 || !reflect.DeepEqual(deleted, want) || lists != 2 {
		t.Fatalf("prune crossed prefix/naming scope: removed=%d objects=%v lists=%d", count, deleted, lists)
	}
}

func TestPruneOffsiteStopsRepeatedPaginationAndCallerCancellation(t *testing.T) {
	lists := 0
	client := offsiteTestClient(t, offsiteTestTransport(func(request *http.Request) (*http.Response, error) {
		lists++
		return offsiteTestResponse(request, 200, "<ListBucketResult><IsTruncated>true</IsTruncated><NextContinuationToken>repeated</NextContinuationToken></ListBucketResult>"), nil
	}))
	if _, err := pruneOffsite(context.Background(), client, "this-site/backups", time.Now()); err == nil {
		t.Fatal("repeated pagination token loop accepted")
	}
	if lists != 2 {
		t.Fatalf("pagination did not stop promptly: %d", lists)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	before := lists
	if _, err := pruneOffsite(ctx, client, "this-site/backups", time.Now()); !errors.Is(err, context.Canceled) {
		t.Fatalf("cancellation not propagated: %v", err)
	}
	if lists != before {
		t.Fatal("cancelled prune performed network operations")
	}
}

func TestReadStatusDoesNotAcceptMissingCompletionTime(t *testing.T) {
	root := t.TempDir()
	data, _ := json.Marshal(BackupStatus{Archive: "backup.tar.gz", Offsite: "uploaded", Size: 8})
	if err := os.WriteFile(filepath.Join(root, "last-backup.json"), data, 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := ReadBackupStatus(root); err == nil {
		t.Fatal("incomplete status appeared as completed backup")
	}
}
