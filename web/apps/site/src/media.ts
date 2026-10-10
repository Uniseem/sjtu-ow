import type { ImageSpec } from "@sjtu-ow/api"

// Where a picture is (12-architecture 3.4, frontend-migration A7): Caddy
// hands the file out of the media volume, or Go makes it the first time.
// The spec list comes from Go's AllowedSpecs (gen/specs.ts), so a size that
// does not exist is a type error, not a 404 on the live site.
export function imageUrl(id: number, spec: ImageSpec): string {
  return `/media/r/${id}/${spec}.webp`
}
