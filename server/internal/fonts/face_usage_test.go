package fonts

import (
	"context"
	"encoding/base64"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func seededWeights(t *testing.T) (*fontEnv, int64, map[int]int64) {
	t.Helper()
	env := newFontEnv(t)
	first, err := env.service.importFont(env.ctx, ImportIn{Source: "package", LicenseConfirmed: true, PackageBase64: base64.StdEncoding.EncodeToString(packageFixture(t, nil, nil))})
	if err != nil {
		t.Fatal(err)
	}
	added, err := env.service.importFont(env.ctx, ImportIn{FamilyID: first.Font.ID, Source: "package", LicenseConfirmed: true, PackageBase64: base64.StdEncoding.EncodeToString(packageFixture(t, func(manifest *Manifest) { manifest.Faces[0].Weight = 700 }, nil))})
	if err != nil {
		t.Fatal(err)
	}
	ids := map[int]int64{}
	for _, face := range added.Slices {
		ids[face.Weight] = face.ID
	}
	err = env.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(ctx, `UPDATE typography_rules SET mode='system',family_id=NULL`); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, `UPDATE typography_rules SET mode='custom',family_id=?,weight=400 WHERE region='body'`, first.Font.ID)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	page, err := readTypography(context.Background(), env.d.ReadPool())
	if err != nil {
		t.Fatal(err)
	}
	if _, err = env.service.patchTypography(env.ctx, PatchTypographyIn{BaseVersion: page.Version, Changes: TypographyChanges{Regions: &page.Regions}}); err != nil {
		t.Fatal(err)
	}
	return env, first.Font.ID, ids
}
func currentFontCSS(t *testing.T, env *fontEnv) string {
	t.Helper()
	page, err := readTypography(context.Background(), env.d.ReadPool())
	if err != nil {
		t.Fatal(err)
	}
	css, err := buildCSS(context.Background(), env.d.ReadPool(), page.Regions, page.Fonts)
	if err != nil {
		t.Fatal(err)
	}
	pointer, err := env.service.CSSPointer(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(pointer, "/media/fonts/css/") {
		t.Fatal("public font CSS pointer was not generated")
	}
	stored, err := os.ReadFile(filepath.Join(env.media, strings.TrimPrefix(pointer, "/media/")))
	if err != nil {
		t.Fatal(err)
	}
	if string(stored) != css {
		t.Fatal("published CSS no longer matches effective referenced pairs")
	}
	return string(stored)
}
func TestUnusedWeightCanBeDeletedWhileFamilyIsUsed(t *testing.T) {
	env, family, ids := seededWeights(t)
	before, err := env.service.detail(env.ctx, family)
	if err != nil {
		t.Fatal(err)
	}
	if before.Font.CanDelete {
		t.Fatal("family deletion was allowed while body uses it")
	}
	for _, face := range before.Slices {
		if face.CanDelete != (face.Weight == 700) {
			t.Fatalf("per-weight permission incorrect: %+v", face)
		}
	}
	if _, err = env.service.deleteFace(env.ctx, ids[400]); err == nil {
		t.Fatal("used weight deletion accepted")
	}
	publicBefore := currentFontCSS(t, env)
	libraryBefore, err := env.service.libraryCSS(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(libraryBefore, "-700-normal") {
		t.Fatal("library did not initially contain unused weight")
	}
	after, err := env.service.deleteFace(env.ctx, ids[700])
	if err != nil {
		t.Fatal(err)
	}
	if len(after.Slices) != 1 || after.Slices[0].Weight != 400 {
		t.Fatal("unused deletion also removed used weight")
	}
	if publicAfter := currentFontCSS(t, env); publicBefore != publicAfter {
		t.Fatal("unused weight unexpectedly changed public referenced-pair CSS")
	}
	libraryAfter, err := env.service.libraryCSS(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(libraryAfter, "-700-normal") {
		t.Fatal("private library CSS still advertises deleted weight")
	}
}
func TestInheritedBodyWeightBlocksDeletionInTransaction(t *testing.T) {
	env, family, ids := seededWeights(t)
	if _, err := env.d.WritePool().Exec(`UPDATE typography_rules SET mode='inherit',family_id=NULL,weight=700 WHERE region='h1'`); err != nil {
		t.Fatal(err)
	}
	detail, err := env.service.detail(env.ctx, family)
	if err != nil {
		t.Fatal(err)
	}
	for _, face := range detail.Slices {
		if face.CanDelete {
			t.Fatal("inherit did not block effective body-family weight")
		}
	}
	if _, err = env.service.deleteFace(env.ctx, ids[700]); err == nil {
		t.Fatal("transaction gate ignored inherited reference")
	}
	if _, err = env.d.WritePool().Exec(`UPDATE typography_rules SET mode='system' WHERE region='h1'`); err != nil {
		t.Fatal(err)
	}
	if _, err = env.service.deleteFace(env.ctx, ids[700]); err != nil {
		t.Fatal(err)
	}
}
