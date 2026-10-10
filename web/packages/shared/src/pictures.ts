export type Section = "home" | "news" | "tournaments" | "scrims" | "teams" | "members"
// core/placeholders.py CATALOGUE: nine scenes, four variants. Offsets are
// by object type so IDs shared across tables do not share a cover.
export function coverPlaceholder(id: number, kind: "article" | "tournament" | "scrim" = "article"): string {
  const offset = { article: 0, tournament: 13, scrim: 26 }[kind]
  return `/static/img/placeholders/cover-${String(((id + offset) % 36) + 1).padStart(2, "0")}.svg`
}
// These six pairs are exported from the old section_paths by the fixture
// generator. Day and night use the same scene; CSS selects the mode.
export const SECTION_PICTURES: Record<Section, { light: string; dark: string }> = {
  home: { light: "section-home-light.svg", dark: "cover-02.svg" },
  news: { light: "section-news-light.svg", dark: "cover-20.svg" },
  tournaments: { light: "section-tournaments-light.svg", dark: "cover-07.svg" },
  scrims: { light: "section-scrims-light.svg", dark: "cover-21.svg" },
  teams: { light: "section-teams-light.svg", dark: "cover-01.svg" },
  members: { light: "section-members-light.svg", dark: "cover-33.svg" },
}
