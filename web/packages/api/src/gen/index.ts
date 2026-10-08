// 由 sjtuow apigen 生成。不要手改。

export interface GetApiSessionIn {
}

export interface GetApiSessionOut {
  user: {   id: number;   nickname: string;   email: string;   admin: boolean;   email_verified: boolean;   is_sjtu: boolean; } | null;
}

export function getApiSession(): Promise<GetApiSessionOut> {
  return call<GetApiSessionOut>("GET", "/api/session", {  }, undefined)
}

export async function call<T>(method: string, path: string, params: Record<string, string>, body?: unknown): Promise<T> {
  let url = path
  for (const key of Object.keys(params)) {
    url = url.split("{" + key + "}").join(encodeURIComponent(params[key]))
  }
  const init: RequestInit = { method }
  if (body !== undefined) {
    init.headers = { "content-type": "application/json" }
    init.body = JSON.stringify(body)
  }
  const response = await fetch(url, init)
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return (await response.json()) as T
}
