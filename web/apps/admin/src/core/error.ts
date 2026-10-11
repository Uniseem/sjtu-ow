import { ApiError } from "@sjtu-ow/api"
export type AdminFailure = { status: number; title: string; message: string; retry: boolean }
export function adminFailure(error: unknown): AdminFailure {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401: return { status: 401, title: "登录已失效", message: "请重新登录后继续。", retry: false }
      case 403: return { status: 403, title: "没有权限", message: "你没有权限打开这个页面。", retry: false }
      case 404: return { status: 404, title: "页面不存在", message: "这个内容可能已被删除，或你无权查看。", retry: false }
      case 429: return { status: 429, title: "请求太频繁", message: "请稍后重新打开这个页面。", retry: true }
      default: return { status: error.status, title: "暂时无法打开", message: error.message || "请稍后再试。", retry: true }
    }
  }
  return { status: 0, title: "暂时无法打开", message: "页面没有加载完成，请重新打开。", retry: true }
}
