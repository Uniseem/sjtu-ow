-- +goose Up
CREATE TABLE image_collections (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
) STRICT;

INSERT INTO image_collections (id, name, key, created_at) VALUES
    (1, '默认封面', 'default_cover', '2026-10-09T00:00:00.000000Z'),
    (2, '默认头像', 'default_avatar', '2026-10-09T00:00:00.000000Z'),
    (3, '用户头像', 'user_avatar', '2026-10-09T00:00:00.000000Z'),
    (4, '投稿图片', 'contributed', '2026-10-09T00:00:00.000000Z')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    collection_id INTEGER REFERENCES image_collections(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    uploader_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE article_categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    allow_submission INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE pages (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('article', 'site_page', 'news_index')),
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    live INTEGER NOT NULL DEFAULT 0,
    has_unpublished_changes INTEGER NOT NULL DEFAULT 0,
    go_live_at TEXT,
    expire_at TEXT,
    first_published_at TEXT,
    last_published_at TEXT,
    live_revision_id INTEGER,
    latest_revision_id INTEGER,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    seo_title TEXT NOT NULL DEFAULT '',
    search_description TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(kind, slug)
) STRICT;

CREATE INDEX idx_pages_live_kind ON pages(live, kind);
CREATE INDEX idx_pages_owner ON pages(owner_id);

CREATE TABLE articles (
    page_id INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES article_categories(id) ON DELETE RESTRICT,
    cover_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL,
    summary TEXT NOT NULL DEFAULT '',
    body_md TEXT NOT NULL DEFAULT '',
    body_html TEXT NOT NULL DEFAULT '',
    body_plain TEXT NOT NULL DEFAULT '',
    char_count INTEGER NOT NULL DEFAULT 0,
    reading_time INTEGER NOT NULL DEFAULT 1,
    author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    comments_enabled INTEGER NOT NULL DEFAULT 1,
    related_tournament_id INTEGER,
    search_text TEXT NOT NULL DEFAULT '',
    renderer_version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE site_pages (
    page_id INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    body_md TEXT NOT NULL DEFAULT '',
    body_html TEXT NOT NULL DEFAULT '',
    body_plain TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE TABLE news_index (
    page_id INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    intro TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE TABLE home_pins (
    article_page_id INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE page_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_go_live_at TEXT
) STRICT;

CREATE INDEX idx_page_revisions_page ON page_revisions(page_id, id DESC);

CREATE TABLE redirects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    old_path TEXT NOT NULL UNIQUE,
    new_path TEXT NOT NULL,
    is_permanent INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE embeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    bvid TEXT NOT NULL DEFAULT '',
    resolved_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    expires_at TEXT
) STRICT;

CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    reply_to_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    like_count INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX idx_comments_article ON comments(article_id, parent_id, is_pinned DESC, id ASC);
CREATE INDEX idx_comments_user ON comments(user_id);

CREATE TABLE comment_likes (
    comment_id INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (comment_id, user_id)
) STRICT;

CREATE TABLE broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    recipient_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX idx_broadcasts_article ON broadcasts(article_id, id DESC);

-- +goose Down
DROP TABLE IF EXISTS broadcasts;
DROP TABLE IF EXISTS comment_likes;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS embeds;
DROP TABLE IF EXISTS redirects;
DROP TABLE IF EXISTS page_revisions;
DROP TABLE IF EXISTS home_pins;
DROP TABLE IF EXISTS news_index;
DROP TABLE IF EXISTS site_pages;
DROP TABLE IF EXISTS articles;
DROP TABLE IF EXISTS pages;
DROP TABLE IF EXISTS article_categories;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS image_collections;
