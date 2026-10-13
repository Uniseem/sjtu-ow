import { expect, test } from "vitest"
import { hasHeldLetters } from "./src/mutation"

test("only a real held-letter batch suppresses a page success callback", () => {
  expect(hasHeldLetters({ letters: { batch: "held-1", count: 1 } })).toBe(true)
  expect(hasHeldLetters({ letters: { batch: "", count: 0 } })).toBe(false)
  expect(hasHeldLetters({ letters: 1 })).toBe(false)
  expect(hasHeldLetters({ saved: true })).toBe(false)
})
