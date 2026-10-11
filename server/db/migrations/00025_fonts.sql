-- Fonts D4: finished packages only; production never slices raw TTF/OTF.
-- This file is a migration handoff; root moves it to next available db/migrations number.
-- +goose Up
CREATE TABLE font_families (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 family TEXT NOT NULL,
 display_name TEXT NOT NULL,
 css_name TEXT NOT NULL UNIQUE,
 source TEXT NOT NULL,
 source_ref TEXT NOT NULL DEFAULT '',
 license TEXT NOT NULL,
 license_confirmed INTEGER NOT NULL CHECK(license_confirmed IN (0,1)),
 created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 created_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'ready',
 error TEXT NOT NULL DEFAULT ''
) STRICT;
CREATE TABLE font_faces (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 family_id INTEGER NOT NULL REFERENCES font_families(id) ON DELETE CASCADE,
 weight INTEGER NOT NULL CHECK(weight BETWEEN 100 AND 900 AND weight % 100 = 0),
 style TEXT NOT NULL CHECK(style IN ('normal','italic')),
 slices TEXT NOT NULL,
 bytes INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'ready',
 error TEXT NOT NULL DEFAULT '',
 UNIQUE(family_id,weight,style)
) STRICT;
CREATE TABLE typography_state (
 id INTEGER PRIMARY KEY CHECK(id = 1),
 version INTEGER NOT NULL DEFAULT 1,
 css_path TEXT NOT NULL DEFAULT '',
 generated_at TEXT
) STRICT;
INSERT INTO typography_state(id) VALUES(1);
CREATE TABLE typography_rules (
 region TEXT PRIMARY KEY CHECK(region IN ('body','h1','h2','h3','h4','nav','button','numeric','mono')),
 mode TEXT NOT NULL DEFAULT 'inherit' CHECK(mode IN ('system','inherit','custom')),
 family_id INTEGER REFERENCES font_families(id) ON DELETE RESTRICT,
 weight INTEGER NOT NULL DEFAULT 400 CHECK(weight BETWEEN 100 AND 900 AND weight % 100 = 0),
 size_rem REAL,
 line_height REAL,
 letter_spacing_em REAL,
 CHECK(region <> 'body' OR mode <> 'inherit'),
 CHECK(mode <> 'custom' OR family_id IS NOT NULL)
) STRICT;
INSERT INTO typography_rules(region,mode) VALUES ('body','system'),('h1','inherit'),('h2','inherit'),('h3','inherit'),('h4','inherit'),('nav','inherit'),('button','inherit'),('numeric','system'),('mono','system');
CREATE TABLE font_uploads (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 total_bytes INTEGER NOT NULL CHECK(total_bytes > 0 AND total_bytes <= 67108864),
 state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','consumed')),
 created_at TEXT NOT NULL,
 expires_at TEXT NOT NULL
) STRICT;
-- +goose Down
DROP TABLE font_uploads;
DROP TABLE typography_rules;
DROP TABLE typography_state;
DROP TABLE font_faces;
DROP TABLE font_families;
