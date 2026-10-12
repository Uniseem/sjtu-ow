import { describe, expect, test } from "vitest"
import { orderedBoard } from "./split-model"
import { scrimBoard, scrimSignup } from "./test-fixtures"
import { boardRank, shortTimestamp } from "./domain"

describe("旧分队和编队名单的段位、日期", () => {
  test("分数展示中文段位，0 分仍是青铜 5，缺段位用原文案", () => {
    expect(boardRank(0)).toBe("青铜 5")
    expect(boardRank(4)).toBe("青铜 1")
    expect(boardRank(15)).toBe("白金 5")
    expect(boardRank(20)).toBe("钻石 5")
    expect(boardRank(39)).toBe("英杰 1")
    expect(boardRank(40)).toBe("前 500")
    expect(boardRank(null)).toBe("未填段位")
    expect(boardRank(undefined)).toBe("未填段位")
  })

  test("报名日期按旧模板 m.d H:i 展示并固定北京时间", () => {
    expect(shortTimestamp("2026-10-11T23:59:30Z")).toBe("10.12 07:59")
  })
})


test("分队写回执保持段位排序，不改服务器返回的板版本或原名单", () => {
  const first = { ...scrimSignup(1), best_rating: 10, created_at: "2026-10-11T09:00:00Z" }
  const second = { ...scrimSignup(2), best_rating: 30, created_at: "2026-10-11T10:00:00Z" }
  const receipt = scrimBoard([first, second])
  const rated = orderedBoard(receipt, "rating")
  expect(rated.order).toBe("rating")
  expect(rated.signups.map((item) => item.signup_id)).toEqual([2, 1])
  expect(rated.board_version).toBe(receipt.board_version)
  expect(receipt.signups.map((item) => item.signup_id)).toEqual([1, 2])
  expect(orderedBoard(rated, "created").signups.map((item) => item.signup_id)).toEqual([1, 2])
})
