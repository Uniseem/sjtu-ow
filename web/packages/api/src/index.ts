// 生成物在 ./gen。调用走 client.ts（401、待发信、幂等键）。
export * from "./gen/index.ts";
export { nav } from "./gen/nav.ts";
export { ApiError, createClient } from "./client.ts";
export type { CallOptions, ClientDeps } from "./client.ts";
