import type { RouteRecordRaw } from "vue-router"
import Page from "./pages/Page.vue"
import type { Load } from "./router"

// 02 号文档第 2、3 节里会打开成一页的地址，外加导航已经链到的四个说明页。
// 编号只认 1 到 18 位数字。只接受 POST 的动作、探针、图标、地图和片段不在这里。
const id = ":id(\\d{1,18})"

type Opts = { auth?: "member" }

// Pages that need a login (Django's login_required): SSR sends visitors to
// the login page first (router.ts RouteMeta.auth).
const MEMBER: Opts = { auth: "member" }

function page(path: string, title: string, opts: Opts = {}): RouteRecordRaw {
  const load: Load = () => ({ title })
  return { path, component: Page, meta: { load, ...opts } }
}

function dynamicPage(path: string, comp: () => Promise<any>, title: string, opts: Opts = {}): RouteRecordRaw {
  const load: Load = async (ctx) => {
    const mod = await comp()
    if (typeof mod.load === "function") {
      return mod.load(ctx)
    }
    return { title }
  }
  return { path, component: comp, meta: { load, ...opts } }
}

export const PAGES: RouteRecordRaw[] = [
  dynamicPage("/news/", () => import("./pages/News.vue"), "资讯"),
  page("/about/", "关于我们"),
  page("/terms/", "用户协议"),
  page("/privacy/", "隐私政策"),
  page("/search/", "搜索"),
  page("/submit/", "我要投稿"),
  page("/unsubscribe/:token/", "退订"),
  page("/letters/", "待发信", MEMBER),
  page("/letters/:batch/", "确认发信", MEMBER),
  page(`/letters/:batch/${id}/`, "信件预览", MEMBER),
  page("/_styleguide/emails/", "邮件样张"),
  page("/_styleguide/emails/:key/", "邮件预览"),
  dynamicPage("/me/", () => import("./pages/Profile.vue"), "个人中心", MEMBER),
  dynamicPage("/me/game-accounts/", () => import("./pages/GameAccounts.vue"), "游戏 ID", MEMBER),
  page(`/me/game-accounts/${id}/`, "编辑游戏 ID", MEMBER),
  dynamicPage("/me/contacts/", () => import("./pages/Contacts.vue"), "联系方式", MEMBER),
  page(`/me/contacts/${id}/`, "编辑联系方式", MEMBER),
  page("/me/security/", "账号安全", MEMBER),
  page("/me/delete/", "注销账号", MEMBER),
  page("/me/teams/", "我的战队", MEMBER),
  page("/me/registrations/", "我的报名", MEMBER),
  page("/me/scrims/", "我的内战", MEMBER),
  page("/teams/new/", "创建战队", MEMBER),
  dynamicPage(`/teams/${id}/`, () => import("./pages/TeamDetail.vue"), "战队"),
  dynamicPage(`/teams/${id}/apply/`, () => import("./pages/TeamApply.vue"), "申请入队", MEMBER),
  page(`/teams/${id}/manage/`, "管理战队", MEMBER),
  dynamicPage("/members/", () => import("./pages/Members.vue"), "成员"),
  dynamicPage(`/members/${id}/`, () => import("./pages/MemberDetail.vue"), "成员"),
  dynamicPage("/tournaments/", () => import("./pages/Tournaments.vue"), "赛事"),
  dynamicPage(`/tournaments/${id}/`, () => import("./pages/TournamentDetail.vue"), "赛事"),
  page(`/tournaments/${id}/register/`, "战队报名", MEMBER),
  page(`/tournaments/${id}/signup/`, "个人报名", MEMBER),
  page(`/registrations/${id}/`, "报名", MEMBER),
  dynamicPage("/scrims/", () => import("./pages/Scrims.vue"), "内战"),
  dynamicPage(`/scrims/${id}/`, () => import("./pages/ScrimDetail.vue"), "内战"),
  dynamicPage("/accounts/login/", () => import("./pages/Login.vue"), "登录"),
  page("/accounts/logout/", "退出"),
  page("/accounts/inactive/", "账号已停用"),
  dynamicPage("/accounts/signup/", () => import("./pages/Signup.vue"), "注册"),
  page("/accounts/reauthenticate/", "重新验证", MEMBER),
  page("/accounts/email/", "邮箱", MEMBER),
  dynamicPage("/accounts/confirm-email/", () => import("./pages/ConfirmEmail.vue"), "验证邮箱"),
  page("/accounts/password/change/", "修改密码", MEMBER),
  page("/accounts/password/set/", "设置密码", MEMBER),
  page("/accounts/password/reset/", "重置密码"),
  page("/accounts/password/reset/confirm/", "输入重置码"),
  page("/accounts/password/reset/complete/", "设置新密码"),
  page("/accounts/password/reset/done/", "密码已重置"),
  page("/accounts/login/code/confirm/", "登录"),
]

function admin(path: string, comp: () => Promise<any>, title: string): RouteRecordRaw {
  const load: Load = () => ({ title })
  return { path, component: comp, meta: { load, admin: true, auth: "member" } }
}

export const ADMIN_PAGES: RouteRecordRaw[] = [
  admin("/admin/", () => import("./pages/admin/AdminHome.vue"), "管理后台首页"),
  admin("/admin/letters/", () => import("./pages/admin/AdminLetters.vue"), "待发信管理"),
  admin("/admin/letters/:batch/", () => import("./pages/admin/AdminLetters.vue"), "确认发信批次"),
  admin(`/admin/letters/:batch/${id}/`, () => import("./pages/admin/AdminLetters.vue"), "信件预览"),
  admin("/admin/articles/", () => import("./pages/admin/AdminArticles.vue"), "文章管理"),
  admin("/admin/articles/new/", () => import("./pages/admin/AdminArticleEdit.vue"), "写新文章"),
  admin(`/admin/articles/${id}/`, () => import("./pages/admin/AdminArticleEdit.vue"), "编辑文章"),
  admin("/admin/categories/", () => import("./pages/admin/AdminCategories.vue"), "分类管理"),
  admin("/admin/categories/new/", () => import("./pages/admin/AdminCategories.vue"), "新建分类"),
  admin(`/admin/categories/${id}/`, () => import("./pages/admin/AdminCategories.vue"), "编辑分类"),
  admin("/admin/home-pins/", () => import("./pages/admin/AdminHomePins.vue"), "首页置顶文章"),
  admin("/admin/images/", () => import("./pages/admin/AdminImages.vue"), "图片媒体库"),
  admin("/admin/tournaments/", () => import("./pages/admin/AdminTournaments.vue"), "赛事管理"),
  admin("/admin/tournaments/new/", () => import("./pages/admin/AdminTournamentEdit.vue"), "新建赛事"),
  admin(`/admin/tournaments/${id}/`, () => import("./pages/admin/AdminTournamentEdit.vue"), "编辑赛事"),
  admin(`/admin/tournaments/${id}/board/`, () => import("./pages/admin/AdminTournamentBoard.vue"), "队伍编排板"),
  admin(`/admin/tournaments/${id}/review/`, () => import("./pages/admin/AdminTournamentReview.vue"), "报名审核"),
  admin("/admin/scrims/", () => import("./pages/admin/AdminScrims.vue"), "内战管理"),
  admin("/admin/scrims/new/", () => import("./pages/admin/AdminScrimEdit.vue"), "新建内战"),
  admin(`/admin/scrims/${id}/`, () => import("./pages/admin/AdminScrimEdit.vue"), "编辑内战"),
  admin(`/admin/scrims/${id}/split/`, () => import("./pages/admin/AdminScrimBoard.vue"), "内战分队板"),
  admin("/admin/users/", () => import("./pages/admin/AdminUsers.vue"), "用户管理"),
  admin(`/admin/users/${id}/`, () => import("./pages/admin/AdminUserDetail.vue"), "用户详情与权限"),
  admin("/admin/roles/", () => import("./pages/admin/AdminRoles.vue"), "角色与功能限制"),
  admin("/admin/teams/", () => import("./pages/admin/AdminTeams.vue"), "战队管理"),
  admin(`/admin/teams/${id}/`, () => import("./pages/admin/AdminTeams.vue"), "战队详情"),
  admin("/admin/member-groups/", () => import("./pages/admin/AdminMemberGroups.vue"), "成员分组管理"),
  admin("/admin/member-groups/new/", () => import("./pages/admin/AdminMemberGroups.vue"), "新建成员分组"),
  admin(`/admin/member-groups/${id}/`, () => import("./pages/admin/AdminMemberGroups.vue"), "编辑成员分组"),
  admin("/admin/registrations/", () => import("./pages/admin/AdminRegistrations.vue"), "赛事报名审核"),
  admin(`/admin/registrations/${id}/`, () => import("./pages/admin/AdminRegistrations.vue"), "赛事报名审核"),
  admin("/admin/moderation/", () => import("./pages/admin/AdminModeration.vue"), "内容巡查与审核"),
  admin(`/admin/moderation/${id}/`, () => import("./pages/admin/AdminModeration.vue"), "审核处置详情"),
  admin("/admin/avatars/", () => import("./pages/admin/AdminAvatars.vue"), "头像审核"),
  admin("/admin/comments/", () => import("./pages/admin/AdminComments.vue"), "评论管理"),
  admin("/admin/activity/", () => import("./pages/admin/AdminActivity.vue"), "活动数据统计"),
  admin("/admin/settings/", () => import("./pages/admin/AdminSettings.vue"), "全站设置"),
  admin("/admin/settings/site/", () => import("./pages/admin/AdminSettings.vue"), "全站设置"),
  admin("/admin/log/", () => import("./pages/admin/AdminAuditLog.vue"), "操作记录与审计日志"),
  admin("/admin/manual/", () => import("./pages/admin/AdminManual.vue"), "干部操作手册"),
]

PAGES.push(...ADMIN_PAGES)

