import { expect, test } from "vitest"
import { handle } from "../server"
import type { GetApiMeProfileOut } from "@sjtu-ow/api"

const user = { id: 7, nickname: "成员", email: "member@example.test", admin: false, superuser: false, caps: [], email_verified: true, is_sjtu: true, can_comment: true, can_submit_article: true }
const rank = { score: null, label: "未定级", is_expired: false }
const profile: GetApiMeProfileOut = {
  version:1, avatar_image_id:null,default_avatar_image_id:null,avatar_can_upload:true,avatar_denied:"",avatar_turned_down:null,max_game_accounts:5,profile_gaps:[],waiting_letters:0,deletion_blockers:[],
  id: 7, nickname: "成员", email: user.email, is_sjtu: true,
  motto: "原宣言", main_role: "tank", flex_roles: "support", show_rank: false,
  is_complete: true,
  public_ranks: { tank: rank, damage: rank, support: rank },
  game_accounts: [{ id: 8,version:1,saved:[],saved_at:"2026-10-11T00:00:00Z", battletag: "Player#12345", rank_tank: 0, rank_damage: null, rank_support: 40, tank_label: "青铜 5", damage_label: "未定级", support_label: "前 500", ranks_updated_at: "2026-10-11T00:00:00Z" }],
  contacts: [{ id: 9,version:1,saved:[],saved_at:"2026-10-11T00:00:00Z", type: "qq", type_label: "QQ", value: "12345678", created_at: "2026-10-11T00:00:00Z" }],
}

async function page(url: string, overrides: Record<string, unknown> = {}) {
  const asked: string[] = []
  const response = await handle({ method: "GET", url, headers: { get: () => null } }, {
    apiBase: "http://api.test",
    fetch: async (input, init) => {
      expect(init?.method ?? "GET").toBe("GET")
      const path = new URL(String(input)).pathname
      asked.push(path)
      if (path === "/api/session") return Response.json({ user })
      if (path === "/api/me/profile") return Response.json({ ...profile, ...overrides })
      if (path === "/api/me/announcements") return Response.json({ accepts: false })
      throw new Error("unexpected endpoint " + path)
    },
  })
  return { ...response, asked }
}

test("profile SSR preserves privacy value and disables editing without a real version", async () => {
  const response = await page("/me/",{version:undefined})
  expect(response.status).toBe(200)
  const body = String(response.body)
  expect(body).toContain("基本资料 · SJTU-OW")
  expect(body).toContain("暂时无法保存")
  expect(body).toContain('name="show_rank"')
  expect(body).not.toMatch(/name="show_rank"[^>]*checked/)
  expect(response.asked.filter((path) => path !== "/api/session")).toEqual(["/api/me/profile"])
})

test("new game and contact forms use existing real endpoints without writing during SSR", async () => {
  for (const [path, phrase] of [["/me/game-accounts/?new=1", "名称#12345"], ["/me/contacts/?new=1", "其他"]]) {
    const response = await page(path)
    expect(response.status).toBe(200)
    expect(response.body).toContain(phrase)
    expect(response.body).toContain("添加")
    expect(response.body).not.toContain("已添加游戏 ID")
  }
})

test("ID editing cannot load another owner's object or silently display a blank form", async () => {
  for (const path of ["/me/game-accounts/999/", "/me/contacts/999/"]) {
    expect((await page(path)).status).toBe(404)
  }
  expect((await page("/me/game-accounts/8/")).body).toContain("Player#12345")
  expect((await page("/me/contacts/9/")).body).toContain("12345678")
})

test("null and bronze zero ranks survive the new private list", async () => {
  const response = await page("/me/game-accounts/")
  expect(response.status).toBe(200)
  expect(response.body).toContain("青铜")
  expect(response.body).toContain("未定级")
  expect(response.body).toContain("前 500")
})

test("security needs one page endpoint and displays the real notification state", async () => {
  const response = await page("/me/security/")
  expect(response.status).toBe(200)
  expect(response.body).toContain("活动通知：关着")
  expect(response.body).toContain("打开活动通知")
  expect(response.asked.filter((path) => path !== "/api/session")).toEqual(["/api/me/announcements"])
})

test("absence of deletion preflight is not treated as permission to delete", async () => {
  const response = await page("/me/delete/",{deletion_blockers:undefined})
  expect(response.status).toBe(200)
  expect(response.body).toContain("暂时无法确认账号状态")
  expect(response.body).not.toContain("确认注销</button>")
  const blocked = await page("/me/delete/", { deletion_blockers: ["请先转交队长。"] })
  expect(blocked.body).toContain("请先转交队长。")
  expect(blocked.body).not.toContain("确认注销</button>")
})

test("malformed editable values fail closed rather than becoming false or null writes", async () => {
  const response = await page("/me/", { show_rank: null })
  expect(response.status).toBeGreaterThanOrEqual(500)
})
