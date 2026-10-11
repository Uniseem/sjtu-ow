import type { ScrimBoard, ScrimSignup, TournamentBoard, TournamentEntry } from "./domain"

const at = "2026-10-11T10:00:00Z"

export function tournamentEntry(id: number, registration: number | null = null, conflict = ""): TournamentEntry {
  const entry = {
    signup_id: id,
    user_id: id + 100,
    nickname: `成员${id}`,
    battletag: `Player${id}#1000`,
    roles: ["tank", "damage"],
    rank_tank: 20,
    rank_damage: 15,
    rank_support: null,
    registration_id: registration,
    conflict,
    is_active: true,
    is_sjtu: true,
  }
  return entry
}

export function tournamentBoard(): TournamentBoard & { pool_version: number; roster_min: number } {
  const tournament = {
    id: 7,
    title: "编队赛事",
    summary: "赛事简介",
    cover_image_id: null,
    default_cover_image_id: null,
    starts_at: at,
    registration_opens_at: "2026-10-01T10:00:00Z",
    registration_closes_at: "2026-10-20T10:00:00Z",
    registration_mode: "individual",
    registration_mode_label: "个人报名",
    takes_individuals: true,
    roster_min: 2,
    roster_max: 2,
    sjtu_only: false,
    status: "published",
    phase: "open",
    approved_count: 2,
  }
  return {
    tournament,
    roster_min: 2,
    roster_max: 2,
    pool_version: 12,
    entries: [tournamentEntry(1, 40), tournamentEntry(2, 40), tournamentEntry(3, 41), tournamentEntry(4)],
    teams: [
      { registration_id: 40, name: "第一队", roster_version: 3, signup_ids: [1, 2] },
      { registration_id: 41, name: "第二队", roster_version: 5, signup_ids: [3] },
    ],
  }
}

export function scrimSignup(id: number, team = "", role = "", selected = true): ScrimSignup {
  const result = {
    signup_id: id,
    user_id: id + 100,
    nickname: `成员${id}`,
    battletag: `Player${id}#1000`,
    roles: ["tank", "damage", "support"],
    ratings: { tank: 10, damage: 20, support: 30 },
    rank_text: { tank: "白银 5", damage: "钻石 5", support: "宗师 5" },
    best_rating: 30,
    is_selected: selected,
    team,
    assigned_role: role,
    rating_used: role === "tank" ? 10 : role === "damage" ? 20 : role === "support" ? 30 : null,
    is_active: true,
    is_sjtu: true,
    created_at: at,
  }
  return result
}

export function scrimBoard(signups: ScrimSignup[] = [scrimSignup(1, "a", "tank"), scrimSignup(2, "b", "tank"), scrimSignup(3)]): ScrimBoard {
  const scrim = {
    id: 8,
    title: "分队内战",
    description: "内战说明",
    starts_at: at,
    signup_closes_at: null,
    format: "rq_5v5",
    sjtu_only: false,
    status: "published",
    version: 3,
    board_version: 20,
    default_cover_image_id: null,
    created_at: at,
    updated_at: at,
  }
  const board = {
    scrim,
    order: "created",
    signups,
    selected_count: signups.filter((signup) => signup.is_selected).length,
    needed: 10,
    teams: [
      { team: "a", label: "A 队", total: 10, problems: [], members: signups.filter((signup) => signup.team === "a") },
      { team: "b", label: "B 队", total: 10, problems: [], members: signups.filter((signup) => signup.team === "b") },
    ],
    bench: signups.filter((signup) => signup.is_selected && !signup.team),
    gap: 0,
    has_teams: signups.some((signup) => Boolean(signup.team)),
    teams_stale: false,
    copy_text: "服务端确认的分队文字",
    board_version: 20,
    show_contacts: false,
  }
  return board
}
