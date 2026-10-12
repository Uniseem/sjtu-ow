package fonts

import (
	"context"
	"errors"
	"os"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

var fontObjectPath = regexp.MustCompile(`^fonts/objects/([0-9a-f]{64})\.woff2$`)

type blobLease struct {
	token string
	paths map[string]struct{}
}

func newBlobLease() (*blobLease, error) {
	token, err := randomToken()
	if err != nil {
		return nil, err
	}
	return &blobLease{token: token, paths: map[string]struct{}{}}, nil
}
func (s *Service) claimBlobPaths(ctx context.Context, lease *blobLease, paths []string, now time.Time) error {
	hashes := map[string]string{}
	for _, path := range paths {
		match := fontObjectPath.FindStringSubmatch(path)
		if len(match) != 2 {
			return errors.New("字体对象路径不正确")
		}
		hashes[path] = match[1]
	}
	err := s.d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		for path, hash := range hashes {
			if _, err := tx.ExecContext(c, `INSERT INTO font_blob_claims(path,hash,lease_token,expires_at) VALUES(?,?,?,?)
    ON CONFLICT(path,lease_token) DO UPDATE SET expires_at=excluded.expires_at`, path, hash, lease.token, stamp(now.Add(24*time.Hour))); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return err
	}
	for path := range hashes {
		lease.paths[path] = struct{}{}
	}
	return nil
}
func objectPaths(faces []Face) []string {
	set := map[string]struct{}{}
	for _, face := range faces {
		for _, slice := range face.Slices {
			set[slice.Path] = struct{}{}
		}
	}
	paths := []string{}
	for path := range set {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	return paths
}
func leasePaths(lease *blobLease) []string {
	paths := []string{}
	for path := range lease.paths {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	return paths
}

// Only exact content-addressed objects are eligible. Ref and lease checks and
// unlink share one writer lock; metadata deletion has already committed, so a
// later SQL/audit rollback can never restore a reference to an unlinked file.
func (s *Service) removeUnreferencedBlobsTx(ctx context.Context, tx *db.Tx, paths []string, now time.Time) error {
	if len(paths) == 0 {
		return nil
	}
	readPaths := func(query string, args ...any) (map[string]bool, error) {
		rows, err := tx.QueryContext(ctx, query, args...)
		if err != nil {
			return nil, err
		}
		defer rows.Close()
		values := map[string]bool{}
		for rows.Next() {
			var value string
			if err := rows.Scan(&value); err != nil {
				return nil, err
			}
			values[value] = true
		}
		return values, rows.Err()
	}
	// Read references and leases once, avoiding one full JSON scan per slice.
	refs, err := readPaths(`SELECT DISTINCT json_extract(j.value,'$.path') FROM font_faces f,json_each(f.slices) j WHERE json_extract(j.value,'$.path') IS NOT NULL`)
	if err != nil {
		return err
	}
	claims, err := readPaths("SELECT DISTINCT path FROM font_blob_claims WHERE expires_at>?", stamp(now))
	if err != nil {
		return err
	}
	var root *os.Root
	defer func() {
		if root != nil {
			root.Close()
		}
	}()
	for _, path := range paths {
		if !fontObjectPath.MatchString(path) {
			continue
		}
		if refs[path] || claims[path] {
			continue
		}
		if root == nil {
			var err error
			root, err = os.OpenRoot(s.mediaDir)
			if os.IsNotExist(err) {
				return nil
			}
			if err != nil {
				return err
			}
			for _, directory := range []string{"fonts", "fonts/objects"} {
				info, err := root.Lstat(directory)
				if os.IsNotExist(err) {
					return nil
				}
				if err != nil {
					return err
				}
				if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
					return nil
				}
			}
		}
		// Refuse symlinks and special files even when they live inside our root.
		info, err := root.Lstat(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() || info.Size() > MaxSliceBytes {
			continue
		}
		if err := root.Remove(path); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	return nil
}
func (s *Service) cleanupBlobPaths(ctx context.Context, paths []string, now time.Time) error {
	return s.d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error { return s.removeUnreferencedBlobsTx(c, tx, paths, now) })
}
func (s *Service) releaseBlobClaims(ctx context.Context, lease *blobLease, now time.Time) error {
	if lease == nil {
		return nil
	}
	return s.d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(c, "DELETE FROM font_blob_claims WHERE lease_token=?", lease.token); err != nil {
			return err
		}
		return s.removeUnreferencedBlobsTx(c, tx, leasePaths(lease), now)
	})
}
func (s *Service) finishBlobLease(ctx context.Context, lease *blobLease, now time.Time) error {
	cleanup, cancel := context.WithTimeout(context.WithoutCancel(ctx), 30*time.Second)
	defer cancel()
	return s.releaseBlobClaims(cleanup, lease, now)
}
func (s *Service) cleanupExpiredBlobClaims(ctx context.Context, now time.Time) error {
	return s.d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		rows, err := tx.QueryContext(c, "SELECT DISTINCT path FROM font_blob_claims WHERE expires_at<=?", stamp(now))
		if err != nil {
			return err
		}
		paths := []string{}
		for rows.Next() {
			var path string
			if err := rows.Scan(&path); err != nil {
				rows.Close()
				return err
			}
			paths = append(paths, path)
		}
		readErr := rows.Err()
		rows.Close()
		if readErr != nil {
			return readErr
		}
		if _, err := tx.ExecContext(c, "DELETE FROM font_blob_claims WHERE expires_at<=?", stamp(now)); err != nil {
			return err
		}
		return s.removeUnreferencedBlobsTx(c, tx, paths, now)
	})
}

// Object paths already contain the authoritative hash, so no file content is
// decoded/read under the writer lock. Hashes are created before claims begin.
func preparedPaths(data map[string][]byte) []string {
	paths := []string{}
	for hash := range data {
		paths = append(paths, "fonts/objects/"+strings.ToLower(hash)+".woff2")
	}
	sort.Strings(paths)
	return paths
}
