import type { Requester } from "@sjtu-ow/api"
import { inject, type InjectionKey } from "vue"

// The one way pages talk to Go (frontend-migration A3): the Requester made
// by createClient, provided on the app — the forwarding one with the Go
// base address in SSR (entry-server), the same-origin one in the browser
// (entry-client). Generated functions take it as their first argument:
//   const api = useApi(); await getApiTeamsId(api, id)
// Loaders get the same thing as ctx.api.
export const API: InjectionKey<Requester> = Symbol("api")

export function useApi(): Requester {
  const api = inject(API, null)
  if (!api) throw new Error("useApi() outside an app that provides API")
  return api
}
