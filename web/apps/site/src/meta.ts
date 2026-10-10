import { useHead } from "@unhead/vue"

// The document title as content/seo.py build_seo() writes it: "页面 · SJTU-OW",
// the site name alone when the page is the site itself (frontend-migration A11).
export const SITE_NAME = "SJTU-OW"

export function documentTitle(title: string | undefined | null): string {
  const text = (title ?? "").trim()
  return !text || text === SITE_NAME ? SITE_NAME : `${text} · ${SITE_NAME}`
}

export type PageMeta = { title: string; description?: string | null }

// One place for a page's <title> and description. Canonical, og:* and the
// site-wide fallback description wait for Go to send the site settings
// (STATUS「交给后端」); until then a page without its own description sends none.
export function usePageMeta(meta: () => PageMeta) {
  useHead(() => {
    const { title, description } = meta()
    const text = description?.trim()
    return {
      title: documentTitle(title),
      meta: text ? [{ name: "description", content: text }] : [],
    }
  })
}
