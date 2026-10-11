/** Activity wrappers retain the existing call sites and use generated contracts. */
import {
  getApiAdminAnnounceKindId,
  postApiAdminAnnounceKindIdConfirm,
  postApiAdminTournamentsIdBoard,
  getApiAdminTournamentsIdCopyPreview,
  getApiAdminScrimsIdCopyPreview,
  getApiAdminTournamentsIdPublishPreview,
  getApiAdminScrimsIdPublishPreview,
  postApiAdminTournamentsIdPublishConfirm,
  postApiAdminScrimsIdPublishConfirm,
  getApiAdminTournamentsEditorDefaults,
  getApiAdminScrimsEditorDefaults,
  type CallExtras,
  type Requester,
  type GetApiAdminAnnounceKindIdOut,
  type PostApiAdminTournamentsIdBoardIn,
  type GetApiAdminTournamentsEditorDefaultsOut,
  type GetApiAdminScrimsEditorDefaultsOut,
} from "@sjtu-ow/api"

export interface ActivityNoticePreview {
  audience: "all" | "participants"
  subject: string
  body_text: string
  body_html?: string
  preview_url?: string
  note_max?: number
  recipients: number
  problem: string
  will_wait: boolean
  preview_version: string
}

/** GET announce must return this shape for the exact to audience requested. */
export function noticePreview(value: unknown): ActivityNoticePreview | null {
  if (value === null || typeof value !== "object") return null
  const item = value as Record<string, unknown>
  if (item.audience !== "all" && item.audience !== "participants") return null
  if (typeof item.subject !== "string" || typeof item.body_text !== "string") return null
  if (typeof item.problem !== "string" || typeof item.will_wait !== "boolean") return null
  if (typeof item.recipients !== "number" || !Number.isSafeInteger(item.recipients) || item.recipients < 0) return null
  if (item.note_max !== undefined && (typeof item.note_max !== "number" || !Number.isSafeInteger(item.note_max) || item.note_max < 0)) return null
  if (typeof item.preview_version !== "string" || !item.preview_version) return null
  return {
    audience: item.audience,
    subject: item.subject,
    body_text: item.body_text,
    ...(typeof item.body_html === "string" ? { body_html: item.body_html } : {}),
    ...(typeof item.preview_url === "string" && item.preview_url.startsWith("/api/admin/announce/") ? { preview_url: item.preview_url } : {}),
    ...(typeof item.note_max === "number" && Number.isSafeInteger(item.note_max) ? { note_max: item.note_max } : {}),
    recipients: item.recipients,
    problem: item.problem,
    will_wait: item.will_wait,
    preview_version: item.preview_version,
  }
}

export type NoticeResponse = GetApiAdminAnnounceKindIdOut
export type SafeTeamBoardRequest = PostApiAdminTournamentsIdBoardIn
export type TournamentDefaults = GetApiAdminTournamentsEditorDefaultsOut
export type ScrimDefaults = GetApiAdminScrimsEditorDefaultsOut

export function getActivityNotice(
  api: Requester,
  kind: string,
  id: number,
  audience: "all" | "participants",
  extras: CallExtras = {},
  note = "",
): Promise<NoticeResponse> {
  return getApiAdminAnnounceKindId(api, kind, id, { to: audience, note }, extras)
}

export function sendActivityNotice(
  api: Requester,
  kind: string,
  id: number,
  body: { audience: "all" | "participants"; preview_version: string; note: string },
  extras: CallExtras = {},
) {
  return postApiAdminAnnounceKindIdConfirm(api, kind, id, body, { to: body.audience }, extras)
}

export function saveTeamBoard(api: Requester, id: number, body: SafeTeamBoardRequest, extras: CallExtras = {}) {
  return postApiAdminTournamentsIdBoard(api, id, body, extras)
}

/** Copy previews retain the source ID and perform no database write. */
export function getTournamentCopyPreview(api: Requester, id: number, extras: CallExtras = {}) {
  return getApiAdminTournamentsIdCopyPreview(api, id, extras)
}

export function getScrimCopyPreview(api: Requester, id: number, extras: CallExtras = {}) {
  return getApiAdminScrimsIdCopyPreview(api, id, extras)
}

export function getPublishNoticePreview(api: Requester, kind: "tournaments" | "scrims", id: number, extras: CallExtras = {}): Promise<NoticeResponse> {
  return kind === "tournaments"
    ? getApiAdminTournamentsIdPublishPreview(api, id, extras)
    : getApiAdminScrimsIdPublishPreview(api, id, extras)
}

export function publishWithNotice(
  api: Requester,
  kind: "tournaments" | "scrims",
  id: number,
  body: { announce: boolean; preview_version: string },
  extras: CallExtras = {},
) {
  return kind === "tournaments"
    ? postApiAdminTournamentsIdPublishConfirm(api, id, body, extras)
    : postApiAdminScrimsIdPublishConfirm(api, id, body, extras)
}

export function getTournamentDefaults(api: Requester, extras: CallExtras = {}): Promise<TournamentDefaults> {
  return getApiAdminTournamentsEditorDefaults(api, extras)
}

export function getScrimDefaults(api: Requester, extras: CallExtras = {}): Promise<ScrimDefaults> {
  return getApiAdminScrimsEditorDefaults(api, extras)
}
