// 12 号文档 6.4：错误转换、401 跳登录、待发信跳确认页、写请求带幂等键。

export class ApiError extends Error {
  status: number
  code: string
  fields?: Record<string, string[]>
  current?: unknown

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export type CallOptions = {
  body?: unknown
  params?: Record<string, string>
  /** 重试时传入同一次尝试的键。不传就新生成一个。 */
  key?: string
}

export type ClientDeps = {
  fetch?: typeof fetch
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

export function createClient(deps: ClientDeps = {}) {
  const fetchImpl = deps.fetch ?? fetch
  const locate = deps.location ?? (() =>
    typeof location === "undefined" ? "/" : location.pathname + location.search)
  const assign = deps.assign ?? ((url: string) => {
    if (typeof location !== "undefined") location.assign(url)
  })
  const newKey = deps.newKey ?? (() => crypto.randomUUID())

  return async function request<T>(method: string, path: string, options: CallOptions = {}): Promise<T> {
    let url = path
    for (const [name, value] of Object.entries(options.params ?? {})) {
      url = url.split("{" + name + "}").join(encodeURIComponent(value))
    }
    const headers = new Headers()
    if (options.body !== undefined) headers.set("content-type", "application/json")
    if (WRITE.has(method)) headers.set("Idempotency-Key", options.key ?? newKey())
    const response = await fetchImpl(url, {
      method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })
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
      assign("/accounts/login/?next=" + encodeURIComponent(locate()))
      throw new ApiError(401, "unauthorized", "登录已失效")
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
      const base = here.startsWith("/admin/") ? "/admin/letters/" : "/letters/"
      assign(base + encodeURIComponent(batch) + "/?back=" + encodeURIComponent(here))
    }
    if (WRITE.has(method)) deps.onWrite?.()
    return (payload ?? {}) as T
  }
}
