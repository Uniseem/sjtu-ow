import type { Requester,CallExtras,PostApiTeamsIdLogoOut } from "@sjtu-ow/api"
import type { SaveCurrent } from "@sjtu-ow/shared/autosave"
import type { Team } from "./team-domain"
export type TeamValues = {
  name: string
  description: string
  is_recruiting: boolean
  recruiting_roles: string[]
  member_contact: string
  logo_image_id: number | null
  remove_logo: boolean
}
export type TeamCreateState = { max_captained: number; blocker: string; can_create: boolean }
// Temporary consumer declaration; replaced by the generated endpoint after
// the whole batch reaches its code target and apigen runs on the test host.
export function getTeamCreateState(api: Requester): Promise<TeamCreateState> {
  return api<TeamCreateState>("GET", "/api/teams/create-state")
}
export function teamValues(team: Team): TeamValues {
  return { name: team.name, description: team.description, is_recruiting: team.is_recruiting,
    recruiting_roles: [...team.recruiting_roles], member_contact: team.member_contact || "",
    logo_image_id: team.logo_image_id, remove_logo: false }
}
export function readTeamCurrent(value: unknown): SaveCurrent<TeamValues> | null {
  if (!value || typeof value !== "object" || !("version" in value) || !("values" in value)) return null
  const v = value.values
  if (!Number.isSafeInteger(value.version) || !v || typeof v !== "object") return null
  if (!("name" in v) || typeof v.name !== "string" || !("description" in v) || typeof v.description !== "string") return null
  if (!("is_recruiting" in v) || typeof v.is_recruiting !== "boolean" || !("recruiting_roles" in v) || !Array.isArray(v.recruiting_roles) || !v.recruiting_roles.every(role => typeof role === "string")) return null
  if (!("member_contact" in v) || typeof v.member_contact !== "string" || !("logo_image_id" in v) || (v.logo_image_id !== null && !Number.isSafeInteger(v.logo_image_id))) return null
  return { version: Number(value.version), values: { name: v.name, description: v.description,
    is_recruiting: v.is_recruiting, recruiting_roles: [...v.recruiting_roles], member_contact: v.member_contact,
    logo_image_id: v.logo_image_id as number | null, remove_logo: false } }
}

export function prepareTeamLogo(api:Requester,body:{file_name:string;data_url:string},extras:CallExtras){return api<PostApiTeamsIdLogoOut>("POST","/api/teams/logo",{...extras,body})}
