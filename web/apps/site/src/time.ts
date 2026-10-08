// Everything that shows a time goes through here: one timezone for the
// whole site, so the server and the browser compute the same string
// (12-architecture 6.3, SSR discipline).
const SHANGHAI = "Asia/Shanghai"

export function shanghaiYear(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-US", { timeZone: SHANGHAI, year: "numeric" }).format(now)
}
