import type {
  CallExtras,
  GetApiMeProfileOut,
  Requester,
} from "@sjtu-ow/api"
import { ApiError, getApiMeProfile } from "@sjtu-ow/api"
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
  const response = await api<unknown>("PATCH", "/api/me/profile", { ...extras, body })
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
  const response = await api<unknown>("PATCH", "/api/me/game-accounts/{id}", { ...extras, params: { id }, body })
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
  const response = await api<unknown>("PATCH", "/api/me/contacts/{id}", { ...extras, params: { id }, body })
  const shape: ContactValues = { type: "", value: "" }
  return readSaveReceipt(response, shape, primitiveValues(shape))
}

// [BE-11] Exact deletion blockers are a read projection, not a failed DELETE.
export type DeletionState = {
  blockers: string[]
}

export function getDeletionState(api: Requester): Promise<DeletionState> {
  return api("GET", "/api/auth/delete-account/state")
}

// [BE-12] Individual registration/calendar and full private team projections.
export type PersonalTeamContext = {
  member_contact?: string
}

// [BE-13] Letter preview is a standalone, server-rendered document. The
// frontend must not invent its body from the list's recipient/subject fields.
export type LetterPreviewAvailability = {
  preview_url?: string
}

// [BE-14] Private scrim history, including cancelled/finished and placement.
export type PersonalScrimSignup = {
  id: number
  scrim_id: number
  title: string
  starts_at: string
  role_tank: boolean
  role_damage: boolean
  role_support: boolean
  placement: string
  status: string
}

export type PersonalScrims = {
  signups: PersonalScrimSignup[]
}

export function getPersonalScrims(api: Requester): Promise<PersonalScrims> {
  return api("GET", "/api/me/scrims")
}
