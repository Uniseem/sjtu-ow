import type {
  CallExtras,
  GetApiMeProfileOut,
  GetApiMeScrimsOut,
  Requester,
} from "@sjtu-ow/api"
import { ApiError, getApiMeProfile,getApiMeScrims,patchApiMeProfile,patchApiMeGameAccountsId,patchApiMeContactsId } from "@sjtu-ow/api"
import type { SaveReceipt, SaveRequest } from "@sjtu-ow/shared/autosave"
import { primitiveValues, readSaveReceipt } from "@sjtu-ow/shared/save-receipt"

// [BE-9] F5 versioned profile, game ID and contact editing contracts.
// Remove these adapters when apigen provides the complete additive contract.
// The old profile PATCH ignores unknown JSON fields; never send a changes
// envelope without a real version from GET. No synthetic receipt is allowed.
export type ProfileValues = {
  nickname: string
  is_sjtu: boolean
  motto: string
  main_role: string
  flex_roles: string
  show_rank: boolean
}

export type GameValues = {
  rank_tank: number | null
  rank_damage: number | null
  rank_support: number | null
}

export type ContactValues = {
  type: string
  value: string
}

export type GameEditValues = GameValues & { battletag: string }

export type GameAccount = GetApiMeProfileOut["game_accounts"][number] & {
  version?: number
}

export type Contact = GetApiMeProfileOut["contacts"][number] & {
  version?: number
}

// [BE-10] Personal-center context and avatar permission/moderation projection.
export type PersonalProfile = Omit<GetApiMeProfileOut, "game_accounts" | "contacts"> & {
  version?: number
  avatar_image_id?: number | null
  default_avatar_image_id?: number | null
  avatar_can_upload?: boolean
  avatar_denied?: string
  avatar_turned_down?: {
    status: string
    reason_display: string
    note: string
  } | null
  max_game_accounts?: number
  profile_gaps?: { label: string; href: string; hint: string }[]
  waiting_letters?: number
  accepts_announcements?: boolean
  deletion_blockers?: string[]
  game_accounts: GameAccount[]
  contacts: Contact[]
}

export async function getPersonalProfile(api: Requester): Promise<PersonalProfile> {
  const result: PersonalProfile = await getApiMeProfile(api)
  return result
}

export function validVersion(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0
}

function requireVersion(version: unknown): asserts version is number {
  if (!validVersion(version)) {
    throw new ApiError(503, "save_unavailable", "暂时无法保存，请稍后再试。")
  }
}

export async function patchPersonalProfile(
  api: Requester,
  body: SaveRequest<ProfileValues>,
  extras: CallExtras,
): Promise<SaveReceipt<ProfileValues>> {
  requireVersion(body.base_version)
  const response = await patchApiMeProfile(api,body,extras)
  const shape: ProfileValues = { nickname: "", is_sjtu: false, motto: "", main_role: "", flex_roles: "", show_rank: false }
  return readSaveReceipt(response, shape, primitiveValues(shape))
}

export async function patchPersonalGameAccount(
  api: Requester,
  id: number,
  body: SaveRequest<GameEditValues>,
  extras: CallExtras,
): Promise<SaveReceipt<GameEditValues>> {
  requireVersion(body.base_version)
  const response = await patchApiMeGameAccountsId(api,id,body,extras)
  const shape: GameEditValues = { battletag: "", rank_tank: null, rank_damage: null, rank_support: null }
  return readSaveReceipt(response, shape, primitiveValues(shape))
}

export async function patchPersonalContact(
  api: Requester,
  id: number,
  body: SaveRequest<ContactValues>,
  extras: CallExtras,
): Promise<SaveReceipt<ContactValues>> {
  requireVersion(body.base_version)
  const response = await patchApiMeContactsId(api,id,body,extras)
  const shape: ContactValues = { type: "", value: "" }
  return readSaveReceipt(response, shape, primitiveValues(shape))
}

// Historical adapter filename. All consumed contracts now come from apigen.
export type PersonalScrimSignup=GetApiMeScrimsOut["signups"][number]
export type PersonalScrims=GetApiMeScrimsOut
export const getPersonalScrims=getApiMeScrims
