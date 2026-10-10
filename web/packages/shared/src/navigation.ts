/** Redirect targets are relative site addresses, including their query/fragment. */
export function safeNext(value: unknown, fallback = "/"): string {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) return fallback
  if (/[\\\u0000-\u0020\u007f]/.test(value)) return fallback
  try {
    const decoded = decodeURIComponent(value.split(/[?#]/, 1)[0])
    if (decoded.startsWith("//") || /[\\\u0000-\u0020\u007f]/.test(decoded)) return fallback
    const url = new URL(value, "http://site")
    return url.origin === "http://site" ? value : fallback
  } catch { return fallback }
}

export class PageRedirect extends Error {
  constructor(public location: string, public status: 301 | 302 = 302) {
    super("redirect")
    this.location = safeNext(location)
  }
}

/** Ordinary submitters use 我要投稿, matching Django's runs_admin menu filter. */
export function runsAdmin(user: { admin: boolean; superuser?: boolean; caps?: string[] } | null): boolean {
  return !!user?.admin && (!!user.superuser || !!user.caps?.some((cap) => !["admin.enter", "articles.publish_own", "images.contribute"].includes(cap)))
}
