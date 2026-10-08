import type { RouteRecordRaw } from "vue-router"
import Page from "./pages/Page.vue"
import type { Load } from "./router"

// 02 号文档第 2、3 节里会打开成一页的地址，外加导航已经链到的四个说明页。
// 编号只认 1 到 18 位数字。只接受 POST 的动作、探针、图标、地图和片段不在这里。
const id = ":id(\\d{1,18})"

function page(path: string, title: string): RouteRecordRaw {
  const load: Load = () => ({ title })
  return { path, component: Page, meta: { load } }
}

export const PAGES: RouteRecordRaw[] = [
  page("/news/", "资讯"),
  page("/about/", "关于我们"),
  page("/terms/", "用户协议"),
  page("/privacy/", "隐私政策"),
  page("/search/", "搜索"),
  page("/submit/", "我要投稿"),
  page("/unsubscribe/:token/", "退订"),
  page("/letters/", "待发信"),
  page("/letters/:batch/", "确认发信"),
  page(`/letters/:batch/${id}/`, "信件预览"),
  page("/_styleguide/", "样式"),
  page("/_styleguide/emails/", "邮件样张"),
  page("/_styleguide/emails/:key/", "邮件预览"),
  page("/me/", "个人中心"),
  page("/me/game-accounts/", "游戏 ID"),
  page(`/me/game-accounts/${id}/`, "编辑游戏 ID"),
  page("/me/contacts/", "联系方式"),
  page(`/me/contacts/${id}/`, "编辑联系方式"),
  page("/me/security/", "账号安全"),
  page("/me/delete/", "注销账号"),
  page("/me/teams/", "我的战队"),
  page("/me/registrations/", "我的报名"),
  page("/me/scrims/", "我的内战"),
  page("/teams/new/", "创建战队"),
  page(`/teams/${id}/`, "战队"),
  page(`/teams/${id}/apply/`, "申请入队"),
  page(`/teams/${id}/manage/`, "管理战队"),
  page("/members/", "成员"),
  page(`/members/${id}/`, "成员"),
  page("/tournaments/", "赛事"),
  page(`/tournaments/${id}/`, "赛事"),
  page(`/tournaments/${id}/register/`, "战队报名"),
  page(`/tournaments/${id}/signup/`, "个人报名"),
  page(`/registrations/${id}/`, "报名"),
  page("/scrims/", "内战"),
  page(`/scrims/${id}/`, "内战"),
  page("/accounts/login/", "登录"),
  page("/accounts/logout/", "退出"),
  page("/accounts/inactive/", "账号已停用"),
  page("/accounts/signup/", "注册"),
  page("/accounts/reauthenticate/", "重新验证"),
  page("/accounts/email/", "邮箱"),
  page("/accounts/confirm-email/", "验证邮箱"),
  page("/accounts/password/change/", "修改密码"),
  page("/accounts/password/set/", "设置密码"),
  page("/accounts/password/reset/", "重置密码"),
  page("/accounts/password/reset/confirm/", "输入重置码"),
  page("/accounts/password/reset/complete/", "设置新密码"),
  page("/accounts/password/reset/done/", "密码已重置"),
  page("/accounts/login/code/confirm/", "登录"),
]
