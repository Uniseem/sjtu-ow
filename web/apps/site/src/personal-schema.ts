import { ApiError } from "@sjtu-ow/api"
import type { PersonalProfile } from "./pending-api"
import { readRecord } from "./personal"

/** Strict checks on the editable/private data prevent default-value writes. */
export function validatePersonalProfile(value: PersonalProfile): PersonalProfile {
  const profile = readRecord(value)
  function invalid(): never { throw new ApiError(502, "invalid_profile", "资料暂时无法加载，请稍后再试。") }
  if (!profile || !positiveId(profile.id)) invalid()
  for (const name of ["nickname", "email", "motto", "main_role", "flex_roles"]) {
    if (typeof profile[name] !== "string") invalid()
  }
  if (typeof profile.is_sjtu !== "boolean" || typeof profile.show_rank !== "boolean" || typeof profile.is_complete !== "boolean") invalid()
  if (!Array.isArray(profile.game_accounts) || !Array.isArray(profile.contacts)) invalid()
  const ids = new Set<number>()
  for (const raw of profile.game_accounts) {
    const account = readRecord(raw)
    if (!account || !positiveId(account.id) || typeof account.battletag !== "string") invalid()
    if (ids.has(account.id)) invalid()
    ids.add(account.id)
    if (!rank(account.rank_tank) || !rank(account.rank_damage) || !rank(account.rank_support)) invalid()
    if (typeof account.tank_label !== "string" || typeof account.damage_label !== "string" || typeof account.support_label !== "string") invalid()
    if (!date(account.ranks_updated_at)) invalid()
    if (account.version !== undefined && !version(account.version)) invalid()
  }
  ids.clear()
  for (const raw of profile.contacts) {
    const contact = readRecord(raw)
    if (!contact || !positiveId(contact.id) || typeof contact.type !== "string" || typeof contact.value !== "string" || typeof contact.type_label !== "string") invalid()
    if (ids.has(contact.id)) invalid()
    ids.add(contact.id)
    if (contact.version !== undefined && !version(contact.version)) invalid()
  }
  if (profile.version !== undefined && !version(profile.version)) invalid()
  if (profile.max_game_accounts !== undefined && (!version(profile.max_game_accounts) || profile.max_game_accounts < 1)) invalid()
  return value
}

function positiveId(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0
}

function version(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0
}

function rank(value: unknown): value is number | null {
  return value === null || typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 40
}

function date(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value))
}
