import type { SaveCurrent } from "@sjtu-ow/shared/autosave"
import type { Scrim, Tournament } from "./domain"
import { record } from "./domain"

export type TournamentValues = {
  title: string
  summary: string
  description: string
  cover_image_id: number | null
  starts_at: string | null
  registration_opens_at: string | null
  registration_closes_at: string | null
  registration_mode: string
  roster_min: number
  roster_max: number
  sjtu_only: boolean
  auto_approve: boolean
  participant_contact: string
}

export type ScrimValues = {
  title: string
  description: string
  starts_at: string | null
  signup_closes_at: string | null
  format: string
  sjtu_only: boolean
}

export function tournamentValues(item: Tournament): TournamentValues {
  return {
    title: item.title,
    summary: item.summary,
    description: item.description,
    cover_image_id: item.cover_image_id,
    starts_at: item.starts_at,
    registration_opens_at: item.registration_opens_at,
    registration_closes_at: item.registration_closes_at,
    registration_mode: item.registration_mode,
    roster_min: item.roster_min,
    roster_max: item.roster_max,
    sjtu_only: item.sjtu_only,
    auto_approve: item.auto_approve,
    participant_contact: item.participant_contact ?? "",
  }
}

export function blankTournament(): TournamentValues {
  return {
    title: "",
    summary: "",
    description: "",
    cover_image_id: null,
    starts_at: null,
    registration_opens_at: null,
    registration_closes_at: null,
    registration_mode: "individual",
    roster_min: 5,
    roster_max: 6,
    sjtu_only: false,
    auto_approve: false,
    participant_contact: "",
  }
}

export function scrimValues(item: Scrim): ScrimValues {
  return {
    title: item.title,
    description: item.description,
    starts_at: item.starts_at,
    signup_closes_at: item.signup_closes_at,
    format: item.format,
    sjtu_only: item.sjtu_only,
  }
}

export function blankScrim(): ScrimValues {
  return {
    title: "",
    description: "",
    starts_at: null,
    signup_closes_at: null,
    format: "rq_5v5",
    sjtu_only: false,
  }
}

function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string"
}

export function currentTournament(value: unknown): SaveCurrent<TournamentValues> | null {
  const outer = record(value)
  if (!outer) return null
  const item = record(outer.values) ?? record(outer.tournament) ?? outer
  const version = outer.version ?? item.version
  if (!Number.isSafeInteger(version) || Number(version) < 0) return null
  const textKeys = ["title", "summary", "description", "registration_mode"] as const
  if (textKeys.some((key) => typeof item[key] !== "string")) return null
  const dateKeys = ["starts_at", "registration_opens_at", "registration_closes_at"] as const
  if (dateKeys.some((key) => !nullableString(item[key]))) return null
  if (item.cover_image_id !== null && !Number.isSafeInteger(item.cover_image_id)) return null
  if (!Number.isSafeInteger(item.roster_min) || !Number.isSafeInteger(item.roster_max)) return null
  if (typeof item.sjtu_only !== "boolean" || typeof item.auto_approve !== "boolean") return null
  return {
    version: Number(version),
    values: {
      title: String(item.title),
      summary: String(item.summary),
      description: String(item.description),
      registration_mode: String(item.registration_mode),
      cover_image_id: item.cover_image_id as number | null,
      starts_at: item.starts_at as string | null,
      registration_opens_at: item.registration_opens_at as string | null,
      registration_closes_at: item.registration_closes_at as string | null,
      roster_min: Number(item.roster_min),
      roster_max: Number(item.roster_max),
      sjtu_only: item.sjtu_only,
      auto_approve: item.auto_approve,
      participant_contact: typeof item.participant_contact === "string" ? item.participant_contact : "",
    },
  }
}

export function currentScrim(value: unknown): SaveCurrent<ScrimValues> | null {
  const outer = record(value)
  if (!outer) return null
  const item = record(outer.values) ?? record(outer.scrim) ?? outer
  const version = outer.version ?? item.version
  if (!Number.isSafeInteger(version) || Number(version) < 0) return null
  if (typeof item.title !== "string" || typeof item.description !== "string") return null
  if (typeof item.format !== "string" || typeof item.sjtu_only !== "boolean") return null
  if (!nullableString(item.starts_at) || !nullableString(item.signup_closes_at)) return null
  return {
    version: Number(version),
    values: {
      title: item.title,
      description: item.description,
      format: item.format,
      sjtu_only: item.sjtu_only,
      starts_at: item.starts_at,
      signup_closes_at: item.signup_closes_at,
    },
  }
}
