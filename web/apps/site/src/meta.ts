import { useHead } from "@unhead/vue"
import { inject } from "vue"
import { useRoute } from "vue-router"
import { imageUrl } from "@sjtu-ow/shared/media"
import { useViewer } from "./viewer"
import type { PageData } from "./router"

// The document title as content/seo.py build_seo() writes it: "页面 · SJTU-OW",
// the site name alone when the page is the site itself (frontend-migration A11).
export const SITE_NAME = "SJTU-OW"

export function documentTitle(title: string | undefined | null): string {
  const text = (title ?? "").trim()
  return !text || text === SITE_NAME ? SITE_NAME : `${text} · ${SITE_NAME}`
}

export type PageMeta = { title: string; description?: string | null; imageId?: number | null }

export function privateDocument(path: string): boolean {
  return /^\/(me|accounts|letters|admin|unsubscribe)(\/|$)/.test(path)
}

export function pageHead(meta: PageMeta, path: string, site?: { url: string; description: string; default_share_image_id: number | null }) {
  const description = meta.description?.trim() || site?.description?.trim()
    || "SJTU-OW：上海交通大学守望先锋玩家的社团网站"
  // SITE_URL is supplied by Go, never inferred from an untrusted Host header.
  let canonical: string | undefined
  try {
    const origin = new URL(site?.url ?? "")
    if (origin.protocol === "https:" || origin.protocol === "http:") {
      canonical = new URL(path.split(/[?#]/)[0], origin).href
    }
  } catch { /* A mock without public settings has no canonical URL. */ }
  const imageId = meta.imageId || site?.default_share_image_id
  const image = canonical && imageId ? new URL(imageUrl(imageId, "fill-1200x630"), canonical).href : undefined
  return {
    title: documentTitle(meta.title),
    link: canonical ? [{ rel: "canonical", href: canonical }] : [],
    meta: [
      { name: "description", content: description },
      { property: "og:title", content: meta.title || SITE_NAME },
      { property: "og:description", content: description },
      { property: "og:site_name", content: SITE_NAME },
      ...(canonical ? [{ property: "og:url", content: canonical }] : []),
      ...(image ? [{ property: "og:image", content: image }] : []),
      ...(privateDocument(path) ? [{ name: "robots", content: "noindex" }] : []),
    ],
  }
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? value as Record<string, unknown> : {}
}

/** Defaults for pages that still declare their precise legacy title themselves. */
export function useDocumentMeta() {
  const route = useRoute()
  const viewer = useViewer()
  const data = inject<PageData>("page-data")
  useHead(() => {
    const page = record(data?.page)
    const subject = record(data?.article ?? data?.team ?? page.tournament ?? page.scrim ?? page)
    const cover = subject.cover_image_id ?? subject.logo_image_id ?? page.default_cover_image_id
    const head = pageHead({
      title: data?.title ?? SITE_NAME,
      description: String(data?.description ?? subject.search_description ?? subject.summary ?? ""),
      imageId: typeof cover === "number" ? cover : undefined,
    }, route.path, viewer.site)
    // Child pages own their established document title, including the event suffix.
    return { link: head.link, meta: head.meta }
  })
}

// One place for a page's <title> and description. Canonical, og:* and the
// site-wide fallback description wait for Go to send the site settings
// (STATUS「交给后端」); until then a page without its own description sends none.
export function usePageMeta(meta: () => PageMeta) {
  const route = useRoute()
  const viewer = useViewer()
  useHead(() => pageHead(meta(), route.path, viewer.site))
}
