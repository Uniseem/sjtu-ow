import { describe, expect, test } from "vitest"
import {
  bestTarget, boardFromCurrent, currentSplit, keyboardSide, moveSignup, projectedSignups,
  sideProblems, sideTotal, splitValues, splitZones,
} from "./split-model"
import { scrimBoard, scrimSignup } from "./test-fixtures"

describe("分队板状态与所有输入方式共用的移动规则", () => {
  test("Alt 箭头键实际映射到换队或缓冲，不截获普通或系统快捷键", () => {
    const event = (key: string, altKey = true, ctrlKey = false, metaKey = false) => ({ key, altKey, ctrlKey, metaKey })
    expect(keyboardSide(event("ArrowLeft"))).toBe("a")
    expect(keyboardSide(event("ArrowRight"))).toBe("b")
    expect(keyboardSide(event("ArrowDown"))).toBe("")
    expect(keyboardSide(event("ArrowLeft", false))).toBeNull()
    expect(keyboardSide(event("ArrowLeft", true, true))).toBeNull()
    expect(keyboardSide(event("ArrowRight", true, false, true))).toBeNull()
    expect(keyboardSide(event("Enter"))).toBeNull()
  })

  test("取消勾选只清这个人的显示去向，其他人的分队保留", () => {
    const board = scrimBoard()
    const values = splitValues(board)
    values.signup_ids = [2, 3]
    const projection = projectedSignups(board, values)
    expect(projection[0]).toMatchObject({ is_selected: false, team: "", assigned_role: "" })
    expect(projection[1]).toMatchObject({ is_selected: true, team: "b", assigned_role: "tank" })
    const zones = splitZones(board, values)
    expect(zones.flatMap((zone) => zone.members).map((signup) => signup.signup_id).sort()).toEqual([2, 3])
    expect(board.signups[0]?.team).toBe("a")
  })

  test("按钮和键盘先选择目标再走同一个移动入口，满队先缓冲", () => {
    const signups = Array.from({ length: 5 }, (_, index) => scrimSignup(index + 1, "a", index ? "damage" : "tank"))
    const newcomer = scrimSignup(6)
    const board = scrimBoard([...signups, newcomer])
    const values = splitValues(board)
    const target = bestTarget(splitZones(board, values), newcomer, "a")
    expect(target?.key).toBe("a:tank")
    expect(moveSignup(board, values, 6, target!.key).message).toContain("满员")
    const buffer = bestTarget(splitZones(board, values), signups[0]!, "")!
    const emptied = moveSignup(board, values, 1, buffer.key)
    expect(emptied.message).toBe("")
    const moved = moveSignup(board, emptied.values, 6, target!.key)
    expect(moved.message).toBe("")
    expect(moved.values.placements.find((placement) => placement.signup_id === 6)).toEqual({ signup_id: 6, team: "a", role: "tank" })
    expect(values.placements.find((placement) => placement.signup_id === 1)?.team).toBe("a")
  })

  test("队内换位置即使超过角色配额仍可保存并显示警告", () => {
    const board = scrimBoard(Array.from({ length: 5 }, (_, index) => scrimSignup(index + 1, "a", index ? "damage" : "tank")))
    const result = moveSignup(board, splitValues(board), 2, "a:tank")
    expect(result.message).toBe("")
    const zones = splitZones(board, result.values)
    expect(zones.find((zone) => zone.key === "a:tank")?.members.length).toBe(2)
    expect(sideProblems(zones, "rq_5v5", "a").join(" ")).toContain("坦克 2/1")
  })

  test("未勾选、不存在的人或不存在的区域不能移动", () => {
    const board = scrimBoard([scrimSignup(1, "", "", false)])
    const values = splitValues(board)
    expect(moveSignup(board, values, 1, "a:tank").message).toContain("先勾选")
    expect(moveSignup(board, values, 999, "a:tank").message).toContain("已经不存在")
    expect(moveSignup(board, values, 1, "c:tank").message).toContain("已经不存在")
    expect(moveSignup(board, values, 1, "a:tank").values).toBe(values)
  })

  test("位置缺段位按零算，不用其他位置最高分掩盖缺失", () => {
    const signup = scrimSignup(1, "a", "tank")
    signup.ratings = { damage: 35 }
    signup.best_rating = 35
    const board = scrimBoard([signup])
    const zones = splitZones(board, splitValues(board))
    expect(sideTotal(zones, "a")).toBe(0)
    expect(sideProblems(zones, "rq_5v5", "a").join(" ")).toContain("没有段位")
  })

  test("规格改动后未知旧位置仍可见，不能从界面丢掉报名者", () => {
    const board = scrimBoard([scrimSignup(1, "a", "old-role")])
    const zones = splitZones(board, splitValues(board))
    expect(zones.find((zone) => zone.key === "a:unassigned")?.members[0]?.signup_id).toBe(1)
    expect(zones.flatMap((zone) => zone.members).map((signup) => signup.signup_id)).toEqual([1])
  })

  test("409的完整真实current可恢复版本，截断投影不会被当成完整板", () => {
    const board = scrimBoard()
    const current = currentSplit({ board })
    expect(current?.version).toBe(20)
    expect(current?.values.signup_ids).toEqual([1, 2, 3])
    expect(boardFromCurrent({ board })).toBe(board)
    expect(boardFromCurrent({ board_version: 20, signups: board.signups })).toBeNull()
    expect(currentSplit({ board_version: -1, signups: board.signups })).toBeNull()
  })

  test("冲突投影拒绝零编号、重复编号和未知队伍/位置", () => {
    const valid = scrimBoard()
    expect(currentSplit({ ...valid, signups: [{ ...valid.signups[0], signup_id: 0 }] })).toBeNull()
    expect(currentSplit({ ...valid, signups: [valid.signups[0], valid.signups[0]] })).toBeNull()
    expect(currentSplit({ ...valid, signups: [{ ...valid.signups[0], team: "c" }] })).toBeNull()
    expect(currentSplit({ ...valid, signups: [{ ...valid.signups[0], assigned_role: "made-up" }] })).toBeNull()
  })
})
