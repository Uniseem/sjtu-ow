// 12 号文档 6.4：错误转换、401 跳登录、待发信跳确认页、写请求带幂等键。
// apigen 生成的每个函数都经过这里（frontend-migration A3）：页面不自己 fetch。

export class ApiError extends Error {
  /** HTTP 状态码；连不上、超时是 0。 */
  status: number
  /** 接口给的错误码（`invalid`、`stale`……）；连不上是 `network`，超时是 `timeout`。 */
  code: string
  fields?: Record<string, string[]>
  current?: unknown

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

/** 生成的函数在路径、请求体、查询参数之外还能带的选项。 */
export type CallExtras = {
  /** 幂等键：重试同一次尝试时传入同一个。不传就新生成一个（只有写请求带）。 */
  key?: string
  /** 401 怎么办：默认整页去登录；自动保存要自己提示「登录已失效」（12 号 6.7）。 */
  unauthorized?: "redirect" | "throw"
  signal?: AbortSignal
}

export type CallOptions = CallExtras & {
  body?: unknown
  params?: Record<string, string | number>
  query?: Record<string, string | number | boolean | null | undefined>
}

/** createClient 造出来的发请求函数；生成的接口函数第一个参数就是它。 */
export type Requester = <T>(method: string, path: string, options?: CallOptions) => Promise<T>

export type ClientDeps = {
  fetch?: typeof fetch
  /** 服务端渲染时是 Go 的内网地址；浏览器里是空串（同源）。 */
  base?: string
  /** 超时（毫秒）；服务端渲染给 5 秒（12 号 6.2 第 4 步），浏览器里不设。 */
  timeoutMs?: number
  location?: () => string
  assign?: (url: string) => void
  onWrite?: () => void
  newKey?: () => string
}

const WRITE = new Set(["POST", "PUT", "PATCH", "DELETE"])

type Payload = {
  error?: { code?: string; message?: string }
  fields?: Record<string, string[]>
  current?: unknown
  letters?: { batch?: string }
}

/** 把 `{id}` 换成参数、拼上查询串。空值（undefined、null、空串）不发，和 Go 的绑定一致。 */
export function buildURL(path: string, options: Pick<CallOptions, "params" | "query"> = {}): string {
  let url = path
  for (const [name, value] of Object.entries(options.params ?? {})) {
    url = url.split("{" + name + "}").join(encodeURIComponent(String(value)))
  }
  const search = new URLSearchParams()
  for (const [name, value] of Object.entries(options.query ?? {})) {
    if (value === undefined || value === null || value === "") continue
    search.append(name, String(value))
  }
  const qs = search.toString()
  return qs ? url + "?" + qs : url
}

export function createClient(deps: ClientDeps = {}): Requester {
  const fetchImpl = deps.fetch ?? fetch
  const base = deps.base ?? ""
  const locate = deps.location ?? (() =>
    typeof location === "undefined" ? "/" : location.pathname + location.search)
  const assign = deps.assign ?? ((url: string) => {
    if (typeof location !== "undefined") location.assign(url)
  })
  const newKey = deps.newKey ?? (() => crypto.randomUUID())

  return async function request<T>(method: string, path: string, options: CallOptions = {}): Promise<T> {
    const headers = new Headers()
    if (options.body !== undefined) headers.set("content-type", "application/json")
    if (WRITE.has(method)) headers.set("Idempotency-Key", options.key ?? newKey())
    let signal = options.signal
    if (deps.timeoutMs !== undefined) {
      const timeout = AbortSignal.timeout(deps.timeoutMs)
      signal = signal ? AbortSignal.any([signal, timeout]) : timeout
    }
    let response: Response
    try {
      response = await fetchImpl(base + buildURL(path, options), {
        method,
        headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
        signal,
      })
    } catch (err) {
      if (options.signal?.aborted) throw err
      const timedOut = err instanceof DOMException && err.name === "TimeoutError"
      throw new ApiError(0, timedOut ? "timeout" : "network", timedOut ? "网站响应太慢" : "网络连不上")
    }
    const text = await response.text()
    let payload: Payload | null = null
    if (text) {
      try {
        payload = JSON.parse(text) as Payload
      } catch {
        payload = null
      }
    }
    if (response.status === 401) {
      if (options.unauthorized !== "throw") {
        assign("/accounts/login/?next=" + encodeURIComponent(locate()))
      }
      throw new ApiError(401, "unauthorized", payload?.error?.message || "登录已失效")
    }
    if (!response.ok) {
      const err = new ApiError(response.status, payload?.error?.code ?? "", payload?.error?.message ?? "")
      err.fields = payload?.fields
      err.current = payload?.current
      throw err
    }
    const batch = payload?.letters?.batch
    if (batch) {
      const here = locate()
      const letters = here.startsWith("/admin/") ? "/admin/letters/" : "/letters/"
      assign(letters + encodeURIComponent(batch) + "/?back=" + encodeURIComponent(here))
    }
    if (WRITE.has(method)) deps.onWrite?.()
    return (payload ?? {}) as T
  }
}
