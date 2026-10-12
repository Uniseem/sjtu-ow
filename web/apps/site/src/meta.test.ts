import { describe, it, expect } from "vitest"
import { pageHead, privateDocument } from "./meta"

const site = { url: "https://site.example", description: "社团简介", default_share_image_id: 19 }
describe("document metadata", () => {
  it("uses configured public origin, discards query/fragment and supplies the share fallback", () => {
    const head = pageHead({ title: "资讯" }, "/news/?page=2#more", site)
    expect(head.link).toEqual([{ rel: "canonical", href: "https://site.example/news/" }])
    expect(head.meta).toContainEqual({ property: "og:url", content: "https://site.example/news/" })
    expect(head.meta).toContainEqual({ property: "og:image", content: "https://site.example/media/r/19/fill-1200x630.webp" })
    expect(head.meta).toContainEqual({ name: "description", content: "社团简介" })
  })
  it("prefers the actual page image and description", () => {
    const head = pageHead({ title: "文章", description: " 正文摘要 ", imageId: 7 }, "/news/article/", site)
    expect(head.meta).toContainEqual({ property: "og:image", content: "https://site.example/media/r/7/fill-1200x630.webp" })
    expect(head.meta).toContainEqual({ property: "og:description", content: "正文摘要" })
  })
  it("marks every private namespace but not similarly named public pages", () => {
    for (const path of ["/me/", "/accounts/signup/", "/letters/batch/", "/admin/articles/", "/unsubscribe/token/"]) {
      expect(privateDocument(path)).toBe(true)
      expect(pageHead({ title: "私有页" }, path, site).meta).toContainEqual({ name: "robots", content: "noindex" })
    }
    for (const path of ["/members/", "/news/", "/about/", "/accounts-policy/"]) {
      expect(privateDocument(path)).toBe(false)
      expect(pageHead({ title: "公开页" }, path, site).meta.some(item => "name" in item && item.name === "robots")).toBe(false)
    }
  })
  it("does not emit a canonical or image with a non-http configured origin", () => {
    const head = pageHead({ title: "资讯" }, "/news/", { ...site, url: "javascript:alert(1)" })
    expect(head.link).toEqual([])
    expect(head.meta.some(item => "property" in item && item.property === "og:image")).toBe(false)
  })
})
