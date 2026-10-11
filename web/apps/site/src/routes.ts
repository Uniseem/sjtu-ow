import type { RouteRecordRaw } from "vue-router"
import type { Component } from "vue"
import Page from "./pages/Page.vue"
import type { Load } from "./router"
import { PageRedirect } from "@sjtu-ow/shared/navigation"

// 02 号文档第 2、3 节里会打开成一页的地址，外加导航已经链到的四个说明页。
// 编号只认 1 到 18 位数字。只接受 POST 的动作、探针、图标、地图和片段不在这里。
const id = ":id(\\d{1,18})"

type Opts = { auth?: "member"; guest?: boolean }

// Pages that need a login (Django's login_required): SSR sends visitors to
// the login page first (router.ts RouteMeta.auth).
const MEMBER: Opts = { auth: "member" }

function redirected(path: string, location: string, status: 301 | 302, opts: Opts = {}): RouteRecordRaw {
  const load: Load = () => { throw new PageRedirect(location, status) }
  return { path, component: Page, meta: { load, ...opts } }
}

type PageModule = { default: Component; load?: Load }
function dynamicPage(path: string, comp: () => Promise<PageModule>, title: string, opts: Opts = {}): RouteRecordRaw {
  const load: Load = async (ctx) => {
    const mod = await comp()
    if (typeof mod.load === "function") {
      return mod.load(ctx)
    }
    return { title }
  }
  return { path, component: comp, meta: { load, ...opts } }
}

const standardPage = () => import("./pages/StandardPage.vue")

export const PAGES: RouteRecordRaw[] = [
  dynamicPage("/news/", () => import("./pages/News.vue"), "资讯"),
  // The slug follows Wagtail's (word characters and hyphens, Unicode
  // allowed, so percent-encoded bytes too); never a dot.
  dynamicPage(`/news/:slug([\\w%\\u0080-\\uffff-]+)/`, () => import("./pages/ArticleDetail.vue"), "文章"),
  dynamicPage("/about/", standardPage, "关于我们"),
  dynamicPage("/terms/", standardPage, "用户协议"),
  dynamicPage("/privacy/", standardPage, "隐私政策"),
  dynamicPage("/search/", () => import("./pages/Search.vue"), "站内搜索"),
  dynamicPage("/submit/", () => import("./pages/Submit.vue"), "投稿"),
  dynamicPage("/unsubscribe/:token/", () => import("./pages/Unsubscribe.vue"), "退订活动通知"),
  dynamicPage("/letters/", () => import("./pages/LettersWaiting.vue"), "还没发的信", MEMBER),
  dynamicPage("/letters/:batch/", () => import("./pages/LettersConfirm.vue"), "发信", MEMBER),
  dynamicPage(`/letters/:batch/${id}/`, () => import("./pages/LetterPreview.vue"), "信件预览", MEMBER),
  dynamicPage("/_styleguide/emails/", () => import("./pages/EmailSampleRedirect.vue"), "邮件样张"),
  dynamicPage("/_styleguide/emails/:key/", () => import("./pages/EmailSampleRedirect.vue"), "邮件预览"),
  dynamicPage("/me/", () => import("./pages/Profile.vue"), "个人中心", MEMBER),
  dynamicPage("/me/game-accounts/", () => import("./pages/GameAccounts.vue"), "游戏 ID", MEMBER),
  dynamicPage(`/me/game-accounts/${id}/`, () => import("./pages/GameAccounts.vue"), "游戏 ID 与段位", MEMBER),
  dynamicPage("/me/contacts/", () => import("./pages/Contacts.vue"), "联系方式", MEMBER),
  dynamicPage(`/me/contacts/${id}/`, () => import("./pages/Contacts.vue"), "联系方式", MEMBER),
  dynamicPage("/me/security/", () => import("./pages/Security.vue"), "账号安全", MEMBER),
  dynamicPage("/me/delete/", () => import("./pages/DeleteAccount.vue"), "注销账号", MEMBER),
  dynamicPage("/me/teams/", () => import("./pages/MyTeams.vue"), "我的战队", MEMBER),
  dynamicPage("/me/registrations/", () => import("./pages/MyRegistrations.vue"), "我的报名", MEMBER),
  dynamicPage("/me/scrims/", () => import("./pages/MyScrims.vue"), "我的内战", MEMBER),
  dynamicPage("/teams/new/", () => import("./pages/TeamCreate.vue"), "创建战队", MEMBER),
  dynamicPage(`/teams/${id}/`, () => import("./pages/TeamDetail.vue"), "战队"),
  dynamicPage(`/teams/${id}/apply/`, () => import("./pages/TeamApply.vue"), "申请入队", MEMBER),
  dynamicPage(`/teams/${id}/manage/`, () => import("./pages/TeamManage.vue"), "管理战队", MEMBER),
  dynamicPage("/members/", () => import("./pages/Members.vue"), "成员"),
  dynamicPage(`/members/${id}/`, () => import("./pages/MemberDetail.vue"), "成员"),
  dynamicPage("/tournaments/", () => import("./pages/Tournaments.vue"), "赛事"),
  dynamicPage(`/tournaments/${id}/`, () => import("./pages/TournamentDetail.vue"), "赛事"),
  dynamicPage(`/tournaments/${id}/register/`, () => import("./pages/TournamentRegister.vue"), "战队报名", MEMBER),
  dynamicPage(`/tournaments/${id}/signup/`, () => import("./pages/TournamentSignup.vue"), "个人报名", MEMBER),
  dynamicPage(`/registrations/${id}/`, () => import("./pages/RegistrationDetail.vue"), "报名", MEMBER),
  dynamicPage("/scrims/", () => import("./pages/Scrims.vue"), "内战"),
  dynamicPage(`/scrims/${id}/`, () => import("./pages/ScrimDetail.vue"), "内战"),
  dynamicPage("/accounts/login/", () => import("./pages/Login.vue"), "登录", { guest: true }),
  dynamicPage("/accounts/logout/", () => import("./pages/Logout.vue"), "退出登录"),
  dynamicPage("/accounts/inactive/", () => import("./pages/AccountResult.vue"), "账号已停用"),
  dynamicPage("/accounts/signup/", () => import("./pages/Signup.vue"), "注册", { guest: true }),
  dynamicPage("/accounts/reauthenticate/", () => import("./pages/Reauthenticate.vue"), "确认身份", MEMBER),
  dynamicPage("/accounts/email/", () => import("./pages/EmailChange.vue"), "修改邮箱", MEMBER),
  dynamicPage("/accounts/confirm-email/", () => import("./pages/ConfirmEmail.vue"), "验证邮箱"),
  dynamicPage("/accounts/password/change/", () => import("./pages/PasswordChange.vue"), "修改密码", MEMBER),
  redirected("/accounts/password/set/", "/me/security/", 301, MEMBER),
  dynamicPage("/accounts/password/reset/", () => import("./pages/PasswordReset.vue"), "找回密码"),
  dynamicPage("/accounts/password/reset/confirm/", () => import("./pages/PasswordResetCode.vue"), "找回密码"),
  dynamicPage("/accounts/password/reset/complete/", () => import("./pages/PasswordResetComplete.vue"), "设置新密码"),
  dynamicPage("/accounts/password/reset/done/", () => import("./pages/AccountResult.vue"), "密码已更新"),
  redirected("/accounts/login/code/confirm/", "/accounts/login/", 302, { guest: true }),
  // Other pages an editor makes under the home page (Wagtail's /<slug>/).
  // Fixed routes outrank it; Wagtail's slug is word characters and hyphens
  // (Unicode allowed, so percent-encoded bytes too), never a dot: /x.php/
  // stays a plain 404 without asking Go.
  dynamicPage("/:slug([\\w%\\u0080-\\uffff-]+)/", standardPage, "页面"),
]

