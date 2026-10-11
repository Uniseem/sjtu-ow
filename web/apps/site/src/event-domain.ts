import type { GetApiTournamentsOut, GetApiTournamentsIdOut, GetApiScrimsIdOut } from "@sjtu-ow/api"
import { owDate, owMd, owTime, owWeekday } from "@sjtu-ow/shared/time"
import { coverPlaceholder } from "@sjtu-ow/shared/pictures"
import { imageUrl } from "@sjtu-ow/shared/media"
import { httpError } from "./router"
export type Tournament = NonNullable<GetApiTournamentsIdOut["tournament"]>
export type TournamentCard = GetApiTournamentsOut["groups"][number]["tournaments"][number] & {
  roster_min: number
  roster_max: number
  registration_mode_label: string
  takes_individuals: boolean
  default_cover_image_id?: number | null
}
export type TournamentList = { banner_image_id?:number|null;groups: Array<{ phase: string; label: string; tournaments: TournamentCard[] }> }
export type TournamentPage = GetApiTournamentsIdOut & {
  body_html?: string
  default_cover_image_id?: number | null
  articles?: Array<{ id: number; slug: string; title: string; first_published_at?: string | null }>
}
export type ScrimPage = GetApiScrimsIdOut & { body_html?: string; default_cover_image_id?: number | null }
export function requireTournament(value: Tournament | null): Tournament { if (!value) throw httpError(404); return value }
export function eventDate(value: string | null | undefined): string { return value ? owDate(new Date(value)) : "待定" }
export function eventDateTime(value: string | null | undefined, weekday = false): string { return value ? owDate(new Date(value)) + (weekday ? " " + owWeekday(new Date(value)) : "") + " " + owTime(new Date(value)) : "待定" }
export function eventShortTime(value: string | null | undefined, weekday = true): string { return value ? owMd(new Date(value)) + (weekday ? " " + owWeekday(new Date(value)) : "") + " " + owTime(new Date(value)) : "待定" }
export function eventCover(id: number, kind: "tournament" | "scrim", image: number | null | undefined): string { return image ? imageUrl(image,"fill-2400x900-c50") : coverPlaceholder(id,kind) }
export function modeLabel(mode: string): string { return mode === "individual" ? "个人报名" : "整队报名" }
export function modeSummary(mode: string): string { return mode === "individual" ? "每人报名，管理员编队" : "队长为全队报名" }
