import { inject, type InjectionKey } from "vue"

// Who is looking at the page, from GET /api/session (12-architecture 3.3):
// the SSR paints the account area straight from this, no state.js. `admin`
// is runs_admin (core templatetags ow.py): the account menu links to the
// back office only for people with a job there. Callers provide it on the
// app instance (app.provide(VIEWER, viewer)); pages read useViewer().
export type ViewerUser = { nickname: string; admin: boolean }
export type Viewer = { user: ViewerUser | null }

export const VIEWER: InjectionKey<Viewer> = Symbol("viewer")

export function useViewer(): Viewer {
  return inject(VIEWER, { user: null })
}
