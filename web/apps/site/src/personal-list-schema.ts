import { ApiError } from "@sjtu-ow/api"
import type { GetApiMeTeamsOut, GetApiMeRegistrationsOut } from "@sjtu-ow/api"
import type { PersonalMemberships } from "./team-display"
import type { PersonalRegistrations } from "./registration-display"
import type { PersonalScrims } from "./pending-api"

type Row = Record<string, unknown>

function row(value: unknown): Row | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Row
    : null
}

function invalid(): never {
  throw new ApiError(502, "invalid_personal_list", "个人信息暂时无法加载，请稍后再试。")
}

function id(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0
}

function textFields(value: Row, names: string[]): void {
  if (names.some((name) => typeof value[name] !== "string")) invalid()
}

function booleanFields(value: Row, names: string[]): void {
  if (names.some((name) => typeof value[name] !== "boolean")) invalid()
}

function date(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value))
}

function rows(value: unknown, identifier: string): Row[] {
  if (!Array.isArray(value)) invalid()
  const identifiers = new Set<number>()
  return value.map((entry: unknown) => {
    const item = row(entry)
    if (!item || !id(item[identifier])) invalid()
    const number = item[identifier] as number
    if (identifiers.has(number)) invalid()
    identifiers.add(number)
    return item
  })
}

/** Optional private projections are validated when present, never invented. */
export function personalMemberships(raw: GetApiMeTeamsOut): PersonalMemberships {
  const value = row(raw)
  if (!value) invalid()
  for (const team of rows(value.teams, "team_id")) {
    textFields(team, ["name", "role"])
    if (!date(team.joined_at)) invalid()
    if (team.role !== "captain" && team.role !== "member") invalid()
    if (typeof team.member_count !== "number" || !Number.isSafeInteger(team.member_count) || team.member_count < 0) invalid()
    if (team.member_contact !== undefined && typeof team.member_contact !== "string") invalid()
    if (team.logo_image_id !== null && !id(team.logo_image_id)) invalid()
  }
  for (const application of rows(value.applications, "id")) {
    if (!id(application.team_id)) invalid()
    textFields(application, ["team_name", "status", "decision_note"])
    if (!date(application.created_at)) invalid()
    if (application.decided_at !== undefined && application.decided_at !== null && !date(application.decided_at)) invalid()
    if (!Array.isArray(application.roles) || application.roles.some((role: unknown) => typeof role !== "string")) invalid()
  }
  if (value.alumni !== undefined) {
    for (const alumnus of rows(value.alumni, "id")) {
      if (!id(alumnus.team_id)) invalid()
      textFields(alumnus, ["team_name"])
      if (!date(alumnus.joined_at) || !date(alumnus.left_at)) invalid()
    }
  }
  return raw
}

export function personalRegistrations(raw: GetApiMeRegistrationsOut): PersonalRegistrations {
  const value = row(raw)
  if (!value) invalid()
  for (const registration of rows(value.registrations, "registration_id")) {
    if (!id(registration.tournament_id)) invalid()
    textFields(registration, ["title", "team_name", "status"])
    if (!date(registration.submitted_at)) invalid()
    if (registration.team_id !== undefined && registration.team_id !== null && !id(registration.team_id)) invalid()
    if (registration.starts_at !== undefined && registration.starts_at !== null && !date(registration.starts_at)) invalid()
    if (registration.starts_label !== undefined && typeof registration.starts_label !== "string") invalid()
    if (registration.status_label !== undefined && typeof registration.status_label !== "string") invalid()
  }
  if (value.individual_signups !== undefined) {
    for (const signup of rows(value.individual_signups, "id")) {
      if (!id(signup.tournament_id)) invalid()
      textFields(signup, ["title", "starts_label", "registration_team_name", "tournament_status"])
      booleanFields(signup, ["role_tank", "role_damage", "role_support", "registration_open"])
      if (signup.starts_at !== null && !date(signup.starts_at)) invalid()
      if (signup.battletag !== null && typeof signup.battletag !== "string") invalid()
      if (signup.registration_id !== null && !id(signup.registration_id)) invalid()
    }
  }
  if (value.calendar !== undefined && value.calendar !== null) {
    const calendar = row(value.calendar)
    if (!calendar) invalid()
    textFields(calendar, ["url", "webcal"])
    calendarAddress(calendar.url as string, calendar.webcal as string)
  }
  return raw
}

export function personalScrims(raw: PersonalScrims): PersonalScrims {
  const value = row(raw)
  if (!value) invalid()
  for (const signup of rows(value.signups, "id")) {
    if (!id(signup.scrim_id)) invalid()
    textFields(signup, ["title", "placement", "status"])
    booleanFields(signup, ["role_tank", "role_damage", "role_support"])
    if (signup.starts_at !== null && !date(signup.starts_at)) invalid()
  }
  return raw
}

export function calendarAddress(https: string, webcal: string): void {
  try {
    const url = new URL(https)
    const subscription = new URL(webcal)
    if (url.protocol !== "https:" && url.protocol !== "http:") invalid()
    if (subscription.protocol !== "webcal:") invalid()
    if (url.username || url.password || subscription.username || subscription.password) invalid()
    if (url.host !== subscription.host || url.pathname !== subscription.pathname || url.search !== subscription.search) invalid()
  } catch {
    invalid()
  }
}
