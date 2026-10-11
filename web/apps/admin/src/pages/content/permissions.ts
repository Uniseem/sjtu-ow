import { computed } from "vue"
import { useAdminSession } from "../../core/session"
import type { Article } from "./types"

export function useContentPermissions() {
  const { user } = useAdminSession()
  const has = (cap: string): boolean => Boolean(user.value?.superuser || user.value?.caps.includes(cap))
  return {
    user,
    everyArticle: computed(() => has("articles.edit_any")),
    writeArticle: computed(() => Boolean(user.value?.can_submit_article)),
    editAuthor: computed(() => has("articles.edit_author")),
    editSchedule: computed(() => has("articles.edit_any")),
    manageCategories: computed(() => has("article_categories.manage")),
    managePages: computed(() => has("site_pages.manage")),
    superuser: computed(() => Boolean(user.value?.superuser)),
    canEdit: (article: Article) => has("articles.edit_any") || article.owner_id === user.value?.id,
    canPublish: (article: Article) => has("articles.edit_any")
      || has("articles.publish_own") && article.owner_id === user.value?.id,
    canUnpublish: (article: Article) => has("articles.edit_any") && article.live,
  }
}
