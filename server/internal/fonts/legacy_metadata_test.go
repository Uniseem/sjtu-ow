package fonts

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestLegacyFontMetadataIsPreservedOnImportAndReimport(t *testing.T) {
	env := newFontEnv(t)
	legacy, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "old.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, statement := range []string{
		`CREATE TABLE core_fontfamily(id INTEGER PRIMARY KEY,name TEXT,css_name TEXT,source TEXT,source_ref TEXT,license_type TEXT,license_note TEXT,license_confirmed INTEGER,created_by_id INTEGER,created_at TEXT)`,
		`CREATE TABLE core_fontface(id INTEGER PRIMARY KEY,family_id INTEGER,weight INTEGER,style TEXT,status TEXT,error TEXT,slices TEXT,glyph_count INTEGER)`,
	} {
		if _, err := legacy.Exec(statement); err != nil {
			t.Fatal(err)
		}
	}
	oldMedia := t.TempDir()
	relative := "fonts/100/slices/fixture.woff2"
	if err = os.MkdirAll(filepath.Dir(filepath.Join(oldMedia, relative)), 0700); err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(oldMedia, relative), woff2Envelope(), 0600); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal([]map[string]string{{"path": relative, "unicode_range": "U+20-7E"}})
	at := stamp(env.ctx.Now())
	if _, err = legacy.Exec(`INSERT INTO core_fontfamily VALUES(100,'旧字体','old-font','upload','fixture.ttf','open_source','许可证原文',1,1,?)`, at); err != nil {
		t.Fatal(err)
	}
	if _, err = legacy.Exec(`INSERT INTO core_fontface VALUES(200,100,400,'normal','ready','',?,95)`, string(raw)); err != nil {
		t.Fatal(err)
	}
	for iteration := 0; iteration < 2; iteration++ {
		if iteration == 1 {
			if _, err = legacy.Exec(`UPDATE core_fontfamily SET source_ref='reimport.ttf',license_type='web_license',license_note='补充授权',created_by_id=2`); err != nil {
				t.Fatal(err)
			}
			if _, err = legacy.Exec(`UPDATE core_fontface SET glyph_count=96`); err != nil {
				t.Fatal(err)
			}
			if _, err = env.d.WritePool().Exec(`UPDATE users SET nickname='第二添加人' WHERE id=2`); err != nil {
				t.Fatal(err)
			}
		}
		report, err := ImportLegacyFonts(context.Background(), env.d, legacy, oldMedia, env.media)
		if err != nil {
			t.Fatal(err)
		}
		if claimCount(t, env) != 0 {
			t.Fatal("legacy import retained blob lease")
		}
		if report.Families != 1 || report.Faces != 1 {
			t.Fatalf("unexpected import counts %+v", report)
		}
		detail, err := env.service.detail(env.ctx, 100)
		if err != nil {
			t.Fatal(err)
		}
		if len(detail.Slices) != 1 || detail.Slices[0].GlyphCount != int64(95+iteration) {
			t.Fatalf("glyph metadata lost: %+v", detail)
		}
		if detail.Font.CreatedAt != at {
			t.Fatal("legacy creation time changed")
		}
		if iteration == 0 {
			if detail.Font.SourceRef != "fixture.ttf" || detail.Font.LicenseType != "open_source" || detail.Font.LicenseNote != "许可证原文" || detail.Font.CreatedByName != "测试管理员" {
				t.Fatalf("font metadata lost: %+v", detail.Font)
			}
			if detail.Font.License != "open_source · 许可证原文" {
				t.Fatal("compatible license value changed")
			}
		} else if detail.Font.SourceRef != "reimport.ttf" || detail.Font.LicenseType != "web_license" || detail.Font.LicenseNote != "补充授权" || detail.Font.CreatedByName != "第二添加人" {
			t.Fatalf("reimport kept stale metadata: %+v", detail.Font)
		}
	}
	var familyCount, faceCount int
	if err = env.d.ReadPool().QueryRow(`SELECT COUNT(*) FROM font_families WHERE id=100`).Scan(&familyCount); err != nil {
		t.Fatal(err)
	}
	if err = env.d.ReadPool().QueryRow(`SELECT COUNT(*) FROM font_faces WHERE id=200`).Scan(&faceCount); err != nil {
		t.Fatal(err)
	}
	if familyCount != 1 || faceCount != 1 {
		t.Fatal("reimport duplicated font identities")
	}
}
