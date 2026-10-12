-- +goose Up
ALTER TABLE pages ADD COLUMN expired INTEGER NOT NULL DEFAULT 0 CHECK(expired IN (0,1));

-- HomePage is not a normal article/site/news row. Keep its original source state.
CREATE TABLE content_home_state (
 id INTEGER PRIMARY KEY,
 live INTEGER NOT NULL CHECK(live IN (0,1)),
 has_unpublished_changes INTEGER NOT NULL CHECK(has_unpublished_changes IN (0,1)),
 last_published_at TEXT,
 latest_revision_id INTEGER
) STRICT;

CREATE TABLE content_home_revisions (
 id INTEGER PRIMARY KEY,
 home_id INTEGER NOT NULL REFERENCES content_home_state(id) DEFERRABLE INITIALLY DEFERRED,
 author_id INTEGER,
 content TEXT NOT NULL,
 created_at TEXT NOT NULL
) STRICT;

-- +goose Down
DROP TABLE content_home_revisions;
DROP TABLE content_home_state;
ALTER TABLE pages DROP COLUMN expired;
