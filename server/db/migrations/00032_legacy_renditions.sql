-- +goose Up
CREATE TABLE legacy_image_renditions (
  file_name TEXT PRIMARY KEY,
  image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE
) STRICT;
CREATE INDEX legacy_image_renditions_image ON legacy_image_renditions(image_id);

-- +goose Down
DROP TABLE legacy_image_renditions;
