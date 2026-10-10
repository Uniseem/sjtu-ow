import type { GetApiSessionOut } from "@sjtu-ow/api"
import { inject, type InjectionKey } from "vue"

// Who is looking at the page: GET /api/session as Go sends it (12-architecture
// 3.3, frontend-migration A6), into SSR and ow-state whole. `admin` is
// runs_admin (the account menu links to the back office only for people with
// a job there); `superuser` and `caps` decide the back office's tabs. Callers
// provide it on the app instance (app.provide(VIEWER, viewer)); pages read
// useViewer().
export type ViewerUser = NonNullable<GetApiSessionOut["user"]>
export type Viewer = { user: ViewerUser | null; flash?: string }

export const VIEWER: InjectionKey<Viewer> = Symbol("viewer")

export function useViewer(): Viewer {
  return inject(VIEWER, { user: null })
}
