import type { ViewerUser } from "../viewer"

export type AdminTab = {
  id: string
  label: string
  path: string
  reqCap?: string
  reqSuperuser?: boolean
  subtabs?: { id: string; label: string; path: string }[]
}

export type AdminSection = {
  id: string
  label: string
  path: string
  tabs: AdminTab[]
  allowed(u: ViewerUser | null): boolean
}

export function hasCap(u: ViewerUser | null, cap: string): boolean {
  if (!u || !u.admin) return false
  if (u.superuser) return true
  return u.caps?.includes(cap) ?? false
}

export const ADMIN_SECTIONS: AdminSection[] = [
  {
    id: "home",
    label: "首页",
    path: "/admin/",
    tabs: [],
    allowed: (u) => Boolean(u?.admin),
  },
  {
    id: "content",
    label: "内容",
    path: "/admin/articles/",
    tabs: [
      { id: "articles", label: "文章", path: "/admin/articles/" },
      { id: "categories", label: "分类", path: "/admin/categories/", reqCap: "article_categories.manage" },
      { id: "home_pins", label: "首页置顶", path: "/admin/home-pins/", reqCap: "articles.edit_any" },
      { id: "images", label: "图片", path: "/admin/images/", reqCap: "images.contribute" },
    ],
    allowed: (u) =>
      Boolean(u?.admin) &&
      (Boolean(u?.superuser) ||
        hasCap(u, "articles.publish_own") ||
        hasCap(u, "articles.edit_any") ||
        hasCap(u, "articles.edit_author") ||
        hasCap(u, "article_categories.manage") ||
        hasCap(u, "images.contribute") ||
        hasCap(u, "images.manage")),
  },
  {
    id: "events",
    label: "活动",
    path: "/admin/tournaments/",
    tabs: [
      { id: "tournaments", label: "赛事", path: "/admin/tournaments/", reqCap: "tournaments.manage" },
      { id: "scrims", label: "内战", path: "/admin/scrims/", reqCap: "scrims.manage" },
    ],
    allowed: (u) => Boolean(u?.admin) && (Boolean(u?.superuser) || hasCap(u, "tournaments.manage") || hasCap(u, "scrims.manage")),
  },
  {
    id: "members",
    label: "成员",
    path: "/admin/users/",
    tabs: [
      {
        id: "users",
        label: "用户与权限",
        path: "/admin/users/",
        reqSuperuser: true,
        subtabs: [
          { id: "users", label: "用户", path: "/admin/users/" },
          { id: "roles", label: "角色", path: "/admin/roles/" },
        ],
      },
      { id: "teams", label: "战队", path: "/admin/teams/", reqSuperuser: true },
      { id: "member_groups", label: "成员分组", path: "/admin/member-groups/", reqCap: "member_groups.manage" },
    ],
    allowed: (u) => Boolean(u?.admin) && (Boolean(u?.superuser) || hasCap(u, "member_groups.manage")),
  },
  {
    id: "review",
    label: "审核",
    path: "/admin/registrations/",
    tabs: [
      { id: "registrations", label: "报名", path: "/admin/registrations/", reqCap: "tournaments.manage" },
      { id: "moderation", label: "内容", path: "/admin/moderation/", reqCap: "moderation.review" },
      { id: "avatars", label: "头像", path: "/admin/avatars/", reqCap: "moderation.review" },
      { id: "comments", label: "评论", path: "/admin/comments/", reqCap: "comments.moderate" },
    ],
    allowed: (u) =>
      Boolean(u?.admin) &&
      (Boolean(u?.superuser) ||
        hasCap(u, "tournaments.manage") ||
        hasCap(u, "moderation.review") ||
        hasCap(u, "comments.moderate")),
  },
  {
    id: "data",
    label: "数据",
    path: "/admin/activity/",
    tabs: [{ id: "activity", label: "活动数据", path: "/admin/activity/", reqCap: "activity.view" }],
    allowed: (u) => Boolean(u?.admin) && (Boolean(u?.superuser) || hasCap(u, "activity.view")),
  },
  {
    id: "settings",
    label: "设置",
    path: "/admin/settings/site/",
    tabs: [
      { id: "site", label: "全站设置", path: "/admin/settings/site/", reqSuperuser: true },
      { id: "log", label: "操作记录", path: "/admin/log/", reqSuperuser: true },
    ],
    allowed: (u) => Boolean(u?.admin) && Boolean(u?.superuser),
  },
  {
    id: "manual",
    label: "手册",
    path: "/admin/manual/",
    tabs: [],
    allowed: (u) => Boolean(u?.admin),
  },
]

export function isTabVisible(tab: AdminTab, u: ViewerUser | null): boolean {
  if (!u || !u.admin) return false
  if (u.superuser) return true
  if (tab.reqSuperuser) return false
  if (tab.reqCap) return hasCap(u, tab.reqCap)
  return true
}

export function sectionForPath(path: string): AdminSection | undefined {
  if (path === "/admin/" || path.startsWith("/admin/letters")) return ADMIN_SECTIONS.find((s) => s.id === "home")
  if (
    path.startsWith("/admin/articles") ||
    path.startsWith("/admin/categories") ||
    path.startsWith("/admin/home-pins") ||
    path.startsWith("/admin/images") ||
    path.startsWith("/admin/pages")
  ) {
    return ADMIN_SECTIONS.find((s) => s.id === "content")
  }
  if (path.startsWith("/admin/tournaments") || path.startsWith("/admin/scrims")) {
    return ADMIN_SECTIONS.find((s) => s.id === "events")
  }
  if (
    path.startsWith("/admin/users") ||
    path.startsWith("/admin/roles") ||
    path.startsWith("/admin/teams") ||
    path.startsWith("/admin/member-groups")
  ) {
    return ADMIN_SECTIONS.find((s) => s.id === "members")
  }
  if (
    path.startsWith("/admin/registrations") ||
    path.startsWith("/admin/moderation") ||
    path.startsWith("/admin/avatars") ||
    path.startsWith("/admin/comments")
  ) {
    return ADMIN_SECTIONS.find((s) => s.id === "review")
  }
  if (path.startsWith("/admin/activity")) {
    return ADMIN_SECTIONS.find((s) => s.id === "data")
  }
  if (path.startsWith("/admin/settings") || path.startsWith("/admin/log")) {
    return ADMIN_SECTIONS.find((s) => s.id === "settings")
  }
  if (path.startsWith("/admin/manual")) {
    return ADMIN_SECTIONS.find((s) => s.id === "manual")
  }
  return undefined
}
