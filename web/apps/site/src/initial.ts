// The first Chinese character or letter of a name, for avatars; leading
// symbols, emoji and spaces are skipped; "?" when there is none
// (design-details 2.2). Same rule as the Django site's ow.initial filter.
export function initial(value: string | null | undefined): string {
  for (const char of String(value ?? "")) {
    if (/[\p{L}\p{N}]/u.test(char)) return char.toUpperCase()
  }
  return "?"
}

export function hue(id: number | null | undefined): number {
  return ((Number(id) || 0) % 5) + 1
}

