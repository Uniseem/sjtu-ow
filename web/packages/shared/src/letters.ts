import { safeNext } from "@sjtu-ow/shared/navigation"
import { shanghaiParts } from "@sjtu-ow/shared/time"
import type { GetApiLettersBatchOut } from "@sjtu-ow/api"
import { ApiError } from "@sjtu-ow/api"

export type PersonalLetter = GetApiLettersBatchOut["letters"][number] & {
  preview_url?: string
}

export type PersonalLetterBatch = Omit<GetApiLettersBatchOut, "letters"> & {
  letters: PersonalLetter[]
}

export function letterBatch(value: string | undefined): string {
  if (!value || !/^[A-Za-z0-9_-]{1,128}$/.test(value)) throw new ApiError(404, "not_found", "没有这批信。")
  return value
}

export function letterDate(value: string): string {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ""
  const parts = shanghaiParts(date)
  return `${Number(parts.month)} 月 ${Number(parts.day)} 日 ${parts.hour}:${parts.minute}`
}

/** Only the server's own private preview URL may be used in an iframe. */
export function previewURL(value: string | undefined, batch: string, id: number): string | null {
  if (!value) return null
  const path = safeNext(value, "")
  if (!path || path.includes("?") || path.includes("#")) return null
  const encoded = encodeURIComponent(batch)
  const allowed = [
    `/letters/${encoded}/${id}/`,
    `/api/letters/${encoded}/${id}/preview`,
  ]
  return allowed.includes(path) ? path : null
}

export function returnFromLetters(value: string | undefined): string {
  const destination = safeNext(value, "/letters/")
  // Returning to the same confirmation document would loop after handling it.
  if (/^\/(?:admin\/)?letters\/[^/]+\//.test(destination)) return "/letters/"
  return destination
}

export function waitingURL(batch: string, backOffice: boolean): string {
  return `${backOffice ? '/admin' : ''}/letters/${encodeURIComponent(batch)}/`
}
