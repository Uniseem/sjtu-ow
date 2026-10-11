import type { SaveCurrent } from "@sjtu-ow/shared/autosave"
import { record, roleLabel, roleRequirements, teamSize } from "./domain"
import type { ScrimBoard, ScrimSignup, Side } from "./domain"

export type Placement = {
  signup_id: number
  team: string
  role: string
}

export type SplitValues = {
  signup_ids: number[]
  placements: Placement[]
}

export type SplitZone = {
  key: string
  team: Side
  role: string
  label: string
  capacity: number
  members: ScrimSignup[]
}

export function splitValues(board: ScrimBoard): SplitValues {
  return {
    signup_ids: board.signups.filter((signup) => signup.is_selected).map((signup) => signup.signup_id),
    placements: board.signups.map((signup) => ({
      signup_id: signup.signup_id,
      team: signup.team,
      role: signup.assigned_role,
    })),
  }
}

export function sameSelection(left: number[], right: number[]): boolean {
  if (left.length !== right.length) return false
  const ids = new Set(left)
  return right.every((id) => ids.has(id))
}

export function projectedSignups(board: ScrimBoard, values: SplitValues): ScrimSignup[] {
  const selected = new Set(values.signup_ids)
  const placements = new Map(values.placements.map((placement) => [placement.signup_id, placement]))
  return board.signups.map((signup) => {
    const placement = placements.get(signup.signup_id)
    const isSelected = selected.has(signup.signup_id)
    const team = isSelected ? placement?.team ?? signup.team : ""
    const assignedRole = team ? placement?.role ?? signup.assigned_role : ""
    const rating = assignedRole ? signup.ratings[assignedRole] ?? 0 : signup.best_rating
    return {
      ...signup,
      is_selected: isSelected,
      team,
      assigned_role: assignedRole,
      rating_used: rating,
    }
  })
}

export function splitZones(board: ScrimBoard, values: SplitValues): SplitZone[] {
  const format = board.scrim?.format ?? "rq_5v5"
  const requirements = roleRequirements(format)
  const signups = projectedSignups(board, values)
  const zones: SplitZone[] = []
  for (const team of ["a", "b"] as const) {
    for (const [role, capacity] of Object.entries(requirements)) {
      zones.push({
        key: `${team}:${role}`,
        team,
        role,
        label: roleLabel(role),
        capacity,
        members: signups.filter((signup) => signup.team === team && (role === "" || signup.assigned_role === role)),
      })
    }
    // Imported/changed format may leave an assignment outside its new roles.
    // Keep such people visible and movable, rather than silently dropping them.
    const knownRoles = new Set(Object.keys(requirements))
    const unassigned = signups.filter((signup) => signup.team === team && !knownRoles.has(signup.assigned_role))
    if (unassigned.length && !knownRoles.has("")) zones.push({
      key: `${team}:unassigned`,
      team,
      role: "",
      label: "未分位置",
      capacity: 0,
      members: unassigned,
    })
  }
  zones.push({
    key: "buffer",
    team: "",
    role: "",
    label: "缓冲区（不上场）",
    capacity: 0,
    members: signups.filter((signup) => signup.is_selected && !signup.team),
  })
  return zones
}

export function sideTotal(zones: SplitZone[], team: Side): number {
  return zones.filter((zone) => zone.team === team).flatMap((zone) => zone.members)
    .reduce((total, signup) => total + (signup.rating_used ?? 0), 0)
}

export function sideProblems(zones: SplitZone[], format: string, team: Side): string[] {
  const teamZones = zones.filter((zone) => zone.team === team)
  const count = teamZones.reduce((sum, zone) => sum + zone.members.length, 0)
  const problems: string[] = []
  if (count !== teamSize(format)) problems.push(`人数 ${count}/${teamSize(format)}`)
  for (const zone of teamZones) {
    if (zone.capacity && zone.members.length !== zone.capacity) problems.push(`${zone.label} ${zone.members.length}/${zone.capacity}`)
    for (const signup of zone.members) {
      if (zone.role && !signup.roles.includes(zone.role)) problems.push(`${signup.nickname} 没选${zone.label}`)
      if (zone.role && signup.ratings[zone.role] === undefined) problems.push(`${signup.nickname} ${zone.label}没有段位`)
    }
  }
  return [...new Set(problems)]
}

export function moveSignup(
  board: ScrimBoard,
  values: SplitValues,
  signupId: number,
  zoneKey: string,
): { values: SplitValues; message: string } {
  const signup = board.signups.find((item) => item.signup_id === signupId)
  const zones = splitZones(board, values)
  const target = zones.find((zone) => zone.key === zoneKey)
  if (!signup || !target) return { values, message: "这个人或目标位置已经不存在，请刷新名单。" }
  if (target.team && !values.signup_ids.includes(signupId)) return { values, message: "请先勾选这个人上场。" }
  const existing = values.placements.find((placement) => placement.signup_id === signupId)
  const targetCount = zones.filter((zone) => zone.team === target.team).reduce((count, zone) => count + zone.members.length, 0)
  if (target.team && existing?.team !== target.team && targetCount >= teamSize(board.scrim?.format ?? "rq_5v5")) {
    return { values, message: "队伍满员时不能直接移进去，先把要换下来的人移到缓冲区。" }
  }
  const next = structuredClone(values)
  const placement = next.placements.find((item) => item.signup_id === signupId)
  if (!placement) return { values, message: "名单已经变动，请刷新名单。" }
  placement.team = target.team
  placement.role = target.role
  return { values: next, message: "" }
}

/** The card's keyboard mapping is independent of Vue and the DOM. */
export function keyboardSide(event: Pick<KeyboardEvent, "key" | "altKey" | "ctrlKey" | "metaKey">): Side | null {
  if (!event.altKey || event.ctrlKey || event.metaKey) return null
  if (event.key === "ArrowLeft") return "a"
  if (event.key === "ArrowRight") return "b"
  if (event.key === "ArrowDown") return ""
  return null
}

export function bestTarget(zones: SplitZone[], signup: ScrimSignup, team: Side): SplitZone | null {
  if (!team) return zones.find((zone) => zone.team === "") ?? null
  const possible = zones.filter((zone) => zone.team === team)
  return possible.find((zone) => !zone.role || signup.roles.includes(zone.role)) ?? possible[0] ?? null
}

export function currentSplit(value: unknown): SaveCurrent<SplitValues> | null {
  const outer = record(value)
  if (!outer) return null
  const board = record(outer.board) ?? outer
  const version = board.board_version
  if (!Number.isSafeInteger(version) || Number(version) < 0 || !Array.isArray(board.signups)) return null
  const signupIds: number[] = []
  const seen = new Set<number>()
  const placements: Placement[] = []
  for (const candidate of board.signups) {
    const signup = record(candidate)
    if (!signup || !Number.isSafeInteger(signup.signup_id) || Number(signup.signup_id) <= 0) return null
    const id = Number(signup.signup_id)
    if (seen.has(id)) return null
    seen.add(id)
    if (typeof signup.is_selected !== "boolean" || typeof signup.team !== "string" || typeof signup.assigned_role !== "string") return null
    if (!["", "a", "b"].includes(signup.team)) return null
    if (!["", "tank", "damage", "support"].includes(signup.assigned_role)) return null
    if (signup.is_selected) signupIds.push(Number(signup.signup_id))
    placements.push({ signup_id: Number(signup.signup_id), team: signup.team, role: signup.assigned_role })
  }
  return { version: Number(version), values: { signup_ids: signupIds, placements } }
}

export function boardFromCurrent(value: unknown): ScrimBoard | null {
  const outer = record(value)
  if (!outer) return null
  const board = record(outer.board) ?? outer
  if (!currentSplit(board)) return null
  if (!Array.isArray(board.teams) || !Array.isArray(board.bench) || !record(board.scrim)) return null
  if (typeof board.copy_text !== "string" || typeof board.has_teams !== "boolean" || typeof board.teams_stale !== "boolean") return null
  return board as unknown as ScrimBoard
}
