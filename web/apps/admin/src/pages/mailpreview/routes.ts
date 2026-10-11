import type { RouteRecordRaw } from "vue-router"

export const mailpreviewRoutes: RouteRecordRaw[] = [
  {
    path: "/admin/settings/email-samples/",
    name: "admin-mail-samples",
    component: () => import("./MailSamplesPage.vue"),
    meta: { section: "settings", tab: "email_samples", title: "邮件样张" },
  },
  {
    path: "/admin/settings/email-samples/:key([a-z][a-z0-9-]*)/",
    name: "admin-mail-sample",
    component: () => import("./MailSamplePage.vue"),
    meta: { section: "settings", tab: "email_samples", title: "邮件样张" },
  },
]
