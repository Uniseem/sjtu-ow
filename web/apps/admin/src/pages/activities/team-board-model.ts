import { record } from "./domain"
import type { TournamentBoard, TournamentEntry } from "./domain"

export type TeamZone = {
  key: string
  registration_id: number | null
  name: string
  base_version: number
  signup_ids: number[]
}

export type TeamLayout = {
  zones: TeamZone[]
  base_pool_version: number | null
}

export type BoardMoveResult = {
  layout: TeamLayout
  message: string
}

export function boardPoolVersion(board: TournamentBoard): number | null {
  const source = record(board)
  const value = source?.pool_version
  return Number.isSafeInteger(value) && Number(value) > 0 ? Number(value) : null
}

export function layoutFromBoard(board: TournamentBoard): TeamLayout {
  return {
    base_pool_version: boardPoolVersion(board),
    zones: board.teams.map((team) => ({
      key: `r${team.registration_id}`,
      registration_id: team.registration_id,
      name: team.name,
      base_version: team.roster_version,
      signup_ids: [...team.signup_ids],
    })),
  }
}

export function benchEntries(board: TournamentBoard, layout: TeamLayout): TournamentEntry[] {
  const placed = new Set(layout.zones.flatMap((zone) => zone.signup_ids))
  return board.entries.filter((entry) => !placed.has(entry.signup_id))
}

export function zoneEntries(board: TournamentBoard, zone: TeamZone): TournamentEntry[] {
  const map = new Map(board.entries.map((entry) => [entry.signup_id, entry]))
  return zone.signup_ids.flatMap((id) => {
    const entry = map.get(id)
    return entry ? [entry] : []
  })
}

export function zoneProblems(zone: TeamZone, minimum: number, maximum: number): string[] {
  const problems: string[] = []
  if (zone.signup_ids.length && !zone.name.trim()) problems.push("请填写队名")
  if (zone.name.length > 16) problems.push("队名最多 16 字")
  if (zone.signup_ids.length && zone.signup_ids.length < minimum) problems.push(`人数 ${zone.signup_ids.length}/${minimum}，低于下限`)
  if (zone.signup_ids.length > maximum) problems.push(`人数 ${zone.signup_ids.length}/${maximum}，超过上限`)
  return problems
}

export function placeEntry(
  board: TournamentBoard,
  layout: TeamLayout,
  signupId: number,
  targetKey: string,
): BoardMoveResult {
  const entry = board.entries.find((item) => item.signup_id === signupId)
  if (!entry) return { layout, message: "这个人已经不在报名名单里，请刷新。" }
  const current = layout.zones.find((zone) => zone.signup_ids.includes(signupId))
  const target = targetKey ? layout.zones.find((zone) => zone.key === targetKey) : null
  if (targetKey && !target) return { layout, message: "目标队伍已经不存在，请刷新。" }
  if (current?.key === targetKey || (!current && !targetKey)) return { layout, message: "" }
  if (target && entry.conflict) return { layout, message: entry.conflict }
  if (target && target.signup_ids.length >= board.roster_max) return {
    layout,
    message: "队伍满员时不能直接拖进去，先把要换下来的人移回散人池。",
  }
  const next = structuredClone(layout)
  for (const zone of next.zones) zone.signup_ids = zone.signup_ids.filter((id) => id !== signupId)
  if (targetKey) next.zones.find((zone) => zone.key === targetKey)?.signup_ids.push(signupId)
  return { layout: next, message: "" }
}

export function addZone(layout: TeamLayout, key: string): TeamLayout {
  return {
    ...structuredClone(layout),
    zones: [...structuredClone(layout.zones), {
      key,
      registration_id: null,
      name: "",
      base_version: 0,
      signup_ids: [],
    }],
  }
}

export function renameZone(layout: TeamLayout, key: string, name: string): TeamLayout {
  const next = structuredClone(layout)
  const zone = next.zones.find((item) => item.key === key)
  if (zone) zone.name = name
  return next
}

export function dissolveZone(layout: TeamLayout, key: string): TeamLayout {
  const next = structuredClone(layout)
  const zone = next.zones.find((item) => item.key === key)
  if (!zone) return next
  if (zone.registration_id === null) next.zones = next.zones.filter((item) => item.key !== key)
  else zone.signup_ids = []
  return next
}

export function layoutPayload(layout: TeamLayout): {
  teams: { registration_id: number | null; name: string; signup_ids: number[]; base_version: number }[]
  base_pool_version: number
} | null {
  if (layout.base_pool_version === null) return null
  return {
    base_pool_version: layout.base_pool_version,
    teams: layout.zones.filter((zone) => zone.registration_id !== null || zone.signup_ids.length).map((zone) => ({
      registration_id: zone.registration_id,
      name: zone.name,
      signup_ids: [...zone.signup_ids],
      base_version: zone.base_version,
    })),
  }
}

export function layoutEqual(left: TeamLayout, right: TeamLayout): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

/** Local inspection explains issues; the service remains the validation gate. */
export function layoutErrors(board: TournamentBoard, layout: TeamLayout): string[] {
  const entries = new Map(board.entries.map((entry) => [entry.signup_id, entry]))
  const seen = new Set<number>()
  const names = new Set<string>()
  const problems: string[] = []
  for (const zone of layout.zones) {
    if (!zone.signup_ids.length) continue
    const name = zone.name.trim()
    if (!name) problems.push("请给新队伍填队名。")
    if (name.length > 16) problems.push("队名最多 16 字。")
    if (names.has(name)) problems.push(`队名「${name}」重复。`)
    names.add(name)
    if (zone.signup_ids.length > board.roster_max) problems.push(`「${name}」超过人数上限。`)
    if (zone.registration_id !== null && zone.base_version <= 0) problems.push(`「${name}」缺少名单版本，请刷新。`)
    for (const id of zone.signup_ids) {
      const entry = entries.get(id)
      if (!entry) problems.push("名单里有人已经取消报名，请刷新。")
      if (seen.has(id)) problems.push(`${entry?.nickname ?? id} 被放进了两支队伍。`)
      if (entry?.conflict) problems.push(`${entry.nickname}：${entry.conflict}`)
      seen.add(id)
    }
  }
  return [...new Set(problems)]
}
