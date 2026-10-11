import { syncFontCSS } from "@sjtu-ow/shared/font-css"
import { computed, inject, shallowRef, type InjectionKey, type Ref } from "vue"
import { getApiSession, type GetApiSessionOut, type Requester } from "@sjtu-ow/api"
import { getAdminNavigation, type AdminSection } from "./api"

export type AdminUser = NonNullable<GetApiSessionOut["user"]>
export type AdminSession = {
  user: Ref<AdminUser | null>
  nav: Ref<AdminSection[]>
  ready: Ref<boolean>
  message: Ref<string>
  refresh: () => Promise<void>
  can: (capability: string) => boolean
}

export const ADMIN_SESSION: InjectionKey<AdminSession> = Symbol("admin-session")

export function createAdminSession(api: Requester): AdminSession {
  const user = shallowRef<AdminUser | null>(null)
  const nav = shallowRef<AdminSection[]>([])
  const ready = shallowRef(false)
  const message = shallowRef("")
  let generation = 0

  async function refresh(): Promise<void> {
    const current = ++generation
    const result = await getApiSession(api, { refresh: ready.value }, { unauthorized: "throw" })
    if (current !== generation) return
    syncFontCSS((result as typeof result & {font_css_path?:string}).font_css_path)
 user.value = result.user
    message.value = result.flash ?? ""
    const enters = result.user && (result.user.superuser || result.user.caps.includes("admin.enter"))
    if (enters) {
      const navigation = await getAdminNavigation(api, { unauthorized: "throw" })
      if (current !== generation) return
      nav.value = navigation.sections
    } else nav.value = []
    ready.value = true
  }

  function can(capability: string): boolean {
    return Boolean(user.value && (user.value.superuser || user.value.caps.includes(capability)))
  }

  return { user, nav, ready, message, refresh, can }
}

export function useAdminSession(): AdminSession {
  const session = inject(ADMIN_SESSION, null)
  if (!session) throw new Error("Admin session was not provided")
  return session
}

export function useAdminCapability(capability: string) {
  const session = useAdminSession()
  return computed(() => session.can(capability))
}
