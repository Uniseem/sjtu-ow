import { describe, expect, test } from "vitest"
import {
  addZone, benchEntries, boardPoolVersion, dissolveZone, layoutErrors,
  layoutFromBoard, layoutPayload, placeEntry, renameZone, zoneProblems,
} from "./team-board-model"
import type { TournamentBoard } from "./domain"
import { tournamentBoard } from "./test-fixtures"

describe("编排名册移动与提交保护", () => {
  test("满员时保持原名册，先回池再补入才能交换", () => {
    const board = tournamentBoard()
    const initial = layoutFromBoard(board)
    const rejected = placeEntry(board, initial, 4, "r40")
    expect(rejected.message).toContain("满员")
    expect(rejected.layout).toBe(initial)
    const emptied = placeEntry(board, initial, 2, "")
    expect(emptied.message).toBe("")
    expect(benchEntries(board, emptied.layout).map((entry) => entry.signup_id)).toEqual([2, 4])
    const accepted = placeEntry(board, emptied.layout, 4, "r40")
    expect(accepted.message).toBe("")
    expect(accepted.layout.zones[0]?.signup_ids).toEqual([1, 4])
    expect(initial.zones[0]?.signup_ids).toEqual([1, 2])
    expect(board.teams[0]?.signup_ids).toEqual([1, 2])
  })

  test("不存在的人、目标队伍以及已有冲突都不能改变原布局", () => {
    const board = tournamentBoard()
    const initial = layoutFromBoard(board)
    const unknown = placeEntry(board, initial, 999, "r41")
    expect(unknown.message).toContain("不在报名名单")
    expect(unknown.layout).toBe(initial)
    const deleted = placeEntry(board, initial, 4, "r999")
    expect(deleted.message).toContain("队伍已经不存在")
    expect(deleted.layout).toBe(initial)
    board.entries[3]!.conflict = "已在另一支有效战队名单中"
    const conflict = placeEntry(board, initial, 4, "r41")
    expect(conflict.message).toBe("已在另一支有效战队名单中")
    expect(conflict.layout).toBe(initial)
  })

  test("人数低于下限是可保存警告；重复与失效名单是不可提交错误", () => {
    const board = tournamentBoard()
    const layout = layoutFromBoard(board)
    expect(zoneProblems(layout.zones[1]!, 2, 2).join(" ")).toContain("低于下限")
    expect(layoutErrors(board, layout)).toEqual([])
    const invalid = structuredClone(layout)
    invalid.zones[1]!.signup_ids = [1, 999]
    expect(layoutErrors(board, invalid).join(" ")).toContain("两支队伍")
    expect(layoutErrors(board, invalid).join(" ")).toContain("已经取消报名")
    invalid.zones[0]!.base_version = 0
    expect(layoutErrors(board, invalid).join(" ")).toContain("缺少名单版本")
  })

  test("保存携带真实池版本与每队版本，未使用的新队不写入", () => {
    const board = tournamentBoard()
    const initial = layoutFromBoard(board)
    const withEmptyDraft = addZone(initial, "new-1")
    const payload = layoutPayload(withEmptyDraft)
    expect(payload).toEqual({
      base_pool_version: 12,
      teams: [
        { registration_id: 40, name: "第一队", signup_ids: [1, 2], base_version: 3 },
        { registration_id: 41, name: "第二队", signup_ids: [3], base_version: 5 },
      ],
    })
    payload!.teams[0]!.signup_ids.push(999)
    expect(initial.zones[0]!.signup_ids).toEqual([1, 2])
  })

  test("新队入人后才进入载荷，解散现有队保留带版本的空名册", () => {
    const board = tournamentBoard()
    let layout = renameZone(addZone(layoutFromBoard(board), "new-1"), "new-1", "临时新队")
    layout = placeEntry(board, layout, 4, "new-1").layout
    expect(layoutPayload(layout)?.teams[2]).toEqual({ registration_id: null, name: "临时新队", signup_ids: [4], base_version: 0 })
    const dissolved = dissolveZone(layout, "r40")
    expect(layoutPayload(dissolved)?.teams[0]).toEqual({ registration_id: 40, name: "第一队", signup_ids: [], base_version: 3 })
    expect(benchEntries(board, dissolved).map((entry) => entry.signup_id)).toEqual([1, 2])
    const discardedDraft = dissolveZone(layout, "new-1")
    expect(discardedDraft.zones.some((zone) => zone.key === "new-1")).toBe(false)
  })

  test("缺失、零或非法池版本不能绕过服务端版本校验", () => {
    const board = tournamentBoard()
    for (const version of [0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
      board.pool_version = version
      expect(boardPoolVersion(board)).toBeNull()
      expect(layoutPayload(layoutFromBoard(board))).toBeNull()
    }
    const absent = { ...board, pool_version: undefined }
    expect(boardPoolVersion(absent as unknown as TournamentBoard)).toBeNull()
  })
})
