import { describe, expect, test } from "vitest"
import { handle } from "../server"
import type {
  GetApiSessionOut, GetApiTeamsIdOut, GetApiTeamsIdManageOut,
  GetApiMembersIdOut, GetApiTournamentsIdOut, GetApiTournamentsIdRegisterOut,
  GetApiTournamentsIdSignupOut, GetApiRegistrationsIdOut, GetApiScrimsIdOut,
  GetApiMeProfileOut,
} from "@sjtu-ow/api"

const joined = "2026-09-30T20:30:00Z" // Shanghai: October 1, 04:30.
const starts = "2026-10-11T16:30:00Z" // Shanghai: October 12, 00:30.
const hiddenRank = { score: null, label: "未定级", is_expired: false }
const zeroRank = { score: 0, label: "青铜 5", is_expired: false }
const privateGame = "OwnPlayer#1000"
const snapshotGame = "SnapshotPlayer#2000"
const participantContact = "选手专用群 123456"

type SessionUser = NonNullable<GetApiSessionOut["user"]>
function session(): GetApiSessionOut {
  return {
    user: {
      avatar_image_id: null, default_avatar_image_id: null, avatar_can_upload: true,
      avatar_denied: "", avatar_turned_down: null, max_game_accounts: 5,
      profile_gaps: [], waiting_letters: 0, deletion_blockers: [],
      id: 41, nickname: "当前成员", email: "current@example.invalid",
      admin: false, superuser: false, caps: [], email_verified: true,
      is_sjtu: true, can_submit_article: true, can_comment: true,
    },
  }
}

function profile(): GetApiMeProfileOut {
  return {
    avatar_image_id: null, default_avatar_image_id: null, avatar_can_upload: true,
    avatar_denied: "", avatar_turned_down: null, max_game_accounts: 5,
    profile_gaps: [], waiting_letters: 0, deletion_blockers: [],
    id: 41, nickname: "当前成员", email: "current@example.invalid", is_sjtu: true,
    motto: "", main_role: "tank", flex_roles: "", show_rank: true,
    version: 3, is_complete: true,
    public_ranks: { tank: zeroRank, damage: hiddenRank, support: hiddenRank },
    game_accounts: [{ id: 121, version: 1, saved: [], saved_at: joined,
      battletag: privateGame, rank_tank: 0, rank_damage: null, rank_support: null,
      tank_label: "青铜 5", damage_label: "未定级", support_label: "未定级", ranks_updated_at: joined }],
    contacts: [{ id: 151, version: 1, saved: [], saved_at: joined, type: "qq", type_label: "QQ", value: "123456", created_at: joined }],
  }
}

function teamMember(id = 41): GetApiTeamsIdOut["members"][number] {
  return {
    avatar_image_id: null, default_avatar_image_id: null, motto: "公开宣言",
    member_url: `/members/${id}/`, user_id: id, nickname: id === 41 ? "当前成员" : "另一成员",
    is_active: true, main_role: "tank", roles: ["tank"],
    ranks: { tank: zeroRank, damage: hiddenRank, support: hiddenRank },
    role: id === 41 ? "captain" : "member", joined_at: joined,
  }
}

function teamPage(): GetApiTeamsIdOut {
  return {
    entries: [{ id: 90, tournament_id: 7, title: "通过的赛事", status: "published" }],
    team: { id: 5, name: "晨光战队", description: "公开战队简介", logo_image_id: null,
      is_recruiting: true, recruiting_roles: ["support"], version: 8,
      created_at: joined, updated_at: joined },
    members: [teamMember(), teamMember(42)], alumni: [], max_members: 10,
    viewer: { is_member: false, is_captain: false, is_superuser: false,
      can_apply: false, apply_reason: "", needs_game_account: false },
  }
}

function memberPage(): GetApiMembersIdOut {
  return {
    card: { avatar_image_id: null, default_avatar_image_id: null,
      user_id: 42, number: 2, nickname: "另一成员", motto: "公开宣言", main_role: "tank",
      roles: ["tank"], ranks: { tank: zeroRank, damage: hiddenRank, support: hiddenRank },
      teams: [{ id: 5, name: "晨光战队" }], groups: ["赛事组"], titles: ["队员"] },
    groups: [{ id: 2, name: "赛事组", titles: ["队员"] }],
    teams: [{ id: 5, name: "晨光战队", member_count: 2, logo_image_id: null, is_recruiting: true, is_captain: false }],
    alumni: [], articles: [], article_count: 0, is_owner: false,
  }
}

function tournamentPage(): GetApiTournamentsIdOut {
  const tournament: NonNullable<GetApiTournamentsIdOut["tournament"]> = {
    id: 7, title: "十月赛事", summary: "公开赛事简介", description: "原始 Markdown",
    cover_image_id: null, default_cover_image_id: null, starts_at: starts,
    registration_opens_at: "2026-09-30T00:00:00Z", registration_closes_at: "2026-10-11T15:30:00Z",
    roster_min: 2, roster_max: 3, sjtu_only: false, registration_mode: "individual",
    auto_approve: false, status: "published", version: 4, created_at: joined, updated_at: joined,
  }
  return {
    tournament, phase: "open", phase_label: "报名中",
    approved_teams: [{ registration_id: 90, team_id: null, team_name: "临时一队", member_count: 2, is_adhoc: true }],
    pool: { total: 1, tank: 1, damage: 0, support: 1,
      entries: [{ avatar_image_id: null, signup_id: 81, user_id: 42, nickname: "散人同学", roles: ["tank", "support"] }] },
    viewer: { registration_open: true, captain_teams: [], on_roster: null,
      my_signup: null, individual_problems: [], is_manager: false },
    card: { id: 7, title: tournament.title, summary: tournament.summary, cover_image_id: null,
      starts_at: starts, registration_opens_at: tournament.registration_opens_at,
      registration_closes_at: tournament.registration_closes_at, registration_mode: "individual",
      sjtu_only: false, status: "published", phase: "open", approved_count: 1,
      roster_min: 2, roster_max: 3, registration_mode_label: "个人报名", takes_individuals: true, default_cover_image_id: null },
    body_html: "<h2>正式赛规</h2><p>服务端渲染的公开说明。</p>", default_cover_image_id: null,
    articles: [{ id: 14, title: "赛事安排文章", slug: "event-plan", url: "/news/event-plan/", first_published_at: joined }],
  }
}

function registrationPage(): GetApiRegistrationsIdOut {
  const tournament = { ...tournamentPage().card, registration_mode: "team", registration_mode_label: "整队报名", takes_individuals: false }
  return {
    registration: { status_label: "已通过", id: 90, tournament_id: 7, team_id: 5,
      status: "approved", team_name: "晨光战队", roster_version: 6, submitted_by: 41,
      submitted_at: joined, status_note: "审核通过备注", created_at: joined, updated_at: joined },
    tournament,
    roster: [{ rank_labels: ["坦克 青铜 5"], rank_summary: "坦克 青铜 5",
      id: 61, user_id: 41, game_account_id: 121, nickname: "提交时的昵称", battletag: snapshotGame,
      is_sjtu: true, rank_tank: 0, rank_damage: null, rank_support: null, is_captain: true, is_active: true }],
    logs: [{ action_label: "通过", from_status_label: "待审核", to_status_label: "已通过",
      actor_type_label: "本站管理员", id: 50, action: "approve", from_status: "pending", to_status: "approved",
      actor_type: "admin", actor_user_id: 9, roster_version: 6, note: "管理员的真实审核备注", created_at: joined }],
    is_captain: true, can_withdraw: true, can_resubmit: true, roster_differs: true,
    can_leave: false, participant_contact: participantContact,
    is_adhoc: false, can_change: true, resubmittable: false, status_label: "已通过",
  }
}

function registerForm(): GetApiTournamentsIdRegisterOut {
  const tournament = tournamentPage().tournament!
  tournament.registration_mode = "team"
  return {
    tournament,
    teams: [{ id: 5, name: "晨光战队", version: 8 }, { id: 6, name: "第二战队", version: 2 }],
    team: { id: 5, name: "晨光战队", version: 8 },
    rows: [
      { user_id: 41, nickname: "队长同学", is_captain: true, is_sjtu: true,
        accounts: [{ id: 121, battletag: privateGame, rank_tank: 0, rank_damage: null, rank_support: null },
          { id: 122, battletag: "OtherOwnPlayer#1000", rank_tank: 5, rank_damage: null, rank_support: null }],
        selected_account_id: 121, problems: [] },
      { user_id: 42, nickname: "队员同学", is_captain: false, is_sjtu: false,
        accounts: [{ id: 123, battletag: "RosterMember#1000", rank_tank: null, rank_damage: 10, rank_support: null }],
        selected_account_id: 123, problems: [] },
    ],
    existing: registrationPage().registration, problems: [], can_submit: true,
  }
}

function individualForm(): GetApiTournamentsIdSignupOut {
  return { tournament: tournamentPage().tournament,
    game_accounts: [{ id: 121, battletag: privateGame, rank_tank: 0, rank_damage: null, rank_support: null }],
    my_signup: null, registration_team_name: "", problems: [], can_submit: true, can_cancel: false }
}

function scrimPage(): GetApiScrimsIdOut {
  return {
    scrim: { default_cover_image_id: null, id: 8, title: "十月内战", description: "原始说明",
      starts_at: starts, signup_closes_at: null, format: "rq_5v5", sjtu_only: false,
      status: "published", version: 4, board_version: 3, created_at: joined, updated_at: joined },
    card: { id: 8, title: "十月内战", starts_at: starts, signup_deadline: starts,
      format: "rq_5v5", format_label: "角色限定 5v5", sjtu_only: false, status: "published",
      signup_open: true, signup_total: 1, players_needed: 10, default_cover_image_id: null },
    counts: { total: 1, tank: 1, damage: 0, support: 1 },
    signups: [{ user_id: 42, avatar_image_id: null, nickname: "公开报名同学", roles: ["tank", "support"] }],
    mine: null, problems: [], body_html: "<h2>内战说明</h2><p>服务端内战正文。</p>",
    default_cover_image_id: null, group_url: "", game_accounts: [],
  }
}

function scrimForMember(): GetApiScrimsIdOut {
  const data = scrimPage()
  data.game_accounts = [{ id: 121, battletag: privateGame, rank_tank: 0, rank_damage: null, rank_support: null }]
  return data
}
function addOwnPublicSignup(data: GetApiScrimsIdOut): void {
  data.signups.push({ user_id: 41, avatar_image_id: null, nickname: "当前成员", roles: ["tank"] })
  data.counts.total += 1
  data.counts.tank += 1
  data.card.signup_total += 1
}

type APIResult = { data: unknown; status?: number }
async function page(url: string, user: SessionUser | null, results: Record<string, APIResult>) {
  const asked: string[] = []
  const response = await handle({ method: "GET", url, headers: { get: () => null } }, {
    apiBase: "https://api.example.invalid",
    fetch: async (input, init) => {
      const method = init?.method ?? "GET"
      expect(method, "SSR must never save/create/notify while rendering").toBe("GET")
      const address = new URL(String(input))
      const path = address.pathname
      asked.push(path + address.search)
      if (path === "/api/session") return Response.json({ user } satisfies GetApiSessionOut)
      const result = results[path]
      if (!result) throw new Error("unexpected endpoint: " + path)
      return Response.json(result.data, { status: result.status ?? 200 })
    },
  })
  return { ...response, asked }
}

function main(html: string): string {
  const result = html.match(/<main\b[\s\S]*?<\/main>/)
  if (!result) throw new Error("SSR response contained no main element")
  return result[0]
}
function text(html: string): string { return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim() }
function selectedOption(html: string, value: number): string {
  return html.match(new RegExp(`<option[^>]*value="${value}"[^>]*>`))?.[0] ?? ""
}
function checkedInput(html: string, value: string): string {
  return html.match(new RegExp(`<input[^>]*value="${value}"[^>]*>`))?.[0] ?? ""
}
function select(html: string, id: string): string {
  return html.match(new RegExp(`<select[^>]*id="${id}"[^>]*>[\\s\\S]*?</select>`))?.[0] ?? ""
}
const missing = { error: { code: "not_found", message: "找不到这个页面" } }
const forbidden = { error: { code: "forbidden", message: "没有权限做这件事" } }

// Fixtures are explicitly typed from apigen and follow each backend projection:
// public rosters contain no game IDs/contact fields; private forms contain only
// the current captain's selectable roster; scrim placement exists only in mine.
describe("F6 SSR public/private team and member projections", () => {
  test("visitor sees public roster, rank zero and Shanghai date, with login action", async () => {
    const result = await page("/teams/5/", null, { "/api/teams/5": { data: teamPage() } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("晨光战队")
    expect(visible.replace(/<[^>]+>/g, "").replace(/<!--.*?-->/g, "")).toContain("青铜 5")
    expect(visible).toContain("2026.10.01")
    expect(visible).toContain("登录后申请")
    expect(visible).toContain('href="/members/41/"')
    expect(visible).not.toContain(privateGame)
    expect(visible).not.toContain("队内联系方式")
    expect(result.asked.sort()).toEqual(["/api/session", "/api/teams/5"].sort())
  })

  test("member receives team contact and leave control, captain receives management", async () => {
    const member = teamPage()
    member.team!.member_contact = "队内专用 QQ 567890"
    member.viewer.is_member = true
    const normal = await page("/teams/5/", session().user, { "/api/teams/5": { data: member } })
    expect(normal.status).toBe(200)
    expect(text(main(normal.body))).toContain("队内专用 QQ 567890")
    expect(main(normal.body)).toContain("退出战队")
    expect(main(normal.body)).not.toContain("管理战队")
    member.viewer.is_captain = true
    const captain = await page("/teams/5/", session().user, { "/api/teams/5": { data: member } })
    expect(captain.status).toBe(200)
    expect(main(captain.body)).toContain('href="/teams/5/manage/"')
    expect(main(captain.body)).not.toContain("退出战队")
  })

  test("stopped public member loses profile link/avatar/play and keeps stopped label", async () => {
    const data = teamPage()
    Object.assign(data.members[1]!, { is_active: false, member_url: null, motto: "",
      roles: [], avatar_image_id: null, default_avatar_image_id: null,
      ranks: { tank: hiddenRank, damage: hiddenRank, support: hiddenRank } })
    const result = await page("/teams/5/", null, { "/api/teams/5": { data } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("账号已停用")
    expect(visible).toContain("另一成员")
    expect(visible).not.toContain('href="/members/42/"')
  })

  test("missing team and unauthorized management retain backend 404 rather than rendering success", async () => {
    for (const url of ["/teams/999/", "/teams/5/manage/"]) {
      const endpoint = url.includes("manage") ? "/api/teams/5/manage" : "/api/teams/999"
      const result = await page(url, session().user, { [endpoint]: { data: missing, status: 404 } })
      expect(result.status).toBe(404)
      expect(main(result.body)).not.toContain("解散战队")
    }
    const result = await page("/teams/5/manage/", session().user, { "/api/teams/5/manage": { data: forbidden, status: 403 } })
    expect(result.status).toBe(403)
  })

  test("authorized management renders only returned private IDs and no automatic writes", async () => {
    const detail = teamPage()
    const manage: GetApiTeamsIdManageOut = { team: detail.team, members: detail.members,
      alumni: [], pending: [], disband_blockers: ["尚有进行中的赛事报名"], max_members: 10 }
    manage.members[0]!.game_accounts = [{ id: 121, battletag: privateGame, rank_summary: "坦克 青铜 5" }]
    manage.members[0]!.game_ids = [privateGame]
    const result = await page("/teams/5/manage/", session().user, { "/api/teams/5/manage": { data: manage } })
    expect(result.status).toBe(200)
    expect(main(result.body)).toContain(privateGame)
    expect(main(result.body)).toContain("暂时不能解散")
    expect(main(result.body)).toContain("尚有进行中的赛事报名")
    expect(result.asked).not.toContain("/api/me/profile")
  })

  test("public member respects hidden ranks and does not obtain own profile/contact API", async () => {
    const member = memberPage()
    member.card.ranks = { tank: hiddenRank, damage: hiddenRank, support: hiddenRank }
    const result = await page("/members/42/", session().user, { "/api/members/42": { data: member } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("公开宣言")
    expect(visible).not.toContain("青铜 5")
    expect(visible).not.toContain("编辑资料")
    expect(visible).not.toContain(privateGame)
    expect(result.asked.sort()).toEqual(["/api/session", "/api/members/42"].sort())
  })

  test("inaccessible member profile remains 404 and does not disclose private fields", async () => {
    const result = await page("/members/999/", session().user, { "/api/members/999": { data: missing, status: 404 } })
    expect(result.status).toBe(404)
    expect(result.body).not.toContain(privateGame)
    expect(result.asked).not.toContain("/api/me/profile")
  })

  test("only owner projection reveals edit hints; rank zero is not treated as absent", async () => {
    const member = memberPage()
    member.card.user_id = 41
    member.card.nickname = "当前成员"
    member.card.motto = ""
    member.is_owner = true
    const result = await page("/members/41/", session().user, { "/api/members/41": { data: member } })
    expect(result.status).toBe(200)
    expect(main(result.body)).toContain("编辑资料")
    expect(main(result.body)).toContain("还没写个人宣言")
    expect(main(result.body)).toContain("青铜 5")
  })
})

describe("F7 SSR event projections and explicit registration forms", () => {
  test("visitor reads server-rendered tournament rules and public pool, with login action", async () => {
    const result = await page("/tournaments/7/", null, { "/api/tournaments/7": { data: tournamentPage() } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("<h2>正式赛规</h2>")
    expect(visible).not.toContain("&lt;h2&gt;正式赛规")
    expect(visible).not.toContain("原始 Markdown")
    expect(visible).toContain("散人同学")
    expect(visible).toContain("临时一队")
    expect(visible).toContain("登录后报名")
    expect(visible).toContain('href="/news/event-plan/"')
    expect(visible).toContain("2026.10.12 00:30")
    expect(visible).not.toContain(privateGame)
    expect(visible).not.toContain(participantContact)
    expect(result.asked.sort()).toEqual(["/api/session", "/api/tournaments/7"].sort())
  })

  test("member gets personal signup link; closed projection removes edit/cancel controls", async () => {
    const data = tournamentPage()
    const open = await page("/tournaments/7/", session().user, { "/api/tournaments/7": { data } })
    expect(open.status).toBe(200)
    expect(main(open.body)).toContain('href="/tournaments/7/signup/"')
    data.phase = "closed"
    data.phase_label = "已截止"
    data.card.phase = "closed"
    data.viewer.registration_open = false
    data.tournament!.registration_closes_at = "2026-10-10T16:30:00Z"
    data.card.registration_closes_at = data.tournament!.registration_closes_at
    data.viewer.my_signup = { id: 82, game_account_id: 121, roles: ["tank"], placed: false, registration_id: null, created_at: joined }
    const closed = await page("/tournaments/7/", session().user, { "/api/tournaments/7": { data } })
    expect(closed.status).toBe(200)
    const visible = main(closed.body)
    expect(visible).toContain("已个人报名，等待编队")
    expect(visible).not.toContain("修改报名")
    expect(visible).not.toContain("取消报名")
  })

  test("placed individual uses returned registration id and participating contact", async () => {
    const data = tournamentPage()
    data.viewer.my_signup = { id: 82, game_account_id: 121, roles: ["tank"], placed: true, registration_id: 90, created_at: joined }
    data.tournament!.participant_contact = participantContact
    data.viewer.participant_contact = participantContact
    const result = await page("/tournaments/7/", session().user, { "/api/tournaments/7": { data } })
    expect(result.status).toBe(200)
    expect(main(result.body)).toContain('href="/registrations/90/"')
    expect(main(result.body)).toContain(participantContact)
    expect(main(result.body)).not.toContain("修改报名")
    expect(main(result.body)).not.toContain("取消报名")
  })

  test("team-mode captain action is supplied by real captain teams, ordinary member cannot reconstruct it", async () => {
    const data = tournamentPage()
    data.tournament!.registration_mode = "team"
    data.card.registration_mode = "team"
    data.card.registration_mode_label = "整队报名"
    data.card.takes_individuals = false
    data.pool = null
    data.viewer.captain_teams = [{ team_id: 5, name: "晨光战队", registration: null, problems: [] }]
    const captain = await page("/tournaments/7/", session().user, { "/api/tournaments/7": { data } })
    expect(captain.status).toBe(200)
    expect(main(captain.body)).toContain('href="/tournaments/7/register/"')
    data.viewer.captain_teams = []
    const ordinary = await page("/tournaments/7/", session().user, { "/api/tournaments/7": { data } })
    expect(ordinary.status).toBe(200)
    expect(main(ordinary.body)).toContain("需要由队长为战队报名")
    expect(main(ordinary.body)).not.toContain('href="/tournaments/7/register/"')
  })

  test("cancelled event retains detail and rules but exposes no signup action", async () => {
    const data = tournamentPage()
    data.tournament!.status = "cancelled"
    data.card.status = "cancelled"
    data.phase = "cancelled"
    data.phase_label = "已取消"
    data.viewer.registration_open = false
    const result = await page("/tournaments/7/", session().user, { "/api/tournaments/7": { data } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("这项赛事已取消")
    expect(visible).toContain("正式赛规")
    expect(visible).not.toContain('href="/tournaments/7/signup/"')
  })

  test("team registration renders real members, selected game IDs and existing immutable roster version", async () => {
    const result = await page("/tournaments/7/register/?team=5", session().user, { "/api/tournaments/7/register": { data: registerForm() } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("队长同学")
    expect(visible).toContain("队员同学")
    expect(visible).toContain("不需要队员确认")
    expect(visible).toContain("名单版本 6")
    expect(selectedOption(select(visible, "account-41"), 121)).toMatch(/\bselected(?:\s|=|>)/)
    expect(select(visible, "account-42")).toContain("RosterMember#1000")
    expect(select(visible, "account-42")).not.toContain(privateGame)
    expect(result.asked).toContain("/api/tournaments/7/register?team=5")
    expect(result.asked).not.toContain("/api/me/profile")
  })

  test("member missing game IDs keeps all validation messages and disables submission", async () => {
    const form = registerForm()
    form.rows[1]!.accounts = []
    form.rows[1]!.selected_account_id = null
    form.rows[1]!.problems = ["队员同学 的资料不完整（缺少游戏 ID）"]
    form.problems = [...form.rows[1]!.problems]
    form.can_submit = false
    const result = await page("/tournaments/7/register/", session().user, { "/api/tournaments/7/register": { data: form } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("这位队员还没有填写游戏 ID")
    expect(visible).toContain("下面的问题需要先解决")
    expect(visible).toMatch(/<button[^>]*disabled[^>]*>提交报名<\/button>/)
    expect(select(visible, "account-42")).toBe("")
  })

  test("placed personal registration cannot be edited or cancelled by its owner", async () => {
    const form = individualForm()
    form.my_signup = { id: 82, game_account_id: 121, roles: ["tank"], placed: true, registration_id: 90, created_at: joined }
    form.registration_team_name = "管理员编排队伍"
    form.can_submit = false
    form.can_cancel = false
    const result = await page("/tournaments/7/signup/", session().user, { "/api/tournaments/7/signup": { data: form } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("管理员编排队伍")
    expect(visible).toContain("要改动请联系赛事管理员")
    expect(visible).not.toContain('id="signup-account"')
    expect(visible).not.toContain("取消报名")
  })

  test("personal registration keeps chosen account and existing role checkbox from actual signup", async () => {
    const form = individualForm()
    form.game_accounts.push({ id: 122, battletag: "ChosenOwn#2000", rank_tank: null, rank_damage: 10, rank_support: null })
    form.my_signup = { id: 82, game_account_id: 122, roles: ["damage"], placed: false, registration_id: null, created_at: joined }
    form.can_cancel = true
    const result = await page("/tournaments/7/signup/", session().user, { "/api/tournaments/7/signup": { data: form } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(selectedOption(select(visible, "signup-account"), 122)).toMatch(/\bselected(?:\s|=|>)/)
    expect(checkedInput(visible, "damage")).toMatch(/\bchecked(?:\s|=|>)/)
    expect(visible).toContain("保存修改")
    expect(visible).toContain("返回赛事")
    expect(visible).not.toContain("取消个人报名")
  })

  test("registration detail renders server snapshot, status history and Shanghai timestamp without reloading live profile", async () => {
    const result = await page("/registrations/90/", session().user, { "/api/registrations/90": { data: registrationPage() } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("名单快照")
    expect(visible).toContain("提交时的昵称")
    expect(visible).toContain(snapshotGame)
    expect(visible).not.toContain(privateGame)
    expect(visible).toContain("坦克 青铜 5")
    expect(visible).toContain("名单版本 6")
    expect(visible).toContain("管理员的真实审核备注")
    expect(visible).toContain("2026.10.01 04:30")
    expect(visible).toContain('href="/tournaments/7/register/?team=5"')
    expect(visible).toContain("撤回报名")
    expect(visible).toContain(participantContact)
    expect(result.asked.sort()).toEqual(["/api/session", "/api/registrations/90"].sort())
  })

  test("temporary roster member gets leave, never captain sync/withdraw controls", async () => {
    const data = registrationPage()
    data.registration!.team_id = null
    data.registration!.team_name = "临时一队"
    data.is_captain = false
    data.is_adhoc = true
    data.can_withdraw = false
    data.can_resubmit = false
    data.can_change = false
    data.can_leave = true
    data.roster_differs = false
    const result = await page("/registrations/90/", session().user, { "/api/registrations/90": { data } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("退出队伍")
    expect(visible).toContain("临时队伍")
    expect(visible).not.toContain("撤回报名")
    expect(visible).not.toContain("同步名单")
    expect(visible).not.toContain("register/?team=null")
  })

  test("unknown private registration and inaccessible event preserve API status", async () => {
    const notFound = await page("/registrations/999/", session().user, { "/api/registrations/999": { data: missing, status: 404 } })
    expect(notFound.status).toBe(404)
    const noPermission = await page("/tournaments/7/register/", session().user, { "/api/tournaments/7/register": { data: forbidden, status: 403 } })
    expect(noPermission.status).toBe(403)
    const hidden = await page("/tournaments/999/", null, { "/api/tournaments/999": { data: missing, status: 404 } })
    expect(hidden.status).toBe(404)
  })
})

describe("scrim SSR public roster and private placement", () => {
  test("visitor reads public signup names/roles and body but no game ID or placement", async () => {
    const result = await page("/scrims/8/", null, { "/api/scrims/8": { data: scrimPage() } })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("公开报名同学")
    expect(visible).toContain("<h2>内战说明</h2>")
    expect(visible).toContain("2026.10.12 00:30")
    expect(visible).toContain("登录后报名")
    expect(visible).not.toContain(privateGame)
    expect(visible).not.toContain("当前分队")
    expect(result.asked).not.toContain("/api/me/profile")
  })

  test("eligible member sees only own game IDs as form options and no public placement", async () => {
    const result = await page("/scrims/8/", session().user, {
      "/api/scrims/8": { data: scrimForMember() }, "/api/me/profile": { data: profile() },
    })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain(privateGame)
    expect(visible).toContain("勾选的每个位置都要在这个游戏 ID 上填了段位")
    expect(selectedOption(select(visible,"scrim-8-account"),121)).toMatch(/\bselected(?:\s|=|>)/)
    expect(select(visible,"scrim-8-account")).not.toContain("请选择")
    expect(visible).not.toContain(snapshotGame)
    expect(visible).not.toContain("当前分队")
    expect(result.asked).not.toContain("/api/admin/scrims/8/board")
  })

  test("missing contact uses real service blocker and removes signup form", async () => {
    const data = scrimForMember()
    data.problems = ["资料不完整（缺少联系方式）"]
    const incomplete = profile()
    incomplete.contacts = []
    incomplete.is_complete = false
    incomplete.profile_gaps = [{ label: "联系方式", href: "/me/contacts/", hint: "添加一个联系方式" }]
    const incompleteSession = session().user!
    incompleteSession.profile_gaps = [...incomplete.profile_gaps]
    const result = await page("/scrims/8/", incompleteSession, {
      "/api/scrims/8": { data }, "/api/me/profile": { data: incomplete },
    })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("资料不完整（缺少联系方式）")
    expect(visible).toContain('href="/me/contacts/"')
    expect(text(visible)).toContain("去补全：联系方式")
    expect(visible).not.toContain('href="/me/game-accounts/" class="c-link"')
    expect(visible).not.toContain('id="scrim-8-account"')
  })

  test("only own mine field renders game ID, placement and cancellation", async () => {
    const data = scrimForMember()
    addOwnPublicSignup(data)
    data.group_url = "https://qm.qq.com/example-test-club"
    data.mine = { id: 88, game_account_id: 121, roles: ["tank"], placement: "A 队 · 坦克",
      can_cancel: true, can_edit: true, battletag: privateGame }
    data.game_accounts = [{ id: 121, battletag: privateGame, rank_tank: 0, rank_damage: null, rank_support: null }]
    const result = await page("/scrims/8/", session().user, {
      "/api/scrims/8": { data }, "/api/me/profile": { data: profile() },
    })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(text(visible)).toContain("当前分队： A 队 · 坦克")
    expect(visible).toContain(privateGame)
    expect(visible).toContain('href="https://qm.qq.com/example-test-club"')
    expect(visible).toContain("取消报名")
    expect(visible).not.toContain("B 队 · 输出")
    expect(result.asked).not.toContain("/api/admin/scrims/8/board")
  })

  test("closed scrim keeps own placement but removes edits/cancellation", async () => {
    const data = scrimForMember()
    data.card.signup_open = false
    data.scrim!.starts_at = "2026-10-10T16:30:00Z"
    data.card.starts_at = data.scrim!.starts_at
    data.card.signup_deadline = data.scrim!.starts_at
    addOwnPublicSignup(data)
    data.mine = { id: 88, game_account_id: 121, roles: ["tank"], placement: "替补",
      can_cancel: false, can_edit: false, battletag: privateGame }
    data.game_accounts = [{ id: 121, battletag: privateGame, rank_tank: 0, rank_damage: null, rank_support: null }]
    const result = await page("/scrims/8/", session().user, {
      "/api/scrims/8": { data }, "/api/me/profile": { data: profile() },
    })
    expect(result.status).toBe(200)
    const visible = main(result.body)
    expect(visible).toContain("替补")
    expect(visible).toContain("报名已截止，不能再修改")
    expect(visible).not.toContain("取消报名")
    expect(visible).not.toContain("保存修改")
  })

  test("unknown scrim remains 404 even when member profile loads concurrently", async () => {
    const result = await page("/scrims/999/", session().user, {
      "/api/scrims/999": { data: missing, status: 404 }, "/api/me/profile": { data: profile() },
    })
    expect(result.status).toBe(404)
  })
})


describe("完整身份矩阵的报名权限与缺项投影", () => {
  test("非队长包括超管直接打开整队报名会回到赛事详情", async () => {
    const form = registerForm()
    form.teams = []; form.team = null; form.rows = []; form.can_submit = false
    form.problems = ["需要由队长为战队报名。"]
    for (const superuser of [false, true]) {
      const user = session().user!; user.superuser = superuser
      const result = await page("/tournaments/7/register/", user, {"/api/tournaments/7/register": {data: form}})
      expect(result.status).toBe(302)
      expect(result.headers.location).toBe("/tournaments/7/")
    }
  })

  test("无游戏 ID 的申请提示单独显示补全段落，只链接申请所缺的游戏 ID", async () => {
    const data = teamPage(); data.viewer.apply_reason = "请先在个人中心添加至少一个游戏 ID。"; data.viewer.needs_game_account = true
    const user = session().user!; user.profile_gaps = [{label:"游戏 ID",href:"/me/game-accounts/",hint:""},{label:"联系方式",href:"/me/contacts/",hint:""}]
    for (const url of ["/teams/5/", "/teams/5/apply/"]) {
      const result = await page(url,user,{"/api/teams/5":{data}})
      expect(result.status).toBe(200)
      const content = main(result.body)
      expect(content).toContain('<p class="mt-2">去补全：')
      expect(content).toContain('href="/me/game-accounts/" class="c-link">游戏 ID</a>')
      expect(content).not.toContain('href="/me/contacts/" class="c-link"')
    }
  })

  test("个人报名缺项只显示真实缺项，干部兼容联系方式字段不会出现在公开详情", async () => {
    const data = tournamentPage(); data.viewer.is_manager = true; data.tournament!.participant_contact = participantContact
    data.viewer.individual_problems = ["你的资料不完整（缺少游戏 ID、联系方式）"]
    const user = session().user!; user.admin = true; user.caps = ["tournaments.manage"]
    user.profile_gaps = [{label:"游戏 ID",href:"/me/game-accounts/",hint:""},{label:"联系方式",href:"/me/contacts/",hint:""}]
    const detail = await page("/tournaments/7/",user,{"/api/tournaments/7":{data}})
    expect(text(main(detail.body))).toContain("去补全：游戏 ID、联系方式")
    expect(main(detail.body)).not.toContain(participantContact)
    const form = individualForm(); form.problems = data.viewer.individual_problems; form.game_accounts = []; form.can_submit = false
    const signup = await page("/tournaments/7/signup/",user,{"/api/tournaments/7/signup":{data:form}})
    expect(text(main(signup.body))).toContain("去补全：游戏 ID、联系方式")
  })

  test("非队长已报名队员看到冻结队名与自己的报名详情链接", async () => {
    const data = tournamentPage(); data.tournament!.registration_mode = "team"; data.pool = null
    data.viewer.on_roster = {id:90,status:"approved",team_name:"截图战队"}
    const result = await page("/tournaments/7/",session().user,{"/api/tournaments/7":{data}})
    expect(text(main(result.body))).toContain("你在「截图战队」的名单里")
    expect(main(result.body)).toContain('href="/registrations/90/"')
    expect(main(result.body)).not.toContain('href="/tournaments/7/register/"')
  })
})


test("内战修改报名保留已有游戏 ID，新报名选本人第一项且不显示空选项", async () => {
  const data = scrimForMember()
  data.game_accounts.push({id:122,battletag:"SecondOwn#1234",rank_tank:null,rank_damage:10,rank_support:null})
  data.mine = {id:91,game_account_id:122,battletag:"SecondOwn#1234",roles:["damage"],placement:"",can_cancel:true,can_edit:true}
  const existing = await page("/scrims/8/",session().user,{"/api/scrims/8":{data}})
  expect(selectedOption(select(main(existing.body),"scrim-8-account"),122)).toMatch(/\bselected(?:\s|=|>)/)
  expect(select(main(existing.body),"scrim-8-account")).not.toContain("请选择")
  data.mine = null
  const fresh = await page("/scrims/8/",session().user,{"/api/scrims/8":{data}})
  expect(selectedOption(select(main(fresh.body),"scrim-8-account"),121)).toMatch(/\bselected(?:\s|=|>)/)
})
