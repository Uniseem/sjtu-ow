import { expect, test } from "vitest"
import { ICONS } from "./icons"
import { sampleClock, seats, SPECIMEN_ICONS, styleguideHidden } from "./specimen"

test("sample dates follow the Shanghai evening of that calendar day", () => {
  const clock = sampleClock(new Date("2026-10-08T04:00:00Z"))
  expect(clock.dayDate).toBe("2026.10.11")
  expect(clock.dayMd).toBe("10.11")
  expect(clock.dayTime).toBe("19:30")
  expect(clock.dayWeekday).toBe("周日")
  expect(clock.dayMonth).toBe("10")
  expect(clock.dayDom).toBe("11")
  expect(clock.closeMd).toBe("10.20")
  expect(clock.closeWeekday).toBe("周二")
  expect(clock.pastMd).toBe("08.29")
})

test("seat cells fill from the left and cap the row", () => {
  expect(seats(8, 10).filter(Boolean)).toHaveLength(8)
  expect(seats(8, 10)).toHaveLength(10)
  expect(seats(12, 12).every(Boolean)).toBe(true)
  expect(seats(0, 0)).toEqual([])
})

test("every specimen icon has a path", () => {
  for (const name of SPECIMEN_ICONS) {
    expect(ICONS[name]?.length, name).toBeGreaterThan(0)
    for (const path of ICONS[name] ?? []) expect(path).toMatch(/^M/)
  }
})

test("the style guide stays hidden from anyone who is not staff", () => {
  expect(styleguideHidden("/_styleguide/", false)).toBe(true)
  expect(styleguideHidden("/_styleguide/emails/welcome/", false)).toBe(true)
  expect(styleguideHidden("/_styleguide/", true)).toBe(false)
  expect(styleguideHidden("/teams/", false)).toBe(false)
})
