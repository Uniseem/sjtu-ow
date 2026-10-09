// 由 sjtuow apigen 生成。不要手改。

export interface DeleteApiAdminCategoriesIdIn {
}

export interface DeleteApiAdminCategoriesIdOut {
  result: string;
}

export function deleteApiAdminCategoriesId(id: string): Promise<DeleteApiAdminCategoriesIdOut> {
  return call<DeleteApiAdminCategoriesIdOut>("DELETE", "/api/admin/categories/{id}", { id }, undefined)
}

export interface DeleteApiAdminMemberGroupPeopleIdIn {
}

export interface DeleteApiAdminMemberGroupPeopleIdOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function deleteApiAdminMemberGroupPeopleId(id: string): Promise<DeleteApiAdminMemberGroupPeopleIdOut> {
  return call<DeleteApiAdminMemberGroupPeopleIdOut>("DELETE", "/api/admin/member-group-people/{id}", { id }, undefined)
}

export interface DeleteApiAdminMemberGroupsIdIn {
}

export interface DeleteApiAdminMemberGroupsIdOut {
  result: string;
}

export function deleteApiAdminMemberGroupsId(id: string): Promise<DeleteApiAdminMemberGroupsIdOut> {
  return call<DeleteApiAdminMemberGroupsIdOut>("DELETE", "/api/admin/member-groups/{id}", { id }, undefined)
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

export interface GetApiAdminMemberGroupsIn {
}

export interface GetApiAdminMemberGroupsOut {
  groups: {   Group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };   member_count: number; }[];
}

export function getApiAdminMemberGroups(): Promise<GetApiAdminMemberGroupsOut> {
  return call<GetApiAdminMemberGroupsOut>("GET", "/api/admin/member-groups", {  }, undefined)
}

export interface GetApiAdminMemberGroupsIdIn {
}

export interface GetApiAdminMemberGroupsIdOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function getApiAdminMemberGroupsId(id: string): Promise<GetApiAdminMemberGroupsIdOut> {
  return call<GetApiAdminMemberGroupsIdOut>("GET", "/api/admin/member-groups/{id}", { id }, undefined)
}

export interface GetApiAdminMemberGroupsIdPeopleIn {
}

export interface GetApiAdminMemberGroupsIdPeopleOut {
  results: {   user_id: number;   nickname: string;   email?: string; }[];
}

export function getApiAdminMemberGroupsIdPeople(id: string): Promise<GetApiAdminMemberGroupsIdPeopleOut> {
  return call<GetApiAdminMemberGroupsIdPeopleOut>("GET", "/api/admin/member-groups/{id}/people", { id }, undefined)
}

export interface GetApiAdminTeamsIn {
}

export interface GetApiAdminTeamsOut {
  teams: {   id: number;   name: string;   member_count: number;   captain_id: number | null;   captain_name: string;   captain_active: boolean;   no_captain: boolean;   disbanded_at?: string | null;   created_at: string; }[];
}

export function getApiAdminTeams(): Promise<GetApiAdminTeamsOut> {
  return call<GetApiAdminTeamsOut>("GET", "/api/admin/teams", {  }, undefined)
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
  teams: {   team_id: number;   name: string;   role: string;   joined_at: string; }[];
  team_applications: {   id: number;   team_id: number;   team_name: string;   roles: string[];   message: string;   status: string;   created_at: string; }[];
  team_alumni: {   team_id: number;   team_name: string;   role: string;   joined_at: string;   left_at: string;   reason: string; }[];
  member_groups: {   group_id: number;   name: string;   title: string; }[];
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

export interface GetApiMeTeamsIn {
}

export interface GetApiMeTeamsOut {
  teams: {   team_id: number;   name: string;   logo_image_id: number | null;   role: string;   member_count: number;   joined_at: string; }[];
  applications: {   id: number;   team_id: number;   team_name: string;   roles: string[];   status: string;   decision_note: string;   created_at: string;   decided_at?: string | null; }[];
}

export function getApiMeTeams(): Promise<GetApiMeTeamsOut> {
  return call<GetApiMeTeamsOut>("GET", "/api/me/teams", {  }, undefined)
}

export interface GetApiMediaRIdSpecIn {
}

export interface GetApiMediaRIdSpecOut {
  url: string;
}

export function getApiMediaRIdSpec(id: string, spec: string): Promise<GetApiMediaRIdSpecOut> {
  return call<GetApiMediaRIdSpecOut>("GET", "/api/media/r/{id}/{spec}", { id, spec }, undefined)
}

export interface GetApiMembersIn {
}

export interface GetApiMembersOut {
  sections: {   id: number;   name: string;   description: string;   entries: {   titles: string[];   member: {   user_id: number;   number: number;   nickname: string;   motto: string;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   teams: {   id: number;   name: string; }[];   groups: string[];   titles: string[]; }; }[]; }[];
  members: {   user_id: number;   number: number;   nickname: string;   motto: string;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   teams: {   id: number;   name: string; }[];   groups: string[];   titles: string[]; }[];
  total: number;
  role: string;
  free: boolean;
  filtering: boolean;
}

export function getApiMembers(): Promise<GetApiMembersOut> {
  return call<GetApiMembersOut>("GET", "/api/members", {  }, undefined)
}

export interface GetApiMembersIdIn {
}

export interface GetApiMembersIdOut {
  card: {   user_id: number;   number: number;   nickname: string;   motto: string;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   teams: {   id: number;   name: string; }[];   groups: string[];   titles: string[]; };
  groups: {   id: number;   name: string;   titles: string[]; }[];
  teams: {   TeamRef: {   id: number;   name: string; };   member_count: number;   is_captain: boolean; }[];
  alumni: {   team_id: number;   team_name: string;   role: string;   left_at: string;   reason: string; }[];
  articles: {   id: number;   slug: string;   title: string;   first_published_at?: string | null; }[];
  article_count: number;
  is_owner: boolean;
}

export function getApiMembersId(id: string): Promise<GetApiMembersIdOut> {
  return call<GetApiMembersIdOut>("GET", "/api/members/{id}", { id }, undefined)
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
  teams: {   id: number;   name: string;   description: string;   is_recruiting: boolean; } | null[];
  members: {   id: number;   nickname: string;   motto: string; } | null[];
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

export interface GetApiTeamsIn {
}

export interface GetApiTeamsOut {
  teams: {   id: number;   name: string;   description: string;   logo_image_id: number | null;   is_recruiting: boolean;   wanted_roles: string[];   member_count: number;   is_full: boolean; }[];
  team_total: number;
  recruiting_total: number;
  role_counts: Record<string, number>;
  max_members: number;
  recruiting_only: boolean;
  role: string;
}

export function getApiTeams(): Promise<GetApiTeamsOut> {
  return call<GetApiTeamsOut>("GET", "/api/teams", {  }, undefined)
}

export interface GetApiTeamsIdIn {
}

export interface GetApiTeamsIdOut {
  team: {   id: number;   name: string;   description: string;   logo_image_id: number | null;   is_recruiting: boolean;   recruiting_roles: string[];   member_contact?: string;   disbanded_at?: string | null;   version: number;   created_at: string;   updated_at: string; } | null;
  members: {   Person: {   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; }; };   role: string;   joined_at: string; }[];
  alumni: {   id: number;   Person: {   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; }; };   role: string;   joined_at: string;   left_at: string;   reason: string;   can_remove: boolean; }[];
  max_members: number;
  viewer: {   is_member: boolean;   is_captain: boolean;   is_superuser: boolean;   can_apply: boolean;   apply_reason?: string;   needs_game_account: boolean; };
}

export function getApiTeamsId(id: string): Promise<GetApiTeamsIdOut> {
  return call<GetApiTeamsIdOut>("GET", "/api/teams/{id}", { id }, undefined)
}

export interface GetApiTeamsIdManageIn {
}

export interface GetApiTeamsIdManageOut {
  team: {   id: number;   name: string;   description: string;   logo_image_id: number | null;   is_recruiting: boolean;   recruiting_roles: string[];   member_contact?: string;   disbanded_at?: string | null;   version: number;   created_at: string;   updated_at: string; } | null;
  members: {   Person: {   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; }; };   role: string;   joined_at: string; }[];
  alumni: {   id: number;   Person: {   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; }; };   role: string;   joined_at: string;   left_at: string;   reason: string;   can_remove: boolean; }[];
  pending: {   id: number;   applicant: {   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; }; };   roles: string[];   message: string;   created_at: string;   game_ids: string[];   reminded: boolean; }[];
  disband_blockers: string[];
  max_members: number;
}

export function getApiTeamsIdManage(id: string): Promise<GetApiTeamsIdManageOut> {
  return call<GetApiTeamsIdManageOut>("GET", "/api/teams/{id}/manage", { id }, undefined)
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

export interface PatchApiAdminMemberGroupsIdIn {
  base_version: number;
  changes: {   name?: string | null;   description?: string | null;   is_visible?: boolean | null;   sort_order?: number | null; };
}

export interface PatchApiAdminMemberGroupsIdOut {
  version: number;
  saved: string[];
  fields?: Record<string, string[]>;
  saved_at: string;
}

export function patchApiAdminMemberGroupsId(id: string, body: PatchApiAdminMemberGroupsIdIn): Promise<PatchApiAdminMemberGroupsIdOut> {
  return call<PatchApiAdminMemberGroupsIdOut>("PATCH", "/api/admin/member-groups/{id}", { id }, body)
}

export interface PatchApiAdminTeamsIdIn {
  base_version: number;
  changes: {   name?: string | null;   description?: string | null;   is_recruiting?: boolean | null;   recruiting_roles?: string[] | null;   member_contact?: string | null;   logo_image_id?: number | null;   remove_logo?: boolean | null; };
}

export interface PatchApiAdminTeamsIdOut {
  version: number;
  saved: string[];
  fields?: Record<string, string[]>;
  saved_at: string;
}

export function patchApiAdminTeamsId(id: string, body: PatchApiAdminTeamsIdIn): Promise<PatchApiAdminTeamsIdOut> {
  return call<PatchApiAdminTeamsIdOut>("PATCH", "/api/admin/teams/{id}", { id }, body)
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

export interface PatchApiTeamsIdIn {
  base_version: number;
  changes: {   name?: string | null;   description?: string | null;   is_recruiting?: boolean | null;   recruiting_roles?: string[] | null;   member_contact?: string | null;   logo_image_id?: number | null;   remove_logo?: boolean | null; };
}

export interface PatchApiTeamsIdOut {
  version: number;
  saved: string[];
  fields?: Record<string, string[]>;
  saved_at: string;
}

export function patchApiTeamsId(id: string, body: PatchApiTeamsIdIn): Promise<PatchApiTeamsIdOut> {
  return call<PatchApiTeamsIdOut>("PATCH", "/api/teams/{id}", { id }, body)
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

export interface PostApiAdminMemberGroupPeopleIdMoveIn {
  step: number;
}

export interface PostApiAdminMemberGroupPeopleIdMoveOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function postApiAdminMemberGroupPeopleIdMove(id: string, body: PostApiAdminMemberGroupPeopleIdMoveIn): Promise<PostApiAdminMemberGroupPeopleIdMoveOut> {
  return call<PostApiAdminMemberGroupPeopleIdMoveOut>("POST", "/api/admin/member-group-people/{id}/move", { id }, body)
}

export interface PostApiAdminMemberGroupPeopleIdTitleIn {
  title: string;
}

export interface PostApiAdminMemberGroupPeopleIdTitleOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function postApiAdminMemberGroupPeopleIdTitle(id: string, body: PostApiAdminMemberGroupPeopleIdTitleIn): Promise<PostApiAdminMemberGroupPeopleIdTitleOut> {
  return call<PostApiAdminMemberGroupPeopleIdTitleOut>("POST", "/api/admin/member-group-people/{id}/title", { id }, body)
}

export interface PostApiAdminMemberGroupsIn {
}

export interface PostApiAdminMemberGroupsOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminMemberGroups(): Promise<PostApiAdminMemberGroupsOut> {
  return call<PostApiAdminMemberGroupsOut>("POST", "/api/admin/member-groups", {  }, undefined)
}

export interface PostApiAdminMemberGroupsIdPeopleIn {
  user_id: number;
}

export interface PostApiAdminMemberGroupsIdPeopleOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function postApiAdminMemberGroupsIdPeople(id: string, body: PostApiAdminMemberGroupsIdPeopleIn): Promise<PostApiAdminMemberGroupsIdPeopleOut> {
  return call<PostApiAdminMemberGroupsIdPeopleOut>("POST", "/api/admin/member-groups/{id}/people", { id }, body)
}

export interface PostApiAdminTeamsIdAssignCaptainIn {
  user_id: number;
}

export interface PostApiAdminTeamsIdAssignCaptainOut {
  result: string;
}

export function postApiAdminTeamsIdAssignCaptain(id: string, body: PostApiAdminTeamsIdAssignCaptainIn): Promise<PostApiAdminTeamsIdAssignCaptainOut> {
  return call<PostApiAdminTeamsIdAssignCaptainOut>("POST", "/api/admin/teams/{id}/assign-captain", { id }, body)
}

export interface PostApiAdminTeamsIdDisbandIn {
}

export interface PostApiAdminTeamsIdDisbandOut {
  result: string;
}

export function postApiAdminTeamsIdDisband(id: string): Promise<PostApiAdminTeamsIdDisbandOut> {
  return call<PostApiAdminTeamsIdDisbandOut>("POST", "/api/admin/teams/{id}/disband", { id }, undefined)
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

export interface PostApiTeamAlumniIdRemoveIn {
}

export interface PostApiTeamAlumniIdRemoveOut {
  result: string;
}

export function postApiTeamAlumniIdRemove(id: string): Promise<PostApiTeamAlumniIdRemoveOut> {
  return call<PostApiTeamAlumniIdRemoveOut>("POST", "/api/team-alumni/{id}/remove", { id }, undefined)
}

export interface PostApiTeamApplicationsIdApproveIn {
}

export interface PostApiTeamApplicationsIdApproveOut {
  application: {   id: number;   team_id: number;   applicant_id: number;   role_tank: boolean;   role_damage: boolean;   role_support: boolean;   message: string;   status: string;   decided_by?: number | null;   decided_at?: string | null;   decision_note: string;   captain_reminded_at?: string | null;   created_at: string; } | null;
}

export function postApiTeamApplicationsIdApprove(id: string): Promise<PostApiTeamApplicationsIdApproveOut> {
  return call<PostApiTeamApplicationsIdApproveOut>("POST", "/api/team-applications/{id}/approve", { id }, undefined)
}

export interface PostApiTeamApplicationsIdCancelIn {
}

export interface PostApiTeamApplicationsIdCancelOut {
  application: {   id: number;   team_id: number;   applicant_id: number;   role_tank: boolean;   role_damage: boolean;   role_support: boolean;   message: string;   status: string;   decided_by?: number | null;   decided_at?: string | null;   decision_note: string;   captain_reminded_at?: string | null;   created_at: string; } | null;
}

export function postApiTeamApplicationsIdCancel(id: string): Promise<PostApiTeamApplicationsIdCancelOut> {
  return call<PostApiTeamApplicationsIdCancelOut>("POST", "/api/team-applications/{id}/cancel", { id }, undefined)
}

export interface PostApiTeamApplicationsIdRejectIn {
  note: string;
}

export interface PostApiTeamApplicationsIdRejectOut {
  application: {   id: number;   team_id: number;   applicant_id: number;   role_tank: boolean;   role_damage: boolean;   role_support: boolean;   message: string;   status: string;   decided_by?: number | null;   decided_at?: string | null;   decision_note: string;   captain_reminded_at?: string | null;   created_at: string; } | null;
}

export function postApiTeamApplicationsIdReject(id: string, body: PostApiTeamApplicationsIdRejectIn): Promise<PostApiTeamApplicationsIdRejectOut> {
  return call<PostApiTeamApplicationsIdRejectOut>("POST", "/api/team-applications/{id}/reject", { id }, body)
}

export interface PostApiTeamsIn {
  name: string;
  description: string;
  is_recruiting?: boolean | null;
  recruiting_roles?: string[];
  logo_image_id?: number | null;
}

export interface PostApiTeamsOut {
  team: {   id: number;   name: string;   description: string;   logo_image_id: number | null;   is_recruiting: boolean;   recruiting_roles: string[];   member_contact?: string;   disbanded_at?: string | null;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiTeams(body: PostApiTeamsIn): Promise<PostApiTeamsOut> {
  return call<PostApiTeamsOut>("POST", "/api/teams", {  }, body)
}

export interface PostApiTeamsIdApplicationsIn {
  roles: string[];
  message: string;
}

export interface PostApiTeamsIdApplicationsOut {
  application: {   id: number;   team_id: number;   applicant_id: number;   role_tank: boolean;   role_damage: boolean;   role_support: boolean;   message: string;   status: string;   decided_by?: number | null;   decided_at?: string | null;   decision_note: string;   captain_reminded_at?: string | null;   created_at: string; } | null;
}

export function postApiTeamsIdApplications(id: string, body: PostApiTeamsIdApplicationsIn): Promise<PostApiTeamsIdApplicationsOut> {
  return call<PostApiTeamsIdApplicationsOut>("POST", "/api/teams/{id}/applications", { id }, body)
}

export interface PostApiTeamsIdDisbandIn {
}

export interface PostApiTeamsIdDisbandOut {
  result: string;
}

export function postApiTeamsIdDisband(id: string): Promise<PostApiTeamsIdDisbandOut> {
  return call<PostApiTeamsIdDisbandOut>("POST", "/api/teams/{id}/disband", { id }, undefined)
}

export interface PostApiTeamsIdLeaveIn {
}

export interface PostApiTeamsIdLeaveOut {
  result: string;
}

export function postApiTeamsIdLeave(id: string): Promise<PostApiTeamsIdLeaveOut> {
  return call<PostApiTeamsIdLeaveOut>("POST", "/api/teams/{id}/leave", { id }, undefined)
}

export interface PostApiTeamsIdMembersUser_idRemoveIn {
}

export interface PostApiTeamsIdMembersUser_idRemoveOut {
  result: string;
}

export function postApiTeamsIdMembersUser_idRemove(id: string, user_id: string): Promise<PostApiTeamsIdMembersUser_idRemoveOut> {
  return call<PostApiTeamsIdMembersUser_idRemoveOut>("POST", "/api/teams/{id}/members/{user_id}/remove", { id, user_id }, undefined)
}

export interface PostApiTeamsIdTransferIn {
  user_id: number;
}

export interface PostApiTeamsIdTransferOut {
  result: string;
}

export function postApiTeamsIdTransfer(id: string, body: PostApiTeamsIdTransferIn): Promise<PostApiTeamsIdTransferOut> {
  return call<PostApiTeamsIdTransferOut>("POST", "/api/teams/{id}/transfer", { id }, body)
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
