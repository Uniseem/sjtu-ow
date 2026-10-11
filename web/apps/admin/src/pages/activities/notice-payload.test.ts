import { describe, expect, test } from "vitest"
import type { CallOptions, Requester } from "@sjtu-ow/api"
import {
  getActivityNotice, getPublishNoticePreview, getScrimCopyPreview,
  getTournamentCopyPreview, noticePreview, publishWithNotice,
  saveTeamBoard, sendActivityNotice,
} from "./pending"
import { keepSeconds, localMinute, timestamp } from "./domain"
import { currentScrim, currentTournament } from "./form-schema"

function recordingRequester() {
  const calls: { method: string; path: string; options: CallOptions | undefined }[] = []
  const api: Requester = async <T>(method: string, path: string, options?: CallOptions) => {
    calls.push({ method, path, options })
    return {} as T
  }
  return { api, calls }
}

const preview = {
  audience: "participants",
  subject: "赛事通知",
  body_text: "服务端的原始正文",
  body_html: "<html>邮件正文</html>",
  preview_url: "/api/admin/announce/tournament/7/preview?version=123.digest",
  note_max: 500,
  recipients: 4,
  problem: "",
  will_wait: false,
  preview_version: "123.digest",
}

describe("预览与显式发送之间的冻结契约", () => {
  test("完整服务端预览保留原文与签名，不制造正文或版本", () => {
    expect(noticePreview(preview)).toEqual(preview)
    expect(noticePreview({ recipients: 4, subject: "仅列表标题" })).toBeNull()
    expect(noticePreview({ ...preview, preview_version: "" })).toBeNull()
    expect(noticePreview({ ...preview, audience: "other" })).toBeNull()
    expect(noticePreview({ ...preview, recipients: 1.5 })).toBeNull()
    expect(noticePreview({ ...preview, preview_url: "https://foreign.invalid/preview" })?.preview_url).toBeUndefined()
  })

  test("无效负收件人数或限制不能开启确认流程", () => {
    expect(noticePreview({ ...preview, recipients: -1 })).toBeNull()
    expect(noticePreview({ ...preview, note_max: -1 })).toBeNull()
  })

  test("发送携带预览时确认的收件范围、备注和原签名及同一幂等键", async () => {
    const { api, calls } = recordingRequester()
    const body = { audience: "participants" as const, note: "管理员说明", preview_version: "signed-frozen-version" }
    await sendActivityNotice(api, "tournament", 7, body, { key: "stable-key", unauthorized: "throw" })
    expect(calls).toEqual([{
      method: "POST",
      path: "/api/admin/announce/{kind}/{id}/confirm",
      options: {
        key: "stable-key",
        unauthorized: "throw",
        params: { kind: "tournament", id: 7 },
        query: { to: "participants" },
        body,
      },
    }])
    expect(calls[0]?.path.endsWith("/confirm")).toBe(true)
  })

  test("说明改动在GET预览重算，不提前发信或建草稿", async () => {
    const { api, calls } = recordingRequester()
    await getActivityNotice(api, "scrim", 8, "participants", { unauthorized: "throw" }, "新说明")
    await getTournamentCopyPreview(api, 7)
    await getScrimCopyPreview(api, 8)
    expect(calls.map((call) => call.method)).toEqual(["GET", "GET", "GET"])
    expect(calls[0]?.options?.query).toEqual({ to: "participants", note: "新说明" })
    expect(calls.map((call) => call.path)).toEqual([
      "/api/admin/announce/{kind}/{id}",
      "/api/admin/tournaments/{id}/copy-preview",
      "/api/admin/scrims/{id}/copy-preview",
    ])
  })

  test("发布通知预览和原子提交使用独立接口，不依次发布再另发通知", async () => {
    const { api, calls } = recordingRequester()
    await getPublishNoticePreview(api, "scrims", 8)
    await publishWithNotice(api, "scrims", 8, { announce: true, preview_version: "signed" }, { key: "publish-key" })
    expect(calls.map((call) => [call.method, call.path])).toEqual([
      ["GET", "/api/admin/scrims/{id}/publish-preview"],
      ["POST", "/api/admin/scrims/{id}/publish-confirm"],
    ])
    expect(calls[1]?.options).toEqual({ key: "publish-key", params: { id: 8 }, body: { announce: true, preview_version: "signed" } })
  })

  test("编排名册载荷包含池版本与各队名单版本，不夹带用户资料字段", async () => {
    const { api, calls } = recordingRequester()
    const body = { base_pool_version: 12, teams: [{ registration_id: 40, name: "第一队", signup_ids: [1, 2], base_version: 3 }] }
    await saveTeamBoard(api, 7, body, { key: "board-key" })
    expect(calls[0]?.options).toEqual({ key: "board-key", params: { id: 7 }, body })
    expect(Object.keys(calls[0]?.options?.body as object).sort()).toEqual(["base_pool_version", "teams"])
  })
})

describe("按字段保存的时间和冲突恢复", () => {
  test("北京时间表单不跟随操作者电脑时区，失焦不截掉原秒", () => {
    const committed = "2026-10-11T09:03:27Z"
    expect(timestamp(committed)).toBe("2026.10.11 17:03")
    expect(localMinute(committed)).toBe("2026-10-11T17:03")
    expect(keepSeconds("2026-10-11T17:03", committed)).toBe(committed)
    expect(keepSeconds("2026-10-11T17:04", committed)).toBe("2026-10-11T09:04:00.000Z")
    expect(keepSeconds("", committed)).toBeNull()
  })

  test("当前保存值恢复隐私开关原值，不填默认true或改报名方式", () => {
    const values = {
      title: "当前赛事", summary: "", description: "", registration_mode: "team",
      cover_image_id: null, starts_at: null, registration_opens_at: null, registration_closes_at: null,
      roster_min: 5, roster_max: 6, sjtu_only: false, auto_approve: false, participant_contact: "选手 QQ 群",
    }
    expect(currentTournament({ version: 9, values })?.values).toEqual(values)
    expect(currentTournament({ version: 9, values: { ...values, auto_approve: undefined } })).toBeNull()
    expect(currentTournament({ version: -1, values })).toBeNull()
    expect(currentTournament({ version: 9, values: { ...values, roster_min: 1.5 } })).toBeNull()
  })

  test("冲突当前内战要有真实规格、时间、版本与开关，空对象不能清稿", () => {
    const values = { title: "当前内战", description: "说明", starts_at: null, signup_closes_at: null, format: "rq_5v5", sjtu_only: false }
    expect(currentScrim({ version: 8, values })).toEqual({ version: 8, values })
    expect(currentScrim({ version: 8 })).toBeNull()
    expect(currentScrim({ version: 8, values: { ...values, sjtu_only: "false" } })).toBeNull()
  })
})
