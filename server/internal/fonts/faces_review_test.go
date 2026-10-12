package fonts

import (
	"encoding/base64"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestExistingFamilyCanAddDeleteAndDownloadFinishedWeight(t *testing.T) {
	env := newFontEnv(t)
	initial, err := env.service.importFont(env.ctx, ImportIn{Source: "package", LicenseConfirmed: true, PackageBase64: base64.StdEncoding.EncodeToString(packageFixture(t, nil, nil))})
	if err != nil {
		t.Fatal(err)
	}
	addedPackage := packageFixture(t, func(manifest *Manifest) { manifest.Faces[0].Weight = 700 }, nil)
	added, err := env.service.importFont(env.ctx, ImportIn{FamilyID: initial.Font.ID, Source: "package", LicenseConfirmed: true, PackageBase64: base64.StdEncoding.EncodeToString(addedPackage)})
	if err != nil {
		t.Fatal(err)
	}
	if added.Font.ID != initial.Font.ID || len(added.Slices) != 2 {
		t.Fatalf("weight addition created another family: %+v", added)
	}
	var faceID int64
	for _, face := range added.Slices {
		if face.Weight == 700 {
			faceID = face.ID
		}
	}
	downloaded, err := env.service.downloadFace(env.ctx, faceID)
	if err != nil {
		t.Fatal(err)
	}
	raw, err := base64.StdEncoding.DecodeString(downloaded.DataBase64)
	if err != nil {
		t.Fatal(err)
	}
	prepared, err := preparePackage(raw)
	if err != nil {
		t.Fatal(err)
	}
	if len(prepared.manifest.Faces) != 1 || prepared.manifest.Faces[0].Weight != 700 {
		t.Fatal("download did not preserve requested weight")
	}
	if _, err = env.service.importFont(env.ctx, ImportIn{FamilyID: initial.Font.ID, Source: "package", LicenseConfirmed: true, PackageBase64: base64.StdEncoding.EncodeToString(addedPackage)}); err == nil {
		t.Fatal("duplicate weight accepted")
	}
	reduced, err := env.service.deleteFace(env.ctx, faceID)
	if err != nil {
		t.Fatal(err)
	}
	if len(reduced.Slices) != 1 {
		t.Fatal("deletion removed wrong number of weights")
	}
}
func TestFontFacesCSSRequiresActiveSuperuser(t *testing.T) {
	env := newFontEnv(t)
	module := NewModule(env.service)
	for _, viewer := range []*app.Viewer{nil, {ID: 2}, {ID: 1, Superuser: true, Disabled: true}} {
		module.SetViewerResolver(func(*http.Request) *app.Viewer { return viewer })
		response := httptest.NewRecorder()
		module.facesCSS(response, httptest.NewRequest(http.MethodGet, "/api/admin/fonts/faces.css", nil))
		if response.Code == http.StatusOK {
			t.Fatal("private font preview allowed without superuser")
		}
	}
	module.SetViewerResolver(func(*http.Request) *app.Viewer { return env.ctx.Viewer })
	response := httptest.NewRecorder()
	module.facesCSS(response, httptest.NewRequest(http.MethodGet, "/api/admin/fonts/faces.css", nil))
	if response.Code != http.StatusOK || response.Header().Get("Cache-Control") != "private, no-store" {
		t.Fatalf("authorized preview: %d", response.Code)
	}
}
