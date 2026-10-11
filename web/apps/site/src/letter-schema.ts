import { ApiError } from "@sjtu-ow/api"
import type { GetApiLettersOut, GetApiLettersBatchOut } from "@sjtu-ow/api"
import type { PersonalLetterBatch } from "./letters"

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function invalid(): never {
  throw new ApiError(502, "invalid_letters", "信件暂时无法加载，请稍后再试。")
}

function integer(value: unknown, minimum: number): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum
}

function date(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value))
}

/** Validate identifiers before using them in selection or iframe destinations. */
export function readLetterBatch(raw: GetApiLettersBatchOut, requestedBatch: string): PersonalLetterBatch {
  const batch = record(raw)
  if (!batch || batch.batch !== requestedBatch) invalid()
  if (batch.state !== "waiting" && batch.state !== "done" && batch.state !== "expired") invalid()
  if (typeof batch.back !== "string" || typeof batch.in_back_office !== "boolean") invalid()
  if (!Array.isArray(batch.letters)) invalid()
  const ids = new Set<number>()
  for (const item of batch.letters) {
    const letter = record(item)
    if (!letter || !integer(letter.id, 1) || !integer(letter.count, 1)) invalid()
    if (typeof letter.subject !== "string" || typeof letter.who !== "string") invalid()
    if (ids.has(letter.id)) invalid()
    ids.add(letter.id)
    if (letter.preview_url !== undefined && typeof letter.preview_url !== "string") invalid()
  }
  if (batch.state === "waiting" && !batch.letters.length) invalid()
  return raw
}

export function readWaitingLetters(raw: GetApiLettersOut): GetApiLettersOut {
  const waiting = record(raw)
  if (!waiting || !Array.isArray(waiting.batches)) invalid()
  const ids = new Set<string>()
  for (const item of waiting.batches) {
    const batch = record(item)
    if (!batch || typeof batch.batch !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(batch.batch)) invalid()
    if (ids.has(batch.batch)) invalid()
    ids.add(batch.batch)
    if (!Array.isArray(batch.subjects) || batch.subjects.some((subject: unknown) => typeof subject !== "string")) invalid()
    if (!integer(batch.people, 0) || !date(batch.at) || typeof batch.in_back_office !== "boolean") invalid()
  }
  return raw
}
