import type {
  GetApiTeamsOut,
  GetApiTeamsIdOut,
  GetApiTeamsIdManageOut,
} from "@sjtu-ow/api"
import type { PublicPlay, AvatarPerson } from "@sjtu-ow/ui/types"
import { shanghaiParts } from "@sjtu-ow/shared/time"
import { hue } from "@sjtu-ow/shared/initial"
import { httpError } from "./router"

export type Team = NonNullable<GetApiTeamsIdOut["team"]>
export type TeamMember = GetApiTeamsIdOut["members"][number] & {
  avatar_image_id?: number | null
  default_avatar_image_id?: number | null
  motto?: string
  member_url?: string | null
}
export type TeamAlumnus = GetApiTeamsIdOut["alumni"][number] & {
  avatar_image_id?: number | null
  default_avatar_image_id?: number | null
  member_url?: string | null
}
export type TeamEntry = {
  id: number
  tournament_id: number
  title: string
  status: string
}
// [BE-17] Exact public/private viewer projection for F6. These optional
// details do not license reconstructing private fields from another endpoint.
export type TeamDetail = Omit<GetApiTeamsIdOut, "members" | "alumni"> & {
  members: TeamMember[]
  alumni: TeamAlumnus[]
  entries?: TeamEntry[]
  needs_contact?: boolean
}
export type TeamManage = Omit<GetApiTeamsIdManageOut,"team"> & {team:Team}
export type TeamList = GetApiTeamsOut
export const TEAM_ROLES = [
  { code: "tank", label: "坦克" },
  { code: "damage", label: "输出" },
  { code: "support", label: "支援" },
] as const

export function requireTeam(value: Team | null): Team {
  if (!value) throw httpError(404)
  return value
}

export function teamRoleLabel(value: string): string {
  return TEAM_ROLES.find((role) => role.code === value)?.label ?? ""
}

export function teamRoleLabels(values: readonly string[]): string {
  return TEAM_ROLES.filter((role) => values.includes(role.code)).map((role) => role.label).join("、")
}

export function teamScene(id: number): string {
  return `/static/img/placeholders/hue-${hue(id)}.svg`
}

export function joinedMonth(value: string): string {
  const parts = shanghaiParts(new Date(value))
  return `${parts.year}.${parts.month}`
}

export function memberPerson(value: Pick<TeamMember, "user_id" | "nickname" | "is_active" | "avatar_image_id" | "default_avatar_image_id">): AvatarPerson {
  return {
    id: value.user_id,
    nickname: value.nickname,
    is_active: value.is_active,
    avatar_image_id: value.avatar_image_id,
    default_avatar_image_id: value.default_avatar_image_id,
  }
}

/** Only public ranks already projected by the service may be displayed. */
export function memberPlay(value: Pick<TeamMember, "main_role" | "roles" | "ranks">): PublicPlay {
  const ordered = TEAM_ROLES.filter((role) => value.roles.includes(role.code))
  ordered.sort((a, b) => Number(b.code === value.main_role) - Number(a.code === value.main_role))
  const candidates = ordered.length ? ordered : [...TEAM_ROLES].sort((a, b) => {
    return (value.ranks[b.code].score ?? -1) - (value.ranks[a.code].score ?? -1)
  })
  const primary = candidates.find((role) => value.ranks[role.code].score !== null)
  return {
    roles: ordered.map((role) => ({ code: role.code, label: role.label, main: role.code === value.main_role })),
    is_flex: ordered.length === TEAM_ROLES.length,
    main_rank: primary ? {
      label: value.ranks[primary.code].label,
      role_label: primary.label,
      stale: value.ranks[primary.code].is_expired,
    } : null,
  }
}

export function teamMemberHref(member: TeamMember | TeamAlumnus): string | null {
  if (member.member_url === null) return null
  return member.member_url || `/members/${member.user_id}/`
}

export function validTeamRole(value: string): string {
  return TEAM_ROLES.some((role) => role.code === value) ? value : ""
}
