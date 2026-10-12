import { expect, test } from "vitest"
import { fontCSSPath } from "@sjtu-ow/shared/font-css"

test("accepts current 20-digit font hashes and the previous 12-digit URLs", () => {
  for (const hash of ["0123456789ab", "0123456789abcdef0123"]) {
    const path = `/media/fonts/css/fonts.${hash}.css`
    expect(fontCSSPath(path)).toBe(path)
  }
  for (const value of ["https://evil.invalid/a.css", "/media/fonts/raw.ttf", "/media/fonts/css/fonts.abcdef.css", "/media/fonts/css/fonts.0123456789ab.css?evil=1", "/media/fonts/css/preview.0123456789ab.css"]) {
    expect(fontCSSPath(value)).toBeNull()
  }
})
