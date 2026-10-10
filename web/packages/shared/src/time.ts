// Everything that shows a time goes through here: one timezone for the
// whole site, so the server and the browser compute the same string
// (12-architecture 6.3, SSR discipline).
const SHANGHAI = "Asia/Shanghai"

export function shanghaiYear(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-US", { timeZone: SHANGHAI, year: "numeric" }).format(now)
}

const WEEK: Record<string, string> = { Sun: "日", Mon: "一", Tue: "二", Wed: "三", Thu: "四", Fri: "五", Sat: "六" }

export type ShanghaiParts = {
  year: string
  month: string
  day: string
  hour: string
  minute: string
  weekday: string
}

export function shanghaiParts(date: Date): ShanghaiParts {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: SHANGHAI,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    weekday: "short",
  })
  const bag: Record<string, string> = {}
  for (const part of fmt.formatToParts(date)) bag[part.type] = part.value
  return {
    year: bag.year,
    month: bag.month,
    day: bag.day,
    hour: bag.hour,
    minute: bag.minute,
    weekday: "周" + (WEEK[bag.weekday] ?? ""),
  }
}

/** 19:30 in Shanghai on the calendar day of `now`, shifted by whole days. */
export function shanghaiEvening(dayOffset: number, now: Date = new Date()): Date {
  const bag = shanghaiParts(now)
  return new Date(Date.UTC(Number(bag.year), Number(bag.month) - 1, Number(bag.day) + dayOffset, 11, 30, 0))
}

export function owDate(date: Date): string {
  const p = shanghaiParts(date)
  return `${p.year}.${p.month}.${p.day}`
}

export function owMd(date: Date): string {
  const p = shanghaiParts(date)
  return `${p.month}.${p.day}`
}

export function owTime(date: Date): string {
  const p = shanghaiParts(date)
  return `${p.hour}:${p.minute}`
}

export function owWeekday(date: Date): string {
  return shanghaiParts(date).weekday
}

export function owMonthNum(date: Date): string {
  return String(Number(shanghaiParts(date).month))
}

export function owDay(date: Date): string {
  return shanghaiParts(date).day
}
