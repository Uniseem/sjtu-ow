// 生成物在 ./gen。调用走 client.ts（401、待发信、幂等键）：生成的函数第一个参数是 Requester。
export * from "./gen/index.ts";
export { nav } from "./gen/nav.ts";
export { ApiError, buildURL, createClient } from "./client.ts";
export type { CallExtras, CallOptions, ClientDeps, Requester } from "./client.ts";
export { IMAGE_SPECS } from "./gen/specs.ts";
export type { ImageSpec } from "./gen/specs.ts";
