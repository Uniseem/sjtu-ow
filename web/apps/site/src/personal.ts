import type { LoadCtx } from "./router"
import { httpError } from "./router"
import { useViewer } from "./viewer"
import type { AvatarPerson } from "@sjtu-ow/ui/types"
import type {
  ContactValues,
  GameAccount,
  GameEditValues,
  GameValues,
  PersonalProfile,
  ProfileValues,
} from "./pending-api"
import { getPersonalProfile } from "./pending-api"
import type { SaveCurrent } from "@sjtu-ow/shared/autosave"
import { validatePersonalProfile } from "./personal-schema"

export const PERSONAL_NAV = [
  { href: "/me/", label: "基本资料", available: true, icon: "user" },
  { href: "/me/game-accounts/", label: "游戏 ID 与段位", available: true, icon: "id" },
  { href: "/me/contacts/", label: "联系方式", available: true, icon: "phone" },
  { href: "/me/teams/", label: "我的战队", available: true, icon: "shield" },
  { href: "/me/registrations/", label: "我的报名", available: true, icon: "trophy" },
  { href: "/me/scrims/", label: "我的内战", available: true, icon: "calendar" },
  { href: "/me/security/", label: "账号安全", available: true, icon: "lock" },
]

export const PLAY_ROLES = [
  { value: "tank", label: "坦克", icon: "role-tank" },
  { value: "damage", label: "输出", icon: "role-damage" },
  { value: "support", label: "支援", icon: "role-support" },
] as const

export const CONTACT_TYPES = [
  { value: "qq", label: "QQ" },
  { value: "wechat", label: "微信" },
  { value: "phone", label: "手机号" },
  { value: "other", label: "其他" },
] as const

export type PersonalPageData = {
  title: string
  profile: PersonalProfile
  renderedAt?: number
  newItem?: boolean
  editId?: number
}

export async function loadPersonal(ctx: LoadCtx, title: string): Promise<PersonalPageData> {
  const profile = validatePersonalProfile(await getPersonalProfile(ctx.api))
  return { title, profile, renderedAt: Date.now() }
}

export function personalId(value: string | undefined): number {
  if (!value || !/^\d{1,18}$/.test(value)) throw httpError(404)
  const id = Number(value)
  if (!Number.isSafeInteger(id) || id <= 0) throw httpError(404)
  return id
}

export function usePersonalUser(profile: PersonalProfile): AvatarPerson {
  const viewer = useViewer()
  return {
    id: profile.id,
    nickname: profile.nickname,
    is_active: true,
    avatar_image_id: profile.avatar_image_id,
    default_avatar_image_id: profile.default_avatar_image_id,
    // Session nickname is deliberately not used to reset a local form.
    avatar_url: avatarURL(viewer.user),
  }
}

function avatarURL(value: unknown): string | undefined {
  if (!value || typeof value !== "object" || !("avatar_url" in value)) return undefined
  return typeof value.avatar_url === "string" ? value.avatar_url : undefined
}

export function profileValues(profile: PersonalProfile): ProfileValues {
  return {
    nickname: profile.nickname,
    is_sjtu: profile.is_sjtu,
    motto: profile.motto,
    main_role: profile.main_role,
    flex_roles: profile.flex_roles,
    show_rank: profile.show_rank,
  }
}

export function gameValues(account: GameAccount): GameValues {
  return {
    rank_tank: account.rank_tank,
    rank_damage: account.rank_damage,
    rank_support: account.rank_support,
  }
}

export function parseRoles(value: string): string[] {
  const selected = new Set(value.split(",").map((part) => part.trim()))
  return PLAY_ROLES.filter((role) => selected.has(role.value)).map((role) => role.value)
}

export function joinRoles(value: readonly string[]): string {
  return PLAY_ROLES.filter((role) => value.includes(role.value)).map((role) => role.value).join(",")
}

export function rankChoices(): { value: string; label: string }[] {
  const choices = [
    { value: "", label: "未定级" },
    { value: "40", label: "前 500" },
  ]
  const labels = ["青铜", "白银", "黄金", "白金", "钻石", "大师", "宗师", "英杰"]
  labels.forEach((tier, index) => {
    for (let division = 5; division >= 1; division -= 1) {
      choices.push({ value: String(index * 5 + 5 - division), label: `${tier} ${division}` })
    }
  })
  return choices
}

export function rankValue(value: number | null): string {
  return value === null ? "" : String(value)
}

export function parseRank(value: string): number | null {
  if (value === "") return null
  const number = Number(value)
  if (!Number.isInteger(number) || number < 0 || number > 40) throw new Error("非法段位")
  return number
}

export function readRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function currentValues(value: unknown): { version: number; values: Record<string, unknown> } | null {
  const current = readRecord(value)
  if (!current || typeof current.version !== "number" || !Number.isSafeInteger(current.version) || current.version < 0) return null
  const values = readRecord(current.values) ?? current
  return { version: current.version, values }
}

export function readProfileCurrent(value: unknown): SaveCurrent<ProfileValues> | null {
  const current = currentValues(value)
  if (!current) return null
  const values = current.values
  if (typeof values.nickname !== "string" || typeof values.is_sjtu !== "boolean"
    || typeof values.motto !== "string" || typeof values.main_role !== "string"
    || typeof values.flex_roles !== "string" || typeof values.show_rank !== "boolean") return null
  return {
    version: current.version,
    values: {
      nickname: values.nickname,
      is_sjtu: values.is_sjtu,
      motto: values.motto,
      main_role: values.main_role,
      flex_roles: values.flex_roles,
      show_rank: values.show_rank,
    },
  }
}

export function readGameCurrent(value: unknown): SaveCurrent<GameValues> | null {
  const current = currentValues(value)
  if (!current) return null
  const values = current.values
  const validRank = (rank: unknown): rank is number | null => rank === null
    || typeof rank === "number" && Number.isInteger(rank) && rank >= 0 && rank <= 40
  if (!validRank(values.rank_tank) || !validRank(values.rank_damage) || !validRank(values.rank_support)) return null
  return {
    version: current.version,
    values: {
      rank_tank: values.rank_tank,
      rank_damage: values.rank_damage,
      rank_support: values.rank_support,
    },
  }
}

export function readContactCurrent(value: unknown): SaveCurrent<ContactValues> | null {
  const current = currentValues(value)
  if (!current || typeof current.values.type !== "string" || typeof current.values.value !== "string") return null
  return {
    version: current.version,
    values: { type: current.values.type, value: current.values.value },
  }
}

export function requirePageData<T>(data: T | undefined): T {
  if (!data) throw new Error("Missing personal page data")
  return data
}

export function readGameEditCurrent(value: unknown): SaveCurrent<GameEditValues> | null {
  const ranks = readGameCurrent(value)
  const current = currentValues(value)
  if (!ranks || !current || typeof current.values.battletag !== "string") return null
  return { version: ranks.version, values: { ...ranks.values, battletag: current.values.battletag } }
}
