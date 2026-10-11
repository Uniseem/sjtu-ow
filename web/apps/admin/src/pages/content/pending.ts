// Local consumer names are aliases to the generated Go contracts and calls.
// This file no longer owns endpoint paths or request/response field shapes.
import {
  postApiAdminArticlesIdRevisionsRevisionRestore,
  postApiAdminHomePinsPublish,
  postApiAdminNewsIntroPublish,
  postApiAdminPagesIdPublish,
  type CallExtras,
  type Requester,
  type GetApiAdminArticlesIdOut,
  type GetApiAdminArticlesQuery,
  type GetApiAdminArticlesIdRevisionsOut,
  type GetApiAdminArticlesIdRevisionsRevisionOut,
  type GetApiAdminHomePinsDraftOut,
  type GetApiAdminNewsIntroOut,
  type GetApiAdminImageCollectionsOut,
  type GetApiAdminPagesOut,
  type GetApiAdminPagesIdOut,
  type PatchApiAdminImagesIdIn,
  type PatchApiAdminImagesIdOut,
  type PatchApiAdminImageCollectionsIdIn,
  type PostApiAdminImageCollectionsIn,
  type PostApiAdminMarkdownPreviewIn,
  type PostApiAdminMarkdownPreviewOut,
} from "@sjtu-ow/api"

export {
  getApiAdminArticlesId as readArticleEditor,
  getApiAdminArticlesNew as readNewArticleEditor,
  getApiAdminArticlesIdRevisions as readArticleRevisions,
  getApiAdminArticlesIdRevisionsRevision as readArticleRevision,
  getApiAdminArticles as listContentArticles,
  getApiAdminImageCollections as readCollectionTree,
  getApiAdminPages as readSiteParts,
  getApiAdminPagesId as readPlainPage,
  getApiAdminHomePinsDraft as readHomeDraft,
  getApiAdminNewsIntro as readNewsDraft,
  postApiAdminMarkdownPreview as createMarkdownPreview,
  postApiAdminImageCollections as createCollection,
  patchApiAdminImagesId as saveImage,
  patchApiAdminImageCollectionsId as renameCollection,
  patchApiAdminPagesId as savePlainPage,
  patchApiAdminHomePinsDraft as saveHomeDraft,
  patchApiAdminNewsIntro as saveNewsDraft,
  deleteApiAdminImageCollectionsId as deleteCollection,
} from "@sjtu-ow/api"

export type ArticleCapabilities = GetApiAdminArticlesIdOut["capabilities"]
export type ArticleEditorProjection = GetApiAdminArticlesIdOut
export type ArticleFilters = GetApiAdminArticlesQuery
export type ArticleRevision = GetApiAdminArticlesIdRevisionsOut["items"][number]
export type ArticleRevisionsResult = GetApiAdminArticlesIdRevisionsOut
export type ArticleRevisionDetail = GetApiAdminArticlesIdRevisionsRevisionOut
export type MarkdownPreviewInput = PostApiAdminMarkdownPreviewIn
export type MarkdownPreviewResult = PostApiAdminMarkdownPreviewOut
export type ImageEditValues = PatchApiAdminImagesIdOut["values"]
export type ImageEditInput = PatchApiAdminImagesIdIn
export type ImageEditReceipt = PatchApiAdminImagesIdOut
export type CollectionNode = GetApiAdminImageCollectionsOut["collections"][number]
export type CollectionCreateInput = PostApiAdminImageCollectionsIn
export type CollectionSaveInput = PatchApiAdminImageCollectionsIdIn
export type PlainPageDraft = GetApiAdminPagesIdOut["draft"]
export type PlainPage = GetApiAdminPagesIdOut["page"]
export type PlainPageDetail = GetApiAdminPagesIdOut
export type HomePinsDraft = GetApiAdminHomePinsDraftOut["draft"]
export type NewsIntroDraft = GetApiAdminNewsIntroOut["draft"]
export type SitePartsProjection = GetApiAdminPagesOut
export type HomeDraftProjection = GetApiAdminHomePinsDraftOut
export type NewsDraftProjection = GetApiAdminNewsIntroOut

// Preserve consumers' ergonomic version argument; wire bodies still come from
// the generated function signatures rather than a separate local contract.
export function restoreArticleRevision(api: Requester, id: number, revision: number, baseVersion: number, extras: CallExtras = {}) {
  return postApiAdminArticlesIdRevisionsRevisionRestore(api, id, revision, { base_version: baseVersion }, extras)
}
export function publishPlainPage(api: Requester, id: number, version: number, extras: CallExtras = {}) {
  return postApiAdminPagesIdPublish(api, id, { base_version: version }, extras)
}
export function publishHomeDraft(api: Requester, version: number, extras: CallExtras = {}) {
  return postApiAdminHomePinsPublish(api, { base_version: version }, extras)
}
export function publishNewsDraft(api: Requester, version: number, extras: CallExtras = {}) {
  return postApiAdminNewsIntroPublish(api, { base_version: version }, extras)
}
