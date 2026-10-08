// The main navigation (design 13.3). Which item is current follows the
// start of the path, like the Django site's main_nav.html: /me/teams/ is
// not 战队, /registrations/ belongs to 赛事.
export type Section = "home" | "news" | "tournaments" | "scrims" | "teams" | "members"

export const NAV: { to: string; label: string; section: Section }[] = [
  { to: "/", label: "首页", section: "home" },
  { to: "/news/", label: "资讯", section: "news" },
  { to: "/tournaments/", label: "赛事", section: "tournaments" },
  { to: "/scrims/", label: "内战", section: "scrims" },
  { to: "/teams/", label: "战队", section: "teams" },
  { to: "/members/", label: "成员", section: "members" },
]

const PREFIXES: [string, Section][] = [
  ["/news/", "news"],
  ["/tournaments/", "tournaments"],
  ["/registrations/", "tournaments"],
  ["/scrims/", "scrims"],
  ["/teams/", "teams"],
  ["/members/", "members"],
]

export function sectionOf(path: string): Section | null {
  if (path === "/") return "home"
  for (const [prefix, section] of PREFIXES) {
    if (path.startsWith(prefix)) return section
  }
  return null
}
