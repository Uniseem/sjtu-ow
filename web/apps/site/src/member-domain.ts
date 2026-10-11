import type { GetApiMembersOut, GetApiMembersIdOut } from "@sjtu-ow/api"
import type { AvatarPerson } from "@sjtu-ow/ui/types"
import { memberPlay, TEAM_ROLES } from "./team-domain"

export type MemberCard = GetApiMembersOut["members"][number] & {
  avatar_image_id?: number | null
  default_avatar_image_id?: number | null
}
export type MemberList = Omit<GetApiMembersOut, "members" | "sections"> & {
  members: MemberCard[]
  sections: Array<Omit<GetApiMembersOut["sections"][number], "entries"> & {
    entries: Array<{ member: MemberCard; titles: string[] }>
  }>
}
export type MemberPage = Omit<GetApiMembersIdOut, "card" | "teams" | "alumni"> & {
  card: MemberCard
  teams: Array<GetApiMembersIdOut["teams"][number] & {
    logo_image_id?: number | null
    is_recruiting?: boolean
  }>
  alumni: Array<GetApiMembersIdOut["alumni"][number] & { joined_at?: string }>
}
export { memberPlay, TEAM_ROLES }
export function memberAvatar(member: MemberCard): AvatarPerson {
  return { id: member.user_id, nickname: member.nickname, avatar_image_id: member.avatar_image_id,
    default_avatar_image_id: member.default_avatar_image_id }
}
export function memberTags(member: MemberCard): string[] {
  return member.titles.length ? member.titles : member.groups
}
export function memberFilter(role: string, free: boolean): string {
  const query = new URLSearchParams()
  if (role) query.set("role", role)
  if (free) query.set("free", "1")
  return "/members/" + (query.size ? "?" + query.toString() : "") + "#all-members"
}
