-- 00015 通知（M7，设计 10.4、10.5，规则 73–79、206–216）。
-- users.accepts_announcements：活动通知的开关，默认开（规则 212）。
-- users.calendar_version：「换一个订阅地址」让旧地址作废（设计 13.5，v7.20）。
-- broadcasts 换成通用的：文章、赛事、内战的「通知全体成员」和「通知报名的人」各记一条历史。
-- M4 那张只记了条数、没发过信，没有要留的数据。
-- waits_for_publish：文章安排了定时上线，通知排到上线那一刻再发（规则 74）；
-- 同一篇同时只能排一个，唯一索引兜底。

-- +goose Up
ALTER TABLE users ADD COLUMN accepts_announcements INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_version INTEGER NOT NULL DEFAULT 0;

DROP TABLE broadcasts;

CREATE TABLE broadcasts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  object_id INTEGER NOT NULL,
  audience TEXT NOT NULL,
  before_count INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  subject TEXT NOT NULL DEFAULT '',
  sent_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  recipient_count INTEGER NOT NULL DEFAULT 0,
  waits_for_publish INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  CHECK (kind IN ('article', 'tournament', 'scrim')),
  CHECK (audience IN ('everyone', 'participants'))
) STRICT;

CREATE INDEX broadcasts_object ON broadcasts (kind, object_id, id DESC);
CREATE UNIQUE INDEX broadcasts_one_waiting ON broadcasts (kind, object_id) WHERE waits_for_publish = 1;

-- +goose Down
DROP TABLE broadcasts;
CREATE TABLE broadcasts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  recipient_count INTEGER NOT NULL,
  created_at TEXT NOT NULL
) STRICT;
CREATE INDEX idx_broadcasts_article ON broadcasts(article_id, id DESC);
ALTER TABLE users DROP COLUMN calendar_version;
ALTER TABLE users DROP COLUMN accepts_announcements;
