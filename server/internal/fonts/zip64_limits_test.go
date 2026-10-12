package fonts

import (
	"archive/zip"
	"bytes"
	"math"
	"testing"
)

func TestPackageZip64SizeCannotOverflowUncompressedBudget(t *testing.T) {
	// Copy an otherwise valid tiny package, then append an unused LICENSE entry.
	// A raw Zip64 header can claim a huge expansion without supplying those bytes;
	// LICENSE is permitted but is not opened by the importer.
	fixture := packageFixture(t, nil, nil)
	original, err := zip.NewReader(bytes.NewReader(fixture), int64(len(fixture)))
	if err != nil {
		t.Fatal(err)
	}
	var total uint64
	for _, file := range original.File {
		total += file.UncompressedSize64
	}
	for _, claimed := range []uint64{MaxPackageBytes + 1, math.MaxUint64 - total + 1} {
		var buffer bytes.Buffer
		writer := zip.NewWriter(&buffer)
		for _, file := range original.File {
			if err := writer.Copy(file); err != nil {
				t.Fatal(err)
			}
		}
		_, err := writer.CreateRaw(&zip.FileHeader{Name: "LICENSE.txt", Method: zip.Store, UncompressedSize64: claimed, CompressedSize64: 0})
		if err != nil {
			t.Fatal(err)
		}
		if err := writer.Close(); err != nil {
			t.Fatal(err)
		}
		parsed, err := zip.NewReader(bytes.NewReader(buffer.Bytes()), int64(buffer.Len()))
		if err != nil {
			t.Fatal(err)
		}
		last := parsed.File[len(parsed.File)-1]
		if last.UncompressedSize64 != claimed {
			t.Fatalf("fixture lost Zip64 size: %d want %d", last.UncompressedSize64, claimed)
		}
		if _, err := preparePackage(buffer.Bytes()); err == nil {
			t.Fatalf("oversized/overflowing LICENSE accepted: %d", claimed)
		}
	}
}
