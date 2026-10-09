// 由 sjtuow apigen 生成。不要手改。

export interface DeleteApiAdminCategoriesIdIn {
}

export interface DeleteApiAdminCategoriesIdOut {
  result: string;
}

export function deleteApiAdminCategoriesId(id: string): Promise<DeleteApiAdminCategoriesIdOut> {
  return call<DeleteApiAdminCategoriesIdOut>("DELETE", "/api/admin/categories/{id}", { id }, undefined)
}

export interface DeleteApiArticlesIdIn {
}

export interface DeleteApiArticlesIdOut {
  result: string;
}

export function deleteApiArticlesId(id: string): Promise<DeleteApiArticlesIdOut> {
  return call<DeleteApiArticlesIdOut>("DELETE", "/api/articles/{id}", { id }, undefined)
}

export interface DeleteApiCommentsIdIn {
}

export interface DeleteApiCommentsIdOut {
  result: string;
}

export function deleteApiCommentsId(id: string): Promise<DeleteApiCommentsIdOut> {
  return call<DeleteApiCommentsIdOut>("DELETE", "/api/comments/{id}", { id }, undefined)
}

export interface DeleteApiImagesIdIn {
}

export interface DeleteApiImagesIdOut {
  result: string;
}

export function deleteApiImagesId(id: string): Promise<DeleteApiImagesIdOut> {
  return call<DeleteApiImagesIdOut>("DELETE", "/api/images/{id}", { id }, undefined)
}

export interface DeleteApiMeContactsIdIn {
}

export interface DeleteApiMeContactsIdOut {
  result: string;
  message: string;
}

export function deleteApiMeContactsId(id: string): Promise<DeleteApiMeContactsIdOut> {
  return call<DeleteApiMeContactsIdOut>("DELETE", "/api/me/contacts/{id}", { id }, undefined)
}

export interface DeleteApiMeGameAccountsIdIn {
}

export interface DeleteApiMeGameAccountsIdOut {
  result: string;
  message: string;
}

export function deleteApiMeGameAccountsId(id: string): Promise<DeleteApiMeGameAccountsIdOut> {
  return call<DeleteApiMeGameAccountsIdOut>("DELETE", "/api/me/game-accounts/{id}", { id }, undefined)
}

export interface GetApiAdminArticlesIn {
}

export interface GetApiAdminArticlesOut {
  total: number;
  page: number;
  page_size: number;
  items: {   Page: {   id: number;   kind: string;   slug: string;   title: string;   live: boolean;   has_unpublished_changes: boolean;   go_live_at?: string | null;   expire_at?: string | null;   first_published_at?: string | null;   last_published_at?: string | null;   live_revision_id?: number | null;   latest_revision_id?: number | null;   owner_id?: number | null;   seo_title: string;   search_description: string;   version: number;   created_at: string;   updated_at: string; };   category_id?: number | null;   category_name?: string;   cover_image_id?: number | null;   summary: string;   body_md: string;   body_html: string;   body_plain: string;   char_count: number;   reading_time: number;   author_id?: number | null;   author_name?: string;   comments_enabled: boolean;   related_tournament_id?: number | null;   search_text: string;   renderer_version: number; } | null[];
}

export function getApiAdminArticles(): Promise<GetApiAdminArticlesOut> {
  return call<GetApiAdminArticlesOut>("GET", "/api/admin/articles", {  }, undefined)
}

export interface GetApiAdminArticlesIdIn {
}

export interface GetApiAdminArticlesIdOut {
  article: {   Page: {   id: number;   kind: string;   slug: string;   title: string;   live: boolean;   has_unpublished_changes: boolean;   go_live_at?: string | null;   expire_at?: string | null;   first_published_at?: string | null;   last_published_at?: string | null;   live_revision_id?: number | null;   latest_revision_id?: number | null;   owner_id?: number | null;   seo_title: string;   search_description: string;   version: number;   created_at: string;   updated_at: string; };   category_id?: number | null;   category_name?: string;   cover_image_id?: number | null;   summary: string;   body_md: string;   body_html: string;   body_plain: string;   char_count: number;   reading_time: number;   author_id?: number | null;   author_name?: string;   comments_enabled: boolean;   related_tournament_id?: number | null;   search_text: string;   renderer_version: number; } | null;
  revision?: {   title: string;   slug: string;   category_id: number | null;   cover_image_id: number | null;   summary: string;   body_md: string;   author_id: number | null;   comments_enabled: boolean;   related_tournament_id: number | null;   seo_title: string;   search_description: string;   go_live_at: string | null;   expire_at: string | null; } | null;
  version: number;
}

export function getApiAdminArticlesId(id: string): Promise<GetApiAdminArticlesIdOut> {
  return call<GetApiAdminArticlesIdOut>("GET", "/api/admin/articles/{id}", { id }, undefined)
}

export interface GetApiAdminCategoriesIn {
}

export interface GetApiAdminCategoriesOut {
  items: {   id: number;   name: string;   slug: string;   description: string;   sort_order: number;   allow_submission: boolean;   version: number;   created_at: string;   updated_at: string;   article_count?: number; } | null[];
}

export function getApiAdminCategories(): Promise<GetApiAdminCategoriesOut> {
  return call<GetApiAdminCategoriesOut>("GET", "/api/admin/categories", {  }, undefined)
}

export interface GetApiAdminFeatureRoleRestrictionsIn {
}

export interface GetApiAdminFeatureRoleRestrictionsOut {
  restrictions: {   role: string;   feature: string; }[];
}

export function getApiAdminFeatureRoleRestrictions(): Promise<GetApiAdminFeatureRoleRestrictionsOut> {
  return call<GetApiAdminFeatureRoleRestrictionsOut>("GET", "/api/admin/feature-role-restrictions", {  }, undefined)
}

export interface GetApiAdminHomePinsIn {
}

export interface GetApiAdminHomePinsOut {
  items: {   id: number;   slug: string;   title: string;   category_name: string;   cover_image_id?: number | null;   summary: string;   reading_time: number;   author_name: string;   first_published_at?: string | null; } | null[];
}

export function getApiAdminHomePins(): Promise<GetApiAdminHomePinsOut> {
  return call<GetApiAdminHomePinsOut>("GET", "/api/admin/home-pins", {  }, undefined)
}

export interface GetApiAdminUsersIn {
}

export interface GetApiAdminUsersOut {
  total: number;
  users: {   id: number;   email: string;   nickname: string;   is_sjtu: boolean;   is_active: boolean;   is_superuser: boolean;   email_verified: boolean;   deactivation_note: string;   created_at: string; }[];
}

export function getApiAdminUsers(): Promise<GetApiAdminUsersOut> {
  return call<GetApiAdminUsersOut>("GET", "/api/admin/users", {  }, undefined)
}

export interface GetApiAdminUsersIdIn {
}

export interface GetApiAdminUsersIdOut {
  user: {   ID: number;   Email: string;   EmailNorm: string;   PasswordHash: string;   Nickname: string;   IsSJTU: boolean;   AgreedTermsAt: string;   AgreedCrossBorderAt: string;   EmailVerifiedAt: string | null;   PasswordChangedAt: string | null;   Version: number;   IsActive: boolean;   IsSuperuser: boolean;   DeactivationNote: string;   Motto: string;   MainRole: string;   FlexRoles: string;   ShowRank: boolean;   CreatedAt: string;   UpdatedAt: string; } | null;
  roles: string[];
  rules: Record<string, boolean>;
  game_accounts: {   id: number;   battletag: string;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   tank_label: string;   damage_label: string;   support_label: string;   ranks_updated_at: string; }[];
  contacts: {   id: number;   type: string;   type_label: string;   value: string;   created_at: string; }[];
}

export function getApiAdminUsersId(id: string): Promise<GetApiAdminUsersIdOut> {
  return call<GetApiAdminUsersIdOut>("GET", "/api/admin/users/{id}", { id }, undefined)
}

export interface GetApiArticlesIdCommentsIn {
}

export interface GetApiArticlesIdCommentsOut {
  total: number;
  page: number;
  page_size: number;
  comments: {   id: number;   article_id: number;   user_id?: number | null;   author_name: string;   parent_id?: number | null;   reply_to_user_id?: number | null;   reply_to_user_name?: string;   content: string;   is_pinned: boolean;   is_hidden: boolean;   is_deleted: boolean;   is_tombstone?: boolean;   like_count: number;   liked_by_me?: boolean;   reply_count?: number;   replies?: any | null[];   version: number;   created_at: string;   updated_at: string; } | null[];
}

export function getApiArticlesIdComments(id: string): Promise<GetApiArticlesIdCommentsOut> {
  return call<GetApiArticlesIdCommentsOut>("GET", "/api/articles/{id}/comments", { id }, undefined)
}

export interface GetApiHomePinsIn {
}

export interface GetApiHomePinsOut {
  items: {   id: number;   slug: string;   title: string;   category_name: string;   cover_image_id?: number | null;   summary: string;   reading_time: number;   author_name: string;   first_published_at?: string | null; } | null[];
}

export function getApiHomePins(): Promise<GetApiHomePinsOut> {
  return call<GetApiHomePinsOut>("GET", "/api/home-pins", {  }, undefined)
}

export interface GetApiImagesIdIn {
}

export interface GetApiImagesIdOut {
  id: number;
  collection_id: number | null;
  title: string;
  file_name: string;
  file_size: number;
  width: number;
  height: number;
  uploader_id: number | null;
  created_at: string;
  version: number;
}

export function getApiImagesId(id: string): Promise<GetApiImagesIdOut> {
  return call<GetApiImagesIdOut>("GET", "/api/images/{id}", { id }, undefined)
}

export interface GetApiMeExportIn {
}

export interface GetApiMeExportOut {
  user: {   ID: number;   Email: string;   EmailNorm: string;   PasswordHash: string;   Nickname: string;   IsSJTU: boolean;   AgreedTermsAt: string;   AgreedCrossBorderAt: string;   EmailVerifiedAt: string | null;   PasswordChangedAt: string | null;   Version: number;   IsActive: boolean;   IsSuperuser: boolean;   DeactivationNote: string;   Motto: string;   MainRole: string;   FlexRoles: string;   ShowRank: boolean;   CreatedAt: string;   UpdatedAt: string; } | null;
  game_accounts: {   id: number;   battletag: string;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   tank_label: string;   damage_label: string;   support_label: string;   ranks_updated_at: string; }[];
  contacts: {   id: number;   type: string;   type_label: string;   value: string;   created_at: string; }[];
  roles: string[];
  exported_at: string;
}

export function getApiMeExport(): Promise<GetApiMeExportOut> {
  return call<GetApiMeExportOut>("GET", "/api/me/export", {  }, undefined)
}

export interface GetApiMeProfileIn {
}

export interface GetApiMeProfileOut {
  id: number;
  nickname: string;
  email: string;
  is_sjtu: boolean;
  motto: string;
  main_role: string;
  flex_roles: string;
  show_rank: boolean;
  is_complete: boolean;
  public_ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };
  game_accounts: {   id: number;   battletag: string;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   tank_label: string;   damage_label: string;   support_label: string;   ranks_updated_at: string; }[];
  contacts: {   id: number;   type: string;   type_label: string;   value: string;   created_at: string; }[];
}

export function getApiMeProfile(): Promise<GetApiMeProfileOut> {
  return call<GetApiMeProfileOut>("GET", "/api/me/profile", {  }, undefined)
}

export interface GetApiMediaRIdSpecIn {
}

export interface GetApiMediaRIdSpecOut {
  url: string;
}

export function getApiMediaRIdSpec(id: string, spec: string): Promise<GetApiMediaRIdSpecOut> {
  return call<GetApiMediaRIdSpecOut>("GET", "/api/media/r/{id}/{spec}", { id, spec }, undefined)
}

export interface GetApiPageNewsIn {
}

export interface GetApiPageNewsOut {
  total: number;
  page: number;
  page_size: number;
  items: {   id: number;   slug: string;   title: string;   category_name: string;   cover_image_id?: number | null;   summary: string;   reading_time: number;   author_name: string;   first_published_at?: string | null; } | null[];
}

export function getApiPageNews(): Promise<GetApiPageNewsOut> {
  return call<GetApiPageNewsOut>("GET", "/api/page/news", {  }, undefined)
}

export interface GetApiPageNewsSlugIn {
}

export interface GetApiPageNewsSlugOut {
  id: number;
  slug: string;
  title: string;
  category_name: string;
  cover_image_id?: number | null;
  summary: string;
  body_html: string;
  char_count: number;
  reading_time: number;
  author_name: string;
  comments_enabled: boolean;
  related_tournament_id?: number | null;
  first_published_at?: string | null;
  headings: {   level: number;   text: string;   id: string; } | null[];
}

export function getApiPageNewsSlug(slug: string): Promise<GetApiPageNewsSlugOut> {
  return call<GetApiPageNewsSlugOut>("GET", "/api/page/news/{slug}", { slug }, undefined)
}

export interface GetApiPageSlugIn {
}

export interface GetApiPageSlugOut {
  slug: string;
  title: string;
  body_html: string;
}

export function getApiPageSlug(slug: string): Promise<GetApiPageSlugOut> {
  return call<GetApiPageSlugOut>("GET", "/api/page/{slug}", { slug }, undefined)
}

export interface GetApiSearchIn {
}

export interface GetApiSearchOut {
  query: string;
  articles: {   id: number;   slug: string;   title: string;   summary: string;   category_name: string;   first_published_at?: string | null; } | null[];
  teams: {   id: number;   name: string;   bio: string; } | null[];
  tournaments: {   id: number;   title: string;   summary: string; } | null[];
  scrims: {   id: number;   title: string; } | null[];
}

export function getApiSearch(): Promise<GetApiSearchOut> {
  return call<GetApiSearchOut>("GET", "/api/search", {  }, undefined)
}

export interface GetApiSessionIn {
}

export interface GetApiSessionOut {
  user: {   id: number;   nickname: string;   email: string;   admin: boolean;   email_verified: boolean;   is_sjtu: boolean; } | null;
}

export function getApiSession(): Promise<GetApiSessionOut> {
  return call<GetApiSessionOut>("GET", "/api/session", {  }, undefined)
}

export interface PatchApiAdminCategoriesIdIn {
  name: string;
  slug: string;
  description: string;
  sort_order: number;
  allow_submission: boolean;
  version: number;
}

export interface PatchApiAdminCategoriesIdOut {
  category: {   id: number;   name: string;   slug: string;   description: string;   sort_order: number;   allow_submission: boolean;   version: number;   created_at: string;   updated_at: string;   article_count?: number; } | null;
}

export function patchApiAdminCategoriesId(id: string, body: PatchApiAdminCategoriesIdIn): Promise<PatchApiAdminCategoriesIdOut> {
  return call<PatchApiAdminCategoriesIdOut>("PATCH", "/api/admin/categories/{id}", { id }, body)
}

export interface PatchApiAdminUsersIdRolesIn {
  roles: string[];
}

export interface PatchApiAdminUsersIdRolesOut {
  result: string;
  roles: string[];
  message: string;
}

export function patchApiAdminUsersIdRoles(id: string, body: PatchApiAdminUsersIdRolesIn): Promise<PatchApiAdminUsersIdRolesOut> {
  return call<PatchApiAdminUsersIdRolesOut>("PATCH", "/api/admin/users/{id}/roles", { id }, body)
}

export interface PatchApiAdminUsersIdRulesIn {
  rules: Record<string, boolean>;
}

export interface PatchApiAdminUsersIdRulesOut {
  result: string;
  message: string;
}

export function patchApiAdminUsersIdRules(id: string, body: PatchApiAdminUsersIdRulesIn): Promise<PatchApiAdminUsersIdRulesOut> {
  return call<PatchApiAdminUsersIdRulesOut>("PATCH", "/api/admin/users/{id}/rules", { id }, body)
}

export interface PatchApiArticlesIdIn {
  base_version: number;
  changes: Record<string, unknown>;
}

export interface PatchApiArticlesIdOut {
  version: number;
  saved: string[];
  fields?: Record<string, string[]>;
  values?: Record<string, unknown>;
  saved_at: string;
}

export function patchApiArticlesId(id: string, body: PatchApiArticlesIdIn): Promise<PatchApiArticlesIdOut> {
  return call<PatchApiArticlesIdOut>("PATCH", "/api/articles/{id}", { id }, body)
}

export interface PatchApiCommentsIdIn {
  content: string;
}

export interface PatchApiCommentsIdOut {
  comment: {   id: number;   article_id: number;   user_id?: number | null;   author_name: string;   parent_id?: number | null;   reply_to_user_id?: number | null;   reply_to_user_name?: string;   content: string;   is_pinned: boolean;   is_hidden: boolean;   is_deleted: boolean;   is_tombstone?: boolean;   like_count: number;   liked_by_me?: boolean;   reply_count?: number;   replies?: any | null[];   version: number;   created_at: string;   updated_at: string; } | null;
}

export function patchApiCommentsId(id: string, body: PatchApiCommentsIdIn): Promise<PatchApiCommentsIdOut> {
  return call<PatchApiCommentsIdOut>("PATCH", "/api/comments/{id}", { id }, body)
}

export interface PatchApiMeGameAccountsIdIn {
  rank_tank: number | null;
  rank_damage: number | null;
  rank_support: number | null;
}

export interface PatchApiMeGameAccountsIdOut {
  id: number;
  battletag: string;
  rank_tank: number | null;
  rank_damage: number | null;
  rank_support: number | null;
  tank_label: string;
  damage_label: string;
  support_label: string;
  ranks_updated_at: string;
}

export function patchApiMeGameAccountsId(id: string, body: PatchApiMeGameAccountsIdIn): Promise<PatchApiMeGameAccountsIdOut> {
  return call<PatchApiMeGameAccountsIdOut>("PATCH", "/api/me/game-accounts/{id}", { id }, body)
}

export interface PatchApiMeProfileIn {
  nickname: string;
  motto: string;
  main_role: string;
  flex_roles: string;
  show_rank: boolean;
  is_sjtu: boolean | null;
}

export interface PatchApiMeProfileOut {
  result: string;
  message: string;
}

export function patchApiMeProfile(body: PatchApiMeProfileIn): Promise<PatchApiMeProfileOut> {
  return call<PatchApiMeProfileOut>("PATCH", "/api/me/profile", {  }, body)
}

export interface PostApiAdminArticlesIdBroadcastIn {
}

export interface PostApiAdminArticlesIdBroadcastOut {
  broadcast: {   id: number;   article_id: number;   sender_id?: number | null;   recipient_count: number;   created_at: string; } | null;
}

export function postApiAdminArticlesIdBroadcast(id: string): Promise<PostApiAdminArticlesIdBroadcastOut> {
  return call<PostApiAdminArticlesIdBroadcastOut>("POST", "/api/admin/articles/{id}/broadcast", { id }, undefined)
}

export interface PostApiAdminCategoriesIn {
  name: string;
  slug: string;
  description: string;
  sort_order: number;
  allow_submission: boolean;
}

export interface PostApiAdminCategoriesOut {
  category: {   id: number;   name: string;   slug: string;   description: string;   sort_order: number;   allow_submission: boolean;   version: number;   created_at: string;   updated_at: string;   article_count?: number; } | null;
}

export function postApiAdminCategories(body: PostApiAdminCategoriesIn): Promise<PostApiAdminCategoriesOut> {
  return call<PostApiAdminCategoriesOut>("POST", "/api/admin/categories", {  }, body)
}

export interface PostApiAdminUsersIdActivateIn {
}

export interface PostApiAdminUsersIdActivateOut {
  result: string;
  message: string;
}

export function postApiAdminUsersIdActivate(id: string): Promise<PostApiAdminUsersIdActivateOut> {
  return call<PostApiAdminUsersIdActivateOut>("POST", "/api/admin/users/{id}/activate", { id }, undefined)
}

export interface PostApiAdminUsersIdDeactivateIn {
  reason: string;
}

export interface PostApiAdminUsersIdDeactivateOut {
  result: string;
  message: string;
}

export function postApiAdminUsersIdDeactivate(id: string, body: PostApiAdminUsersIdDeactivateIn): Promise<PostApiAdminUsersIdDeactivateOut> {
  return call<PostApiAdminUsersIdDeactivateOut>("POST", "/api/admin/users/{id}/deactivate", { id }, body)
}

export interface PostApiArticlesIn {
  title: string;
  category_id: number | null;
  summary: string;
  body_md: string;
}

export interface PostApiArticlesOut {
  id: number;
  location: string;
  version: number;
}

export function postApiArticles(body: PostApiArticlesIn): Promise<PostApiArticlesOut> {
  return call<PostApiArticlesOut>("POST", "/api/articles", {  }, body)
}

export interface PostApiArticlesIdCommentsIn {
  parent_id?: number | null;
  content: string;
}

export interface PostApiArticlesIdCommentsOut {
  comment: {   id: number;   article_id: number;   user_id?: number | null;   author_name: string;   parent_id?: number | null;   reply_to_user_id?: number | null;   reply_to_user_name?: string;   content: string;   is_pinned: boolean;   is_hidden: boolean;   is_deleted: boolean;   is_tombstone?: boolean;   like_count: number;   liked_by_me?: boolean;   reply_count?: number;   replies?: any | null[];   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiArticlesIdComments(id: string, body: PostApiArticlesIdCommentsIn): Promise<PostApiArticlesIdCommentsOut> {
  return call<PostApiArticlesIdCommentsOut>("POST", "/api/articles/{id}/comments", { id }, body)
}

export interface PostApiArticlesIdPublishIn {
  base_version: number;
}

export interface PostApiArticlesIdPublishOut {
  article: {   Page: {   id: number;   kind: string;   slug: string;   title: string;   live: boolean;   has_unpublished_changes: boolean;   go_live_at?: string | null;   expire_at?: string | null;   first_published_at?: string | null;   last_published_at?: string | null;   live_revision_id?: number | null;   latest_revision_id?: number | null;   owner_id?: number | null;   seo_title: string;   search_description: string;   version: number;   created_at: string;   updated_at: string; };   category_id?: number | null;   category_name?: string;   cover_image_id?: number | null;   summary: string;   body_md: string;   body_html: string;   body_plain: string;   char_count: number;   reading_time: number;   author_id?: number | null;   author_name?: string;   comments_enabled: boolean;   related_tournament_id?: number | null;   search_text: string;   renderer_version: number; } | null;
}

export function postApiArticlesIdPublish(id: string, body: PostApiArticlesIdPublishIn): Promise<PostApiArticlesIdPublishOut> {
  return call<PostApiArticlesIdPublishOut>("POST", "/api/articles/{id}/publish", { id }, body)
}

export interface PostApiArticlesIdUnpublishIn {
}

export interface PostApiArticlesIdUnpublishOut {
  result: string;
}

export function postApiArticlesIdUnpublish(id: string): Promise<PostApiArticlesIdUnpublishOut> {
  return call<PostApiArticlesIdUnpublishOut>("POST", "/api/articles/{id}/unpublish", { id }, undefined)
}

export interface PostApiAuthChangePasswordIn {
  old_password: string;
  password: string;
  confirm_password: string;
}

export interface PostApiAuthChangePasswordOut {
  result: string;
  message: string;
}

export function postApiAuthChangePassword(body: PostApiAuthChangePasswordIn): Promise<PostApiAuthChangePasswordOut> {
  return call<PostApiAuthChangePasswordOut>("POST", "/api/auth/change-password", {  }, body)
}

export interface PostApiAuthDeleteAccountIn {
  password: string;
}

export interface PostApiAuthDeleteAccountOut {
  result: string;
  message: string;
}

export function postApiAuthDeleteAccount(body: PostApiAuthDeleteAccountIn): Promise<PostApiAuthDeleteAccountOut> {
  return call<PostApiAuthDeleteAccountOut>("POST", "/api/auth/delete-account", {  }, body)
}

export interface PostApiAuthEmailChangeIn {
  new_email: string;
}

export interface PostApiAuthEmailChangeOut {
  result: string;
  message: string;
}

export function postApiAuthEmailChange(body: PostApiAuthEmailChangeIn): Promise<PostApiAuthEmailChangeOut> {
  return call<PostApiAuthEmailChangeOut>("POST", "/api/auth/email/change", {  }, body)
}

export interface PostApiAuthEmailChangeConfirmIn {
  code: string;
}

export interface PostApiAuthEmailChangeConfirmOut {
  result: string;
  message: string;
}

export function postApiAuthEmailChangeConfirm(body: PostApiAuthEmailChangeConfirmIn): Promise<PostApiAuthEmailChangeConfirmOut> {
  return call<PostApiAuthEmailChangeConfirmOut>("POST", "/api/auth/email/change/confirm", {  }, body)
}

export interface PostApiAuthLoginIn {
  email: string;
  password: string;
}

export interface PostApiAuthLoginOut {
  result: string;
  message: string;
}

export function postApiAuthLogin(body: PostApiAuthLoginIn): Promise<PostApiAuthLoginOut> {
  return call<PostApiAuthLoginOut>("POST", "/api/auth/login", {  }, body)
}

export interface PostApiAuthLogoutIn {
}

export interface PostApiAuthLogoutOut {
  result: string;
  message: string;
}

export function postApiAuthLogout(): Promise<PostApiAuthLogoutOut> {
  return call<PostApiAuthLogoutOut>("POST", "/api/auth/logout", {  }, undefined)
}

export interface PostApiAuthReauthenticateIn {
  password: string;
}

export interface PostApiAuthReauthenticateOut {
  result: string;
  message: string;
}

export function postApiAuthReauthenticate(body: PostApiAuthReauthenticateIn): Promise<PostApiAuthReauthenticateOut> {
  return call<PostApiAuthReauthenticateOut>("POST", "/api/auth/reauthenticate", {  }, body)
}

export interface PostApiAuthRegisterIn {
  email: string;
  nickname: string;
  password: string;
  confirm_password: string;
  is_sjtu: boolean | null;
  agree_terms: boolean;
  agree_cross_border: boolean;
}

export interface PostApiAuthRegisterOut {
  email: string;
  message: string;
}

export function postApiAuthRegister(body: PostApiAuthRegisterIn): Promise<PostApiAuthRegisterOut> {
  return call<PostApiAuthRegisterOut>("POST", "/api/auth/register", {  }, body)
}

export interface PostApiAuthResendCodeIn {
  email: string;
}

export interface PostApiAuthResendCodeOut {
  email: string;
  message: string;
}

export function postApiAuthResendCode(body: PostApiAuthResendCodeIn): Promise<PostApiAuthResendCodeOut> {
  return call<PostApiAuthResendCodeOut>("POST", "/api/auth/resend-code", {  }, body)
}

export interface PostApiAuthResetPasswordIn {
  email: string;
}

export interface PostApiAuthResetPasswordOut {
  email: string;
  message: string;
}

export function postApiAuthResetPassword(body: PostApiAuthResetPasswordIn): Promise<PostApiAuthResetPasswordOut> {
  return call<PostApiAuthResetPasswordOut>("POST", "/api/auth/reset-password", {  }, body)
}

export interface PostApiAuthResetPasswordConfirmIn {
  email: string;
  code: string;
  password: string;
  confirm_password: string;
}

export interface PostApiAuthResetPasswordConfirmOut {
  result: string;
  message: string;
}

export function postApiAuthResetPasswordConfirm(body: PostApiAuthResetPasswordConfirmIn): Promise<PostApiAuthResetPasswordConfirmOut> {
  return call<PostApiAuthResetPasswordConfirmOut>("POST", "/api/auth/reset-password/confirm", {  }, body)
}

export interface PostApiAuthVerifyEmailIn {
  email: string;
  code: string;
}

export interface PostApiAuthVerifyEmailOut {
  result: string;
  message: string;
}

export function postApiAuthVerifyEmail(body: PostApiAuthVerifyEmailIn): Promise<PostApiAuthVerifyEmailOut> {
  return call<PostApiAuthVerifyEmailOut>("POST", "/api/auth/verify-email", {  }, body)
}

export interface PostApiCommentsIdHideIn {
  hidden: boolean;
}

export interface PostApiCommentsIdHideOut {
  result: string;
}

export function postApiCommentsIdHide(id: string, body: PostApiCommentsIdHideIn): Promise<PostApiCommentsIdHideOut> {
  return call<PostApiCommentsIdHideOut>("POST", "/api/comments/{id}/hide", { id }, body)
}

export interface PostApiCommentsIdLikeIn {
}

export interface PostApiCommentsIdLikeOut {
  liked: boolean;
  like_count: number;
}

export function postApiCommentsIdLike(id: string): Promise<PostApiCommentsIdLikeOut> {
  return call<PostApiCommentsIdLikeOut>("POST", "/api/comments/{id}/like", { id }, undefined)
}

export interface PostApiCommentsIdPinIn {
  article_id: number;
  pinned: boolean;
}

export interface PostApiCommentsIdPinOut {
  result: string;
}

export function postApiCommentsIdPin(id: string, body: PostApiCommentsIdPinIn): Promise<PostApiCommentsIdPinOut> {
  return call<PostApiCommentsIdPinOut>("POST", "/api/comments/{id}/pin", { id }, body)
}

export interface PostApiMeContactsIn {
  type: string;
  value: string;
}

export interface PostApiMeContactsOut {
  id: number;
  type: string;
  type_label: string;
  value: string;
  created_at: string;
}

export function postApiMeContacts(body: PostApiMeContactsIn): Promise<PostApiMeContactsOut> {
  return call<PostApiMeContactsOut>("POST", "/api/me/contacts", {  }, body)
}

export interface PostApiMeGameAccountsIn {
  battletag: string;
  rank_tank: number | null;
  rank_damage: number | null;
  rank_support: number | null;
}

export interface PostApiMeGameAccountsOut {
  id: number;
  battletag: string;
  rank_tank: number | null;
  rank_damage: number | null;
  rank_support: number | null;
  tank_label: string;
  damage_label: string;
  support_label: string;
  ranks_updated_at: string;
}

export function postApiMeGameAccounts(body: PostApiMeGameAccountsIn): Promise<PostApiMeGameAccountsOut> {
  return call<PostApiMeGameAccountsOut>("POST", "/api/me/game-accounts", {  }, body)
}

export interface PutApiAdminFeatureRoleRestrictionsIn {
  restrictions: {   role: string;   feature: string; }[];
}

export interface PutApiAdminFeatureRoleRestrictionsOut {
  result: string;
  message: string;
}

export function putApiAdminFeatureRoleRestrictions(body: PutApiAdminFeatureRoleRestrictionsIn): Promise<PutApiAdminFeatureRoleRestrictionsOut> {
  return call<PutApiAdminFeatureRoleRestrictionsOut>("PUT", "/api/admin/feature-role-restrictions", {  }, body)
}

export interface PutApiAdminHomePinsIn {
  article_ids: number[];
}

export interface PutApiAdminHomePinsOut {
  result: string;
}

export function putApiAdminHomePins(body: PutApiAdminHomePinsIn): Promise<PutApiAdminHomePinsOut> {
  return call<PutApiAdminHomePinsOut>("PUT", "/api/admin/home-pins", {  }, body)
}

export async function call<T>(method: string, path: string, params: Record<string, string>, body?: unknown): Promise<T> {
  let url = path
  for (const key of Object.keys(params)) {
    url = url.split("{" + key + "}").join(encodeURIComponent(params[key]))
  }
  const init: RequestInit = { method }
  if (body !== undefined) {
    init.headers = { "content-type": "application/json" }
    init.body = JSON.stringify(body)
  }
  const response = await fetch(url, init)
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return (await response.json()) as T
}
