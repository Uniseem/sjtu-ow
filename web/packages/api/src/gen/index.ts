// 由 sjtuow apigen 生成。不要手改。

export interface GetApiSessionIn {
}

export interface GetApiSessionOut {
  user: {   id: number;   nickname: string;   email: string;   admin: boolean;   email_verified: boolean;   is_sjtu: boolean; } | null;
}

export function getApiSession(): Promise<GetApiSessionOut> {
  return call<GetApiSessionOut>("GET", "/api/session", {  }, undefined)
}

export interface PostApiAuthLoginIn {
  email: string;
  password: string;
}

export interface PostApiAuthLoginOut {
  result: string;
  message: string;
}

export function postApiAuthLogin(body: PostApiAuthLoginIn): Promise<PostApiAuthLoginOut> {
  return call<PostApiAuthLoginOut>("POST", "/api/auth/login", {  }, body)
}

export interface PostApiAuthRegisterIn {
  email: string;
  nickname: string;
  password: string;
  confirm_password: string;
  is_sjtu: boolean | null;
  agree_terms: boolean;
  agree_cross_border: boolean;
}

export interface PostApiAuthRegisterOut {
  email: string;
  message: string;
}

export function postApiAuthRegister(body: PostApiAuthRegisterIn): Promise<PostApiAuthRegisterOut> {
  return call<PostApiAuthRegisterOut>("POST", "/api/auth/register", {  }, body)
}

export interface PostApiAuthResendCodeIn {
  email: string;
}

export interface PostApiAuthResendCodeOut {
  email: string;
  message: string;
}

export function postApiAuthResendCode(body: PostApiAuthResendCodeIn): Promise<PostApiAuthResendCodeOut> {
  return call<PostApiAuthResendCodeOut>("POST", "/api/auth/resend-code", {  }, body)
}

export interface PostApiAuthVerifyEmailIn {
  email: string;
  code: string;
}

export interface PostApiAuthVerifyEmailOut {
  result: string;
  message: string;
}

export function postApiAuthVerifyEmail(body: PostApiAuthVerifyEmailIn): Promise<PostApiAuthVerifyEmailOut> {
  return call<PostApiAuthVerifyEmailOut>("POST", "/api/auth/verify-email", {  }, body)
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
