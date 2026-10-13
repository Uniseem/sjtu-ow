import type { RouteRecordRaw } from "vue-router"
import type { ActivityAction, ActivityKind } from "./domain"

const digits = ":id(\\d{1,18})"
const edit = () => import("./ActivityEdit.vue")
const list = () => import("./ActivityList.vue")
const confirm = () => import("./ActivityConfirm.vue")
const notice = () => import("./ActivityNotice.vue")

function actionRoute(kind: ActivityKind, action: ActivityAction): RouteRecordRaw {
  const path = action === "delete"
    ? `/admin/${kind}/delete/${digits}/`
    : kind === "tournaments" && action !== "cancel"
      ? `/admin/${kind}/${digits}/action/${action}/`
      : `/admin/${kind}/${digits}/${action}/`
  return {
    path,
    name: `admin-${kind}-${action}`,
    component: confirm,
    props: { kind, action },
    meta: { section: "activities", tab: kind },
  }
}

function activityRoutes(kind: ActivityKind): RouteRecordRaw[] {
  return [
    {
      path: `/admin/${kind}/`,
      name: `admin-${kind}`,
      component: list,
      props: { kind },
      meta: { section: "activities", tab: kind },
    },
    {
      path: `/admin/${kind}/new/`,
      name: `admin-${kind}-new`,
      component: edit,
      props: { kind, mode: "new" },
      meta: { section: "activities", tab: kind },
    },
    {
      path: `/admin/${kind}/edit/${digits}/`,
      name: `admin-${kind}-edit`,
      component: edit,
      props: { kind, mode: "edit" },
      meta: { section: "activities", tab: kind },
    },
    {
      path: `/admin/${kind}/copy/${digits}/`,
      name: `admin-${kind}-copy`,
      component: edit,
      props: { kind, mode: "copy" },
      meta: { section: "activities", tab: kind },
    },
    ...(["publish", "finish", "cancel", "delete"] as const).map((action) => actionRoute(kind, action)),
  ]
}

export const activitiesRoutes: RouteRecordRaw[] = [
  ...activityRoutes("tournaments"),
  ...activityRoutes("scrims"),
  {
    path: `/admin/tournaments/${digits}/teams/`,
    name: "admin-tournament-teams",
    component: () => import("./TournamentTeams.vue"),
    meta: { section: "activities", tab: "tournaments" },
  },
  {
    path: `/admin/scrims/${digits}/split/`,
    name: "admin-scrim-split",
    component: () => import("./ScrimSplit.vue"),
    meta: { section: "activities", tab: "scrims" },
  },
  {
    path: `/admin/scrims/${digits}/split/text/`,
    name: "admin-scrim-text",
    component: () => import("./ScrimText.vue"),
    meta: { section: "activities", tab: "scrims" },
  },
  {
    path: `/admin/announce/tournament/${digits}/`,
    name: "admin-tournament-notice",
    component: notice,
    props: { kind: "tournaments" },
    meta: { section: "activities", tab: "tournaments" },
  },
  {
    path: `/admin/announce/scrim/${digits}/`,
    name: "admin-scrim-notice",
    component: notice,
    props: { kind: "scrims" },
    meta: { section: "activities", tab: "scrims" },
  },
]
