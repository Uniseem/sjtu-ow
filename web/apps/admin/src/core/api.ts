import { inject, type InjectionKey } from "vue"
import type { CallExtras, Requester } from "@sjtu-ow/api"
import { getApiAdminNavigation } from "@sjtu-ow/api"

export const ADMIN_API: InjectionKey<Requester> = Symbol("admin-api")

export function useAdminApi(): Requester {
  const requester = inject(ADMIN_API, null)
  if (!requester) throw new Error("Admin API was not provided")
  return requester
}

export type AdminTab = {
  key: string
  label: string
  url: string
  count: number
  tabs: AdminTab[]
}

export type AdminSection = {
  key: string
  label: string
  url: string
  tabs: AdminTab[]
}

export function getAdminNavigation(api: Requester, extras: CallExtras = {}) {
  return getApiAdminNavigation(api, extras)
}
