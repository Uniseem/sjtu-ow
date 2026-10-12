-- +goose Up
ALTER TABLE font_families ADD COLUMN license_type TEXT NOT NULL DEFAULT 'other';
ALTER TABLE font_families ADD COLUMN license_note TEXT NOT NULL DEFAULT '';
ALTER TABLE font_faces ADD COLUMN glyph_count INTEGER NOT NULL DEFAULT 0 CHECK(glyph_count BETWEEN 0 AND 2147483647);
-- Preserve the existing free-form license field unchanged. Legacy imports fill
-- the two authoritative fields directly; this fallback covers older new DBs.
UPDATE font_families SET license_type=CASE WHEN license IN ('open_source','web_license','other') THEN license WHEN instr(license,' · ')>0 AND substr(license,1,instr(license,' · ')-1) IN ('open_source','web_license','other') THEN substr(license,1,instr(license,' · ')-1) ELSE 'other' END;
UPDATE font_families SET license_note=CASE WHEN instr(license,' · ')>0 AND substr(license,1,instr(license,' · ')-1) IN ('open_source','web_license','other') THEN substr(license,instr(license,' · ')+3) WHEN license IN ('open_source','web_license','other') THEN '' ELSE license END;
-- +goose Down
ALTER TABLE font_faces DROP COLUMN glyph_count;
ALTER TABLE font_families DROP COLUMN license_note;
ALTER TABLE font_families DROP COLUMN license_type;
