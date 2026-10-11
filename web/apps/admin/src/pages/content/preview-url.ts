/** Preview URLs are server-issued same-origin document addresses. */
export function contentPreviewURL(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return null
  const url = new URL(value, location.origin)
  if (url.origin !== location.origin || url.username || url.password) return null
  if (!url.pathname.startsWith("/api/admin/")) return null
  return url.pathname + url.search
}
