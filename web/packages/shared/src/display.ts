/** Python round(): halfway cases round to the even integer (ow.seats). */
function roundEven(n: number): number {
  const low = Math.floor(n)
  return n - low === 0.5 ? low + (low % 2) : Math.round(n)
}
export function seatCells(taken: number, total: number): boolean[] {
  if (!Number.isFinite(taken) || !Number.isFinite(total)) return []
  const got = Math.max(Math.trunc(taken), 0)
  const need = Math.max(Math.trunc(total), 0)
  if (need === 0) return []
  const cells = Math.min(need, 24)
  const filled = Math.min(cells, roundEven(got * cells / need))
  return Array.from({ length: cells }, (_, i) => i < filled)
}
export function rankParts(label: string): [string, string] {
  const text = label.trim()
  const space = text.indexOf(" ")
  return space < 0 ? [text, ""] : [text.slice(0, space), text.slice(space + 1)]
}
