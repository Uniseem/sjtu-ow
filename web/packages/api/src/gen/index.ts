// 由 sjtuow apigen 生成。不要手改。

import type { CallExtras, Requester } from "../client.ts"

export interface DeleteApiAdminCategoriesIdOut {
  result: string;
}

export function deleteApiAdminCategoriesId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiAdminCategoriesIdOut> {
  return r<DeleteApiAdminCategoriesIdOut>("DELETE", "/api/admin/categories/{id}", { ...extras, params: { id } })
}

export interface DeleteApiAdminMemberGroupPeopleIdOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function deleteApiAdminMemberGroupPeopleId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiAdminMemberGroupPeopleIdOut> {
  return r<DeleteApiAdminMemberGroupPeopleIdOut>("DELETE", "/api/admin/member-group-people/{id}", { ...extras, params: { id } })
}

export interface DeleteApiAdminMemberGroupsIdOut {
  result: string;
}

export function deleteApiAdminMemberGroupsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiAdminMemberGroupsIdOut> {
  return r<DeleteApiAdminMemberGroupsIdOut>("DELETE", "/api/admin/member-groups/{id}", { ...extras, params: { id } })
}

export interface DeleteApiAdminScrimsIdOut {
  result: string;
}

export function deleteApiAdminScrimsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiAdminScrimsIdOut> {
  return r<DeleteApiAdminScrimsIdOut>("DELETE", "/api/admin/scrims/{id}", { ...extras, params: { id } })
}

export interface DeleteApiAdminTournamentsIdOut {
  result: string;
}

export function deleteApiAdminTournamentsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiAdminTournamentsIdOut> {
  return r<DeleteApiAdminTournamentsIdOut>("DELETE", "/api/admin/tournaments/{id}", { ...extras, params: { id } })
}

export interface DeleteApiArticlesIdOut {
  result: string;
}

export function deleteApiArticlesId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiArticlesIdOut> {
  return r<DeleteApiArticlesIdOut>("DELETE", "/api/articles/{id}", { ...extras, params: { id } })
}

export interface DeleteApiAuthEmailChangeOut {
  result: string;
  message: string;
}

export function deleteApiAuthEmailChange(r: Requester, extras: CallExtras = {}): Promise<DeleteApiAuthEmailChangeOut> {
  return r<DeleteApiAuthEmailChangeOut>("DELETE", "/api/auth/email/change", { ...extras })
}

export interface DeleteApiCommentsIdOut {
  result: string;
}

export function deleteApiCommentsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiCommentsIdOut> {
  return r<DeleteApiCommentsIdOut>("DELETE", "/api/comments/{id}", { ...extras, params: { id } })
}

export interface DeleteApiImagesIdOut {
  result: string;
}

export function deleteApiImagesId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiImagesIdOut> {
  return r<DeleteApiImagesIdOut>("DELETE", "/api/images/{id}", { ...extras, params: { id } })
}

export interface DeleteApiMeAvatarOut {
  result: string;
}

export function deleteApiMeAvatar(r: Requester, extras: CallExtras = {}): Promise<DeleteApiMeAvatarOut> {
  return r<DeleteApiMeAvatarOut>("DELETE", "/api/me/avatar", { ...extras })
}

export interface DeleteApiMeContactsIdOut {
  result: string;
  message: string;
}

export function deleteApiMeContactsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiMeContactsIdOut> {
  return r<DeleteApiMeContactsIdOut>("DELETE", "/api/me/contacts/{id}", { ...extras, params: { id } })
}

export interface DeleteApiMeGameAccountsIdOut {
  result: string;
  message: string;
}

export function deleteApiMeGameAccountsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiMeGameAccountsIdOut> {
  return r<DeleteApiMeGameAccountsIdOut>("DELETE", "/api/me/game-accounts/{id}", { ...extras, params: { id } })
}

export interface DeleteApiScrimsIdSignupOut {
  result: string;
}

export function deleteApiScrimsIdSignup(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiScrimsIdSignupOut> {
  return r<DeleteApiScrimsIdSignupOut>("DELETE", "/api/scrims/{id}/signup", { ...extras, params: { id } })
}

export interface DeleteApiTournamentsIdSignupOut {
  result: string;
}

export function deleteApiTournamentsIdSignup(r: Requester, id: string | number, extras: CallExtras = {}): Promise<DeleteApiTournamentsIdSignupOut> {
  return r<DeleteApiTournamentsIdSignupOut>("DELETE", "/api/tournaments/{id}/signup", { ...extras, params: { id } })
}

export interface GetApiAdminActivityQuery {
  preset?: string;
  start?: string;
  end?: string;
}

export interface GetApiAdminActivityOut {
  period: {   start: string;   end: string; };
  notice?: string;
  totals: {   members: number;   sjtu_members: number;   scrims: number;   scrim_signups: number;   scrim_players: number;   scrim_people: number;   tournaments: number;   tournament_teams: number;   tournament_people: number;   articles: number;   comments: number;   teams: number; };
  events: {   when: string;   kind: string;   title: string;   status: string;   entries: number;   players: number;   url: string; }[];
  presets: string[];
}

export function getApiAdminActivity(r: Requester, query: GetApiAdminActivityQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminActivityOut> {
  return r<GetApiAdminActivityOut>("GET", "/api/admin/activity", { ...extras, query })
}

export interface GetApiAdminAnnounceKindIdOut {
  problem: string;
  recipients: number;
  will_wait: boolean;
  history: {   id: number;   audience: string;   subject: string;   recipient_count: number;   waiting: boolean;   created_at: string; }[];
}

export function getApiAdminAnnounceKindId(r: Requester, kind: string | number, id: string | number, extras: CallExtras = {}): Promise<GetApiAdminAnnounceKindIdOut> {
  return r<GetApiAdminAnnounceKindIdOut>("GET", "/api/admin/announce/{kind}/{id}", { ...extras, params: { kind, id } })
}

export interface GetApiAdminArticlesQuery {
  category?: string;
  page?: number;
  page_size?: number;
}

export interface GetApiAdminArticlesOut {
  total: number;
  page: number;
  page_size: number;
  items: ({   id: number;   kind: string;   slug: string;   title: string;   live: boolean;   has_unpublished_changes: boolean;   go_live_at?: string | null;   expire_at?: string | null;   first_published_at?: string | null;   last_published_at?: string | null;   live_revision_id?: number | null;   latest_revision_id?: number | null;   owner_id?: number | null;   seo_title: string;   search_description: string;   version: number;   created_at: string;   updated_at: string;   category_id?: number | null;   category_name?: string;   cover_image_id?: number | null;   summary: string;   body_md: string;   body_html: string;   body_plain: string;   char_count: number;   reading_time: number;   author_id?: number | null;   author_name?: string;   comments_enabled: boolean;   related_tournament_id?: number | null;   search_text: string;   renderer_version: number; } | null)[];
}

export function getApiAdminArticles(r: Requester, query: GetApiAdminArticlesQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminArticlesOut> {
  return r<GetApiAdminArticlesOut>("GET", "/api/admin/articles", { ...extras, query })
}

export interface GetApiAdminArticlesIdOut {
  article: {   id: number;   kind: string;   slug: string;   title: string;   live: boolean;   has_unpublished_changes: boolean;   go_live_at?: string | null;   expire_at?: string | null;   first_published_at?: string | null;   last_published_at?: string | null;   live_revision_id?: number | null;   latest_revision_id?: number | null;   owner_id?: number | null;   seo_title: string;   search_description: string;   version: number;   created_at: string;   updated_at: string;   category_id?: number | null;   category_name?: string;   cover_image_id?: number | null;   summary: string;   body_md: string;   body_html: string;   body_plain: string;   char_count: number;   reading_time: number;   author_id?: number | null;   author_name?: string;   comments_enabled: boolean;   related_tournament_id?: number | null;   search_text: string;   renderer_version: number; } | null;
  revision?: {   title: string;   slug: string;   category_id: number | null;   cover_image_id: number | null;   summary: string;   body_md: string;   author_id: number | null;   comments_enabled: boolean;   related_tournament_id: number | null;   seo_title: string;   search_description: string;   go_live_at: string | null;   expire_at: string | null; } | null;
  version: number;
}

export function getApiAdminArticlesId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiAdminArticlesIdOut> {
  return r<GetApiAdminArticlesIdOut>("GET", "/api/admin/articles/{id}", { ...extras, params: { id } })
}

export interface GetApiAdminAvatarsQuery {
  status?: string;
  page?: number;
  page_size?: number;
}

export interface GetApiAdminAvatarsOut {
  items: ({   id: number;   user_id: number;   user_nickname: string;   image_id: number | null;   status: string;   handling_note: string;   reviewed_at?: string | null;   created_at: string; })[];
  total: number;
  page: number;
  page_size: number;
}

export function getApiAdminAvatars(r: Requester, query: GetApiAdminAvatarsQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminAvatarsOut> {
  return r<GetApiAdminAvatarsOut>("GET", "/api/admin/avatars", { ...extras, query })
}

export interface GetApiAdminCategoriesOut {
  items: ({   id: number;   name: string;   slug: string;   description: string;   sort_order: number;   allow_submission: boolean;   version: number;   created_at: string;   updated_at: string;   article_count?: number; } | null)[];
}

export function getApiAdminCategories(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminCategoriesOut> {
  return r<GetApiAdminCategoriesOut>("GET", "/api/admin/categories", { ...extras })
}

export interface GetApiAdminCommentsQuery {
  q?: string;
  hidden?: boolean;
  pinned?: boolean;
  page?: number;
  page_size?: number;
}

export interface GetApiAdminCommentsOut {
  items: {   id: number;   article_id: number;   article_title: string;   author_id: number;   author_name: string;   content: string;   is_pinned: boolean;   is_hidden: boolean;   is_deleted: boolean;   like_count: number;   created_at: string; }[];
  total: number;
  page: number;
  page_size: number;
}

export function getApiAdminComments(r: Requester, query: GetApiAdminCommentsQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminCommentsOut> {
  return r<GetApiAdminCommentsOut>("GET", "/api/admin/comments", { ...extras, query })
}

export interface GetApiAdminFeatureRoleRestrictionsOut {
  restrictions: {   role: string;   feature: string; }[];
}

export function getApiAdminFeatureRoleRestrictions(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminFeatureRoleRestrictionsOut> {
  return r<GetApiAdminFeatureRoleRestrictionsOut>("GET", "/api/admin/feature-role-restrictions", { ...extras })
}

export interface GetApiAdminHomePinsOut {
  items: ({   id: number;   slug: string;   title: string;   category_name: string;   cover_image_id?: number | null;   summary: string;   reading_time: number;   author_name: string;   first_published_at?: string | null;   pinned?: boolean; } | null)[];
}

export function getApiAdminHomePins(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminHomePinsOut> {
  return r<GetApiAdminHomePinsOut>("GET", "/api/admin/home-pins", { ...extras })
}

export interface GetApiAdminImageCollectionsOut {
  collections: {   id: number;   name: string;   key: string;   created_at: string; }[];
}

export function getApiAdminImageCollections(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminImageCollectionsOut> {
  return r<GetApiAdminImageCollectionsOut>("GET", "/api/admin/image-collections", { ...extras })
}

export interface GetApiAdminImagesQuery {
  collection_key?: string;
  collection_id?: number;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface GetApiAdminImagesOut {
  items: ({   id: number;   collection_id: number | null;   title: string;   file_name: string;   file_size: number;   width: number;   height: number;   uploader_id: number | null;   created_at: string;   version: number; })[];
  total: number;
  page: number;
  page_size: number;
}

export function getApiAdminImages(r: Requester, query: GetApiAdminImagesQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminImagesOut> {
  return r<GetApiAdminImagesOut>("GET", "/api/admin/images", { ...extras, query })
}

export interface GetApiAdminLogQuery {
  action?: string;
  actor_id?: number;
  object_type?: string;
  since?: string;
  until?: string;
  page?: number;
  page_size?: number;
}

export interface GetApiAdminLogOut {
  items: ({   id: number;   actor_id: number | null;   action: string;   object_type: string;   object_id: number;   data: unknown;   created_at: string;   actor_nickname: string;   actor_email: string; })[];
  total: number;
  page: number;
  page_size: number;
}

export function getApiAdminLog(r: Requester, query: GetApiAdminLogQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminLogOut> {
  return r<GetApiAdminLogOut>("GET", "/api/admin/log", { ...extras, query })
}

export interface GetApiAdminManualOut {
  parts: {   key: string;   title: string;   steps: {   text: string;   link_url?: string;   link_label?: string; }[]; }[];
}

export function getApiAdminManual(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminManualOut> {
  return r<GetApiAdminManualOut>("GET", "/api/admin/manual", { ...extras })
}

export interface GetApiAdminMemberGroupsOut {
  groups: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string;   member_count: number; }[];
}

export function getApiAdminMemberGroups(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminMemberGroupsOut> {
  return r<GetApiAdminMemberGroupsOut>("GET", "/api/admin/member-groups", { ...extras })
}

export interface GetApiAdminMemberGroupsIdOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function getApiAdminMemberGroupsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiAdminMemberGroupsIdOut> {
  return r<GetApiAdminMemberGroupsIdOut>("GET", "/api/admin/member-groups/{id}", { ...extras, params: { id } })
}

export interface GetApiAdminMemberGroupsIdPeopleQuery {
  q?: string;
}

export interface GetApiAdminMemberGroupsIdPeopleOut {
  results: {   user_id: number;   nickname: string;   email?: string; }[];
}

export function getApiAdminMemberGroupsIdPeople(r: Requester, id: string | number, query: GetApiAdminMemberGroupsIdPeopleQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminMemberGroupsIdPeopleOut> {
  return r<GetApiAdminMemberGroupsIdPeopleOut>("GET", "/api/admin/member-groups/{id}/people", { ...extras, params: { id }, query })
}

export interface GetApiAdminModerationQuery {
  status?: string;
  risk?: string;
  target_type?: string;
  since?: number;
  page?: number;
}

export interface GetApiAdminModerationOut {
  items: ({   id: number;   target_type: string;   target_label: string;   target_id: number;   field: string;   url: string;   author_id: number | null;   excerpt: string;   full_text?: string;   text_hash: string;   risk: string;   categories: string[];   reason: string;   quote: string;   status: string;   reviewed_by: number | null;   reviewed_at: string | null;   handling_note: string;   checked_at: string | null;   notified_at: string | null;   attempts: number;   last_error: string;   failed_at: string | null;   created_at: string; } | null)[];
  total: number;
  page: number;
  page_size: number;
  enabled: boolean;
  waiting: number;
  failed: number;
  last_error: string;
}

export function getApiAdminModeration(r: Requester, query: GetApiAdminModerationQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminModerationOut> {
  return r<GetApiAdminModerationOut>("GET", "/api/admin/moderation", { ...extras, query })
}

export interface GetApiAdminModerationIdOut {
  item: {   id: number;   target_type: string;   target_label: string;   target_id: number;   field: string;   url: string;   author_id: number | null;   excerpt: string;   full_text?: string;   text_hash: string;   risk: string;   categories: string[];   reason: string;   quote: string;   status: string;   reviewed_by: number | null;   reviewed_at: string | null;   handling_note: string;   checked_at: string | null;   notified_at: string | null;   attempts: number;   last_error: string;   failed_at: string | null;   created_at: string; } | null;
  author_flags: number;
  author_problem: string;
  history: ({   id: number;   actor_id: number | null;   action: string;   object_type: string;   object_id: number;   data: unknown;   created_at: string; })[];
}

export function getApiAdminModerationId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiAdminModerationIdOut> {
  return r<GetApiAdminModerationIdOut>("GET", "/api/admin/moderation/{id}", { ...extras, params: { id } })
}

export interface GetApiAdminScrimsOut {
  scrims: ({   id: number;   title: string;   starts_at: string | null;   signup_deadline: string | null;   format: string;   format_label: string;   sjtu_only: boolean;   status: string;   signup_open: boolean;   signup_total: number;   players_needed: number;   missing: string[];   can_delete: boolean;   teams_stale: boolean; })[];
}

export function getApiAdminScrims(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminScrimsOut> {
  return r<GetApiAdminScrimsOut>("GET", "/api/admin/scrims", { ...extras })
}

export interface GetApiAdminScrimsIdOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  row: {   id: number;   title: string;   starts_at: string | null;   signup_deadline: string | null;   format: string;   format_label: string;   sjtu_only: boolean;   status: string;   signup_open: boolean;   signup_total: number;   players_needed: number;   missing: string[];   can_delete: boolean;   teams_stale: boolean; } | null;
}

export function getApiAdminScrimsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiAdminScrimsIdOut> {
  return r<GetApiAdminScrimsIdOut>("GET", "/api/admin/scrims/{id}", { ...extras, params: { id } })
}

export interface GetApiAdminScrimsIdBoardQuery {
  order?: string;
}

export interface GetApiAdminScrimsIdBoardOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  order: string;
  signups: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[];
  selected_count: number;
  needed: number;
  teams: ({   team: string;   label: string;   total: number;   problems: string[];   members: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[]; })[];
  bench: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[];
  gap: number;
  has_teams: boolean;
  teams_stale: boolean;
  copy_text: string;
  board_version: number;
  warnings?: string[];
}

export function getApiAdminScrimsIdBoard(r: Requester, id: string | number, query: GetApiAdminScrimsIdBoardQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminScrimsIdBoardOut> {
  return r<GetApiAdminScrimsIdBoardOut>("GET", "/api/admin/scrims/{id}/board", { ...extras, params: { id }, query })
}

export interface GetApiAdminSettingsOut {
  settings: {   id: number;   site_description: string;   from_name: string;   email_subject_prefix: string;   smtp_host: string;   smtp_port: number;   smtp_security: string;   smtp_username: string;   has_smtp_password: boolean;   from_address: string;   founded_on: string;   default_share_image_id: number | null;   hero_image_id: number | null;   banner_news_id: number | null;   banner_tournaments_id: number | null;   banner_scrims_id: number | null;   banner_teams_id: number | null;   banner_members_id: number | null;   qq_group_url: string;   team_max_members: number;   team_max_captained: number;   tournament_reminder_hours: number;   scrim_reminder_hours: number;   moderation_enabled: boolean;   moderation_configured: boolean;   moderation_provider: string;   has_moderation_api_key: boolean;   moderation_base_url: string;   moderation_model: string;   moderation_max_tokens: number;   moderation_timeout_seconds: number;   moderation_extra_params: string;   moderation_daily_limit: number;   moderation_notify_email: string;   version: number;   updated_at: string; } | null;
}

export function getApiAdminSettings(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminSettingsOut> {
  return r<GetApiAdminSettingsOut>("GET", "/api/admin/settings", { ...extras })
}

export interface GetApiAdminTeamsOut {
  teams: ({   id: number;   name: string;   member_count: number;   captain_id: number | null;   captain_name: string;   captain_active: boolean;   no_captain: boolean;   disbanded_at?: string | null;   created_at: string; })[];
}

export function getApiAdminTeams(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminTeamsOut> {
  return r<GetApiAdminTeamsOut>("GET", "/api/admin/teams", { ...extras })
}

export interface GetApiAdminTodoOut {
  has_duties: boolean;
  items: {   text: string;   url: string;   count: number; }[];
}

export function getApiAdminTodo(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminTodoOut> {
  return r<GetApiAdminTodoOut>("GET", "/api/admin/todo", { ...extras })
}

export interface GetApiAdminTournamentsOut {
  tournaments: ({   id: number;   title: string;   summary: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   registration_mode: string;   sjtu_only: boolean;   status: string;   phase: string;   approved_count: number;   pending_count: number;   waiting_for_team: number;   missing: string[]; })[];
}

export function getApiAdminTournaments(r: Requester, extras: CallExtras = {}): Promise<GetApiAdminTournamentsOut> {
  return r<GetApiAdminTournamentsOut>("GET", "/api/admin/tournaments", { ...extras })
}

export interface GetApiAdminTournamentsIdOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
  missing: string[];
  has_entries: boolean;
  has_registrations: boolean;
  can_delete: boolean;
  team_max_members: number;
}

export function getApiAdminTournamentsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiAdminTournamentsIdOut> {
  return r<GetApiAdminTournamentsIdOut>("GET", "/api/admin/tournaments/{id}", { ...extras, params: { id } })
}

export interface GetApiAdminTournamentsIdBoardOut {
  tournament: {   id: number;   title: string;   summary: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   registration_mode: string;   sjtu_only: boolean;   status: string;   phase: string;   approved_count: number; } | null;
  roster_max: number;
  entries: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   registration_id: number | null;   conflict?: string; })[];
  teams: {   registration_id: number;   name: string;   roster_version: number;   signup_ids: number[]; }[];
}

export function getApiAdminTournamentsIdBoard(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiAdminTournamentsIdBoardOut> {
  return r<GetApiAdminTournamentsIdBoardOut>("GET", "/api/admin/tournaments/{id}/board", { ...extras, params: { id } })
}

export interface GetApiAdminTournamentsIdRegistrationsQuery {
  status?: string;
}

export interface GetApiAdminTournamentsIdRegistrationsOut {
  registrations: ({   registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; };   roster: ({   id: number;   user_id: number;   game_account_id: number | null;   nickname: string;   battletag: string;   is_sjtu: boolean;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   is_captain: boolean;   is_active: boolean; })[];   logs: ({   id: number;   action: string;   from_status: string;   to_status: string;   actor_type: string;   actor_user_id?: number | null;   roster_version: number;   note: string;   created_at: string; })[]; })[];
}

export function getApiAdminTournamentsIdRegistrations(r: Requester, id: string | number, query: GetApiAdminTournamentsIdRegistrationsQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminTournamentsIdRegistrationsOut> {
  return r<GetApiAdminTournamentsIdRegistrationsOut>("GET", "/api/admin/tournaments/{id}/registrations", { ...extras, params: { id }, query })
}

export interface GetApiAdminUsersQuery {
  page?: number;
  page_size?: number;
  search?: string;
}

export interface GetApiAdminUsersOut {
  total: number;
  users: {   id: number;   email: string;   nickname: string;   is_sjtu: boolean;   is_active: boolean;   is_superuser: boolean;   email_verified: boolean;   deactivation_note: string;   created_at: string; }[];
}

export function getApiAdminUsers(r: Requester, query: GetApiAdminUsersQuery = {}, extras: CallExtras = {}): Promise<GetApiAdminUsersOut> {
  return r<GetApiAdminUsersOut>("GET", "/api/admin/users", { ...extras, query })
}

export interface GetApiAdminUsersIdOut {
  user: {   ID: number;   Email: string;   EmailNorm: string;   PasswordHash: string;   Nickname: string;   IsSJTU: boolean;   AgreedTermsAt: string;   AgreedCrossBorderAt: string;   EmailVerifiedAt: string | null;   PasswordChangedAt: string | null;   Version: number;   IsActive: boolean;   IsSuperuser: boolean;   DeactivationNote: string;   Motto: string;   MainRole: string;   FlexRoles: string;   ShowRank: boolean;   AvatarImageID: number | null;   CreatedAt: string;   UpdatedAt: string; } | null;
  roles: string[];
  rules: Record<string, boolean>;
  game_accounts: ({   id: number;   battletag: string;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   tank_label: string;   damage_label: string;   support_label: string;   ranks_updated_at: string; })[];
  contacts: {   id: number;   type: string;   type_label: string;   value: string;   created_at: string; }[];
}

export function getApiAdminUsersId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiAdminUsersIdOut> {
  return r<GetApiAdminUsersIdOut>("GET", "/api/admin/users/{id}", { ...extras, params: { id } })
}

export interface GetApiAnnouncementsUnsubscribeTokenOut {
  nickname?: string;
  accepts: boolean;
}

export function getApiAnnouncementsUnsubscribeToken(r: Requester, token: string | number, extras: CallExtras = {}): Promise<GetApiAnnouncementsUnsubscribeTokenOut> {
  return r<GetApiAnnouncementsUnsubscribeTokenOut>("GET", "/api/announcements/unsubscribe/{token}", { ...extras, params: { token } })
}

export interface GetApiArticlesIdCommentsQuery {
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface GetApiArticlesIdCommentsOut {
  total: number;
  page: number;
  page_size: number;
  comments: ({   id: number;   article_id: number;   user_id?: number | null;   author_name: string;   parent_id?: number | null;   reply_to_user_id?: number | null;   reply_to_user_name?: string;   content: string;   is_pinned: boolean;   is_hidden: boolean;   is_deleted: boolean;   is_tombstone?: boolean;   like_count: number;   liked_by_me?: boolean;   reply_count?: number;   replies?: (unknown | null)[];   version: number;   created_at: string;   updated_at: string;   edited_at: string | null; } | null)[];
}

export function getApiArticlesIdComments(r: Requester, id: string | number, query: GetApiArticlesIdCommentsQuery = {}, extras: CallExtras = {}): Promise<GetApiArticlesIdCommentsOut> {
  return r<GetApiArticlesIdCommentsOut>("GET", "/api/articles/{id}/comments", { ...extras, params: { id }, query })
}

export interface GetApiAuthEmailStateOut {
  email: string;
  pending_email?: string;
  reauthenticated: boolean;
}

export function getApiAuthEmailState(r: Requester, extras: CallExtras = {}): Promise<GetApiAuthEmailStateOut> {
  return r<GetApiAuthEmailStateOut>("GET", "/api/auth/email/state", { ...extras })
}

export interface GetApiAuthResetPasswordStateOut {
  verified: boolean;
  email?: string;
}

export function getApiAuthResetPasswordState(r: Requester, extras: CallExtras = {}): Promise<GetApiAuthResetPasswordStateOut> {
  return r<GetApiAuthResetPasswordStateOut>("GET", "/api/auth/reset-password/state", { ...extras })
}

export interface GetApiHomePinsOut {
  items: ({   id: number;   slug: string;   title: string;   category_name: string;   cover_image_id?: number | null;   summary: string;   reading_time: number;   author_name: string;   first_published_at?: string | null;   pinned?: boolean; } | null)[];
}

export function getApiHomePins(r: Requester, extras: CallExtras = {}): Promise<GetApiHomePinsOut> {
  return r<GetApiHomePinsOut>("GET", "/api/home-pins", { ...extras })
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

export function getApiImagesId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiImagesIdOut> {
  return r<GetApiImagesIdOut>("GET", "/api/images/{id}", { ...extras, params: { id } })
}

export interface GetApiLettersOut {
  batches: {   batch: string;   subjects: string[];   people: number;   at: string;   in_back_office: boolean; }[];
}

export function getApiLetters(r: Requester, extras: CallExtras = {}): Promise<GetApiLettersOut> {
  return r<GetApiLettersOut>("GET", "/api/letters", { ...extras })
}

export interface GetApiLettersBatchOut {
  batch: string;
  state: string;
  letters: {   id: number;   subject: string;   who: string;   count: number; }[];
  back: string;
  in_back_office: boolean;
}

export function getApiLettersBatch(r: Requester, batch: string | number, extras: CallExtras = {}): Promise<GetApiLettersBatchOut> {
  return r<GetApiLettersBatchOut>("GET", "/api/letters/{batch}", { ...extras, params: { batch } })
}

export interface GetApiMeAgendaOut {
  items: ({   kind: string;   title: string;   url: string;   when: string | null;   note: string; })[];
}

export function getApiMeAgenda(r: Requester, extras: CallExtras = {}): Promise<GetApiMeAgendaOut> {
  return r<GetApiMeAgendaOut>("GET", "/api/me/agenda", { ...extras })
}

export interface GetApiMeAnnouncementsOut {
  nickname?: string;
  accepts: boolean;
}

export function getApiMeAnnouncements(r: Requester, extras: CallExtras = {}): Promise<GetApiMeAnnouncementsOut> {
  return r<GetApiMeAnnouncementsOut>("GET", "/api/me/announcements", { ...extras })
}

export interface GetApiMeCalendarOut {
  url: string;
  webcal: string;
}

export function getApiMeCalendar(r: Requester, extras: CallExtras = {}): Promise<GetApiMeCalendarOut> {
  return r<GetApiMeCalendarOut>("GET", "/api/me/calendar", { ...extras })
}

export interface GetApiMeExportOut {
  user: {   ID: number;   Email: string;   EmailNorm: string;   PasswordHash: string;   Nickname: string;   IsSJTU: boolean;   AgreedTermsAt: string;   AgreedCrossBorderAt: string;   EmailVerifiedAt: string | null;   PasswordChangedAt: string | null;   Version: number;   IsActive: boolean;   IsSuperuser: boolean;   DeactivationNote: string;   Motto: string;   MainRole: string;   FlexRoles: string;   ShowRank: boolean;   AvatarImageID: number | null;   CreatedAt: string;   UpdatedAt: string; } | null;
  game_accounts: ({   id: number;   battletag: string;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   tank_label: string;   damage_label: string;   support_label: string;   ranks_updated_at: string; })[];
  contacts: {   id: number;   type: string;   type_label: string;   value: string;   created_at: string; }[];
  roles: string[];
  teams: {   team_id: number;   name: string;   role: string;   joined_at: string; }[];
  team_applications: {   id: number;   team_id: number;   team_name: string;   roles: string[];   message: string;   status: string;   created_at: string; }[];
  team_alumni: {   team_id: number;   team_name: string;   role: string;   joined_at: string;   left_at: string;   reason: string; }[];
  member_groups: {   group_id: number;   name: string;   title: string; }[];
  exported_at: string;
}

export function getApiMeExport(r: Requester, extras: CallExtras = {}): Promise<GetApiMeExportOut> {
  return r<GetApiMeExportOut>("GET", "/api/me/export", { ...extras })
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
  game_accounts: ({   id: number;   battletag: string;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   tank_label: string;   damage_label: string;   support_label: string;   ranks_updated_at: string; })[];
  contacts: {   id: number;   type: string;   type_label: string;   value: string;   created_at: string; }[];
}

export function getApiMeProfile(r: Requester, extras: CallExtras = {}): Promise<GetApiMeProfileOut> {
  return r<GetApiMeProfileOut>("GET", "/api/me/profile", { ...extras })
}

export interface GetApiMeRegistrationsOut {
  registrations: {   registration_id: number;   tournament_id: number;   title: string;   team_name: string;   status: string;   submitted_at: string; }[];
}

export function getApiMeRegistrations(r: Requester, extras: CallExtras = {}): Promise<GetApiMeRegistrationsOut> {
  return r<GetApiMeRegistrationsOut>("GET", "/api/me/registrations", { ...extras })
}

export interface GetApiMeTeamsOut {
  teams: ({   team_id: number;   name: string;   logo_image_id: number | null;   role: string;   member_count: number;   joined_at: string; })[];
  applications: ({   id: number;   team_id: number;   team_name: string;   roles: string[];   status: string;   decision_note: string;   created_at: string;   decided_at?: string | null; })[];
}

export function getApiMeTeams(r: Requester, extras: CallExtras = {}): Promise<GetApiMeTeamsOut> {
  return r<GetApiMeTeamsOut>("GET", "/api/me/teams", { ...extras })
}

export interface GetApiMembersQuery {
  role?: string;
  free?: boolean;
}

export interface GetApiMembersOut {
  sections: ({   id: number;   name: string;   description: string;   entries: ({   titles: string[];   member: {   user_id: number;   number: number;   nickname: string;   motto: string;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   teams: {   id: number;   name: string; }[];   groups: string[];   titles: string[]; }; })[]; })[];
  members: ({   user_id: number;   number: number;   nickname: string;   motto: string;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   teams: {   id: number;   name: string; }[];   groups: string[];   titles: string[]; })[];
  total: number;
  role: string;
  free: boolean;
  filtering: boolean;
}

export function getApiMembers(r: Requester, query: GetApiMembersQuery = {}, extras: CallExtras = {}): Promise<GetApiMembersOut> {
  return r<GetApiMembersOut>("GET", "/api/members", { ...extras, query })
}

export interface GetApiMembersIdOut {
  card: {   user_id: number;   number: number;   nickname: string;   motto: string;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   teams: {   id: number;   name: string; }[];   groups: string[];   titles: string[]; };
  groups: {   id: number;   name: string;   titles: string[]; }[];
  teams: {   id: number;   name: string;   member_count: number;   is_captain: boolean; }[];
  alumni: {   team_id: number;   team_name: string;   role: string;   left_at: string;   reason: string; }[];
  articles: ({   id: number;   slug: string;   title: string;   first_published_at?: string | null; })[];
  article_count: number;
  is_owner: boolean;
}

export function getApiMembersId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiMembersIdOut> {
  return r<GetApiMembersIdOut>("GET", "/api/members/{id}", { ...extras, params: { id } })
}

export interface GetApiPageHomeOut {
  stats: {   member_count: number;   team_count: number;   scrims_held: number;   founded_on?: string;   age?: {   years: number;   days: number; } | null;   hero_image_id?: number | null;   qq_group_url?: string; } | null;
  feature_tournament?: {   id: number;   title: string;   phase: string;   phase_label: string;   registration_mode: string;   takes_individuals: boolean;   approved_teams: number;   starts_at?: string;   registration_opens_at?: string;   registration_closes_at?: string;   cover_image_id?: number | null;   facts: string; } | null;
  scrims: ({   id: number;   title: string;   starts_at: string;   month: number;   day: number;   weekday: string;   time: string;   count: number;   capacity: number;   signup_open: boolean; } | null)[];
  news: ({   id: number;   slug: string;   title: string;   category_name: string;   cover_image_id?: number | null;   summary: string;   reading_time: number;   author_name: string;   first_published_at?: string | null;   pinned?: boolean; } | null)[];
  notices: ({   id: number;   slug: string;   title: string;   month: number;   day: number;   published_at_raw: string; } | null)[];
  teams: ({   id: number;   name: string;   logo_image_id?: number | null;   member_count: number;   is_recruiting: boolean;   wanted_roles?: string;   created_at_month: string; } | null)[];
}

export function getApiPageHome(r: Requester, extras: CallExtras = {}): Promise<GetApiPageHomeOut> {
  return r<GetApiPageHomeOut>("GET", "/api/page/home", { ...extras })
}

export interface GetApiPageNewsQuery {
  category?: string;
  page?: number;
  page_size?: number;
}

export interface GetApiPageNewsOut {
  total: number;
  page: number;
  page_size: number;
  items: ({   id: number;   slug: string;   title: string;   category_name: string;   cover_image_id?: number | null;   summary: string;   reading_time: number;   author_name: string;   first_published_at?: string | null;   pinned?: boolean; } | null)[];
}

export function getApiPageNews(r: Requester, query: GetApiPageNewsQuery = {}, extras: CallExtras = {}): Promise<GetApiPageNewsOut> {
  return r<GetApiPageNewsOut>("GET", "/api/page/news", { ...extras, query })
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
  headings: ({   level: number;   text: string;   id: string; } | null)[];
}

export function getApiPageNewsSlug(r: Requester, slug: string | number, extras: CallExtras = {}): Promise<GetApiPageNewsSlugOut> {
  return r<GetApiPageNewsSlugOut>("GET", "/api/page/news/{slug}", { ...extras, params: { slug } })
}

export interface GetApiPageSlugOut {
  slug: string;
  title: string;
  body_html: string;
  seo_title: string;
  search_description: string;
  last_published_at: string | null;
}

export function getApiPageSlug(r: Requester, slug: string | number, extras: CallExtras = {}): Promise<GetApiPageSlugOut> {
  return r<GetApiPageSlugOut>("GET", "/api/page/{slug}", { ...extras, params: { slug } })
}

export interface GetApiRegistrationsIdOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
  tournament: {   id: number;   title: string;   summary: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   registration_mode: string;   sjtu_only: boolean;   status: string;   phase: string;   approved_count: number; } | null;
  roster: ({   id: number;   user_id: number;   game_account_id: number | null;   nickname: string;   battletag: string;   is_sjtu: boolean;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   is_captain: boolean;   is_active: boolean; })[];
  logs: ({   id: number;   action: string;   from_status: string;   to_status: string;   actor_type: string;   actor_user_id?: number | null;   roster_version: number;   note: string;   created_at: string; })[];
  is_captain: boolean;
  can_withdraw: boolean;
  can_resubmit: boolean;
  roster_differs: boolean;
  can_leave: boolean;
  participant_contact?: string;
}

export function getApiRegistrationsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiRegistrationsIdOut> {
  return r<GetApiRegistrationsIdOut>("GET", "/api/registrations/{id}", { ...extras, params: { id } })
}

export interface GetApiScrimsOut {
  scrims: ({   id: number;   title: string;   starts_at: string | null;   signup_deadline: string | null;   format: string;   format_label: string;   sjtu_only: boolean;   status: string;   signup_open: boolean;   signup_total: number;   players_needed: number; })[];
}

export function getApiScrims(r: Requester, extras: CallExtras = {}): Promise<GetApiScrimsOut> {
  return r<GetApiScrimsOut>("GET", "/api/scrims", { ...extras })
}

export interface GetApiScrimsIdOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  card: {   id: number;   title: string;   starts_at: string | null;   signup_deadline: string | null;   format: string;   format_label: string;   sjtu_only: boolean;   status: string;   signup_open: boolean;   signup_total: number;   players_needed: number; };
  counts: {   total: number;   tank: number;   damage: number;   support: number; };
  signups: {   nickname: string;   roles: string[]; }[];
  mine: {   id: number;   game_account_id: number | null;   roles: string[];   placement: string;   can_cancel: boolean; } | null;
  problems: string[];
}

export function getApiScrimsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiScrimsIdOut> {
  return r<GetApiScrimsIdOut>("GET", "/api/scrims/{id}", { ...extras, params: { id } })
}

export interface GetApiSearchQuery {
  q?: string;
}

export interface GetApiSearchOut {
  query: string;
  groups: {   key: string;   label: string;   hits: {   title: string;   url: string;   excerpt: string;   meta: string; }[];   truncated: boolean; }[];
  articles: ({   id: number;   slug: string;   title: string;   summary: string;   category_name: string;   first_published_at?: string | null; } | null)[];
  teams: ({   id: number;   name: string;   description: string;   is_recruiting: boolean; } | null)[];
  members: ({   id: number;   nickname: string;   motto: string; } | null)[];
  tournaments: ({   id: number;   title: string;   summary: string; } | null)[];
  scrims: ({   id: number;   title: string; } | null)[];
}

export function getApiSearch(r: Requester, query: GetApiSearchQuery = {}, extras: CallExtras = {}): Promise<GetApiSearchOut> {
  return r<GetApiSearchOut>("GET", "/api/search", { ...extras, query })
}

export interface GetApiSessionQuery {
  refresh?: boolean;
}

export interface GetApiSessionOut {
  user: {   id: number;   nickname: string;   email: string;   admin: boolean;   superuser: boolean;   caps: string[];   email_verified: boolean;   is_sjtu: boolean;   can_submit_article: boolean;   can_comment: boolean; } | null;
  flash?: string;
}

export function getApiSession(r: Requester, query: GetApiSessionQuery = {}, extras: CallExtras = {}): Promise<GetApiSessionOut> {
  return r<GetApiSessionOut>("GET", "/api/session", { ...extras, query })
}

export interface GetApiTeamsQuery {
  recruiting?: boolean;
  role?: string;
}

export interface GetApiTeamsOut {
  teams: ({   id: number;   name: string;   description: string;   logo_image_id: number | null;   is_recruiting: boolean;   wanted_roles: string[];   member_count: number;   is_full: boolean; })[];
  team_total: number;
  recruiting_total: number;
  role_counts: Record<string, number>;
  max_members: number;
  recruiting_only: boolean;
  role: string;
}

export function getApiTeams(r: Requester, query: GetApiTeamsQuery = {}, extras: CallExtras = {}): Promise<GetApiTeamsOut> {
  return r<GetApiTeamsOut>("GET", "/api/teams", { ...extras, query })
}

export interface GetApiTeamsIdOut {
  team: {   id: number;   name: string;   description: string;   logo_image_id: number | null;   is_recruiting: boolean;   recruiting_roles: string[];   member_contact?: string;   disbanded_at?: string | null;   version: number;   created_at: string;   updated_at: string; } | null;
  members: ({   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   role: string;   joined_at: string; })[];
  alumni: ({   id: number;   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   role: string;   joined_at: string;   left_at: string;   reason: string;   can_remove: boolean; })[];
  max_members: number;
  viewer: {   is_member: boolean;   is_captain: boolean;   is_superuser: boolean;   can_apply: boolean;   apply_reason?: string;   needs_game_account: boolean; };
}

export function getApiTeamsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiTeamsIdOut> {
  return r<GetApiTeamsIdOut>("GET", "/api/teams/{id}", { ...extras, params: { id } })
}

export interface GetApiTeamsIdManageOut {
  team: {   id: number;   name: string;   description: string;   logo_image_id: number | null;   is_recruiting: boolean;   recruiting_roles: string[];   member_contact?: string;   disbanded_at?: string | null;   version: number;   created_at: string;   updated_at: string; } | null;
  members: ({   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   role: string;   joined_at: string; })[];
  alumni: ({   id: number;   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; };   role: string;   joined_at: string;   left_at: string;   reason: string;   can_remove: boolean; })[];
  pending: ({   id: number;   applicant: {   user_id: number;   nickname: string;   is_active: boolean;   main_role: string;   roles: string[];   ranks: {   tank: {   score: number | null;   label: string;   is_expired: boolean; };   damage: {   score: number | null;   label: string;   is_expired: boolean; };   support: {   score: number | null;   label: string;   is_expired: boolean; }; }; };   roles: string[];   message: string;   created_at: string;   game_ids: string[];   reminded: boolean; })[];
  disband_blockers: string[];
  max_members: number;
}

export function getApiTeamsIdManage(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiTeamsIdManageOut> {
  return r<GetApiTeamsIdManageOut>("GET", "/api/teams/{id}/manage", { ...extras, params: { id } })
}

export interface GetApiTournamentsOut {
  groups: ({   phase: string;   label: string;   tournaments: ({   id: number;   title: string;   summary: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   registration_mode: string;   sjtu_only: boolean;   status: string;   phase: string;   approved_count: number; })[]; })[];
}

export function getApiTournaments(r: Requester, extras: CallExtras = {}): Promise<GetApiTournamentsOut> {
  return r<GetApiTournamentsOut>("GET", "/api/tournaments", { ...extras })
}

export interface GetApiTournamentsIdOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
  phase: string;
  phase_label: string;
  approved_teams: ({   registration_id: number;   team_id: number | null;   team_name: string;   member_count: number;   is_adhoc: boolean; })[];
  pool?: {   total: number;   tank: number;   damage: number;   support: number;   entries: {   signup_id: number;   user_id: number;   nickname: string;   roles: string[]; }[]; } | null;
  viewer: {   registration_open: boolean;   captain_teams: ({   team_id: number;   name: string;   registration: {   id: number;   status: string; } | null;   problems: string[]; })[];   on_roster: {   id: number;   status: string; } | null;   my_signup: {   id: number;   game_account_id: number | null;   roles: string[];   placed: boolean;   registration_id: number | null;   created_at: string; } | null;   individual_problems: string[];   is_manager: boolean; };
}

export function getApiTournamentsId(r: Requester, id: string | number, extras: CallExtras = {}): Promise<GetApiTournamentsIdOut> {
  return r<GetApiTournamentsIdOut>("GET", "/api/tournaments/{id}", { ...extras, params: { id } })
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

export function patchApiAdminCategoriesId(r: Requester, id: string | number, body: PatchApiAdminCategoriesIdIn, extras: CallExtras = {}): Promise<PatchApiAdminCategoriesIdOut> {
  return r<PatchApiAdminCategoriesIdOut>("PATCH", "/api/admin/categories/{id}", { ...extras, params: { id }, body })
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

export function patchApiAdminMemberGroupsId(r: Requester, id: string | number, body: PatchApiAdminMemberGroupsIdIn, extras: CallExtras = {}): Promise<PatchApiAdminMemberGroupsIdOut> {
  return r<PatchApiAdminMemberGroupsIdOut>("PATCH", "/api/admin/member-groups/{id}", { ...extras, params: { id }, body })
}

export interface PatchApiAdminScrimsIdIn {
  base_version: number;
  changes: {   title?: string | null;   description?: string | null;   starts_at?: string | null;   signup_closes_at?: string | null;   format?: string | null;   sjtu_only?: boolean | null; };
}

export interface PatchApiAdminScrimsIdOut {
  version: number;
  saved: string[];
  fields?: Record<string, string[]>;
  saved_at: string;
}

export function patchApiAdminScrimsId(r: Requester, id: string | number, body: PatchApiAdminScrimsIdIn, extras: CallExtras = {}): Promise<PatchApiAdminScrimsIdOut> {
  return r<PatchApiAdminScrimsIdOut>("PATCH", "/api/admin/scrims/{id}", { ...extras, params: { id }, body })
}

export interface PatchApiAdminSettingsIn {
  site_description?: string | null;
  from_name?: string | null;
  email_subject_prefix?: string | null;
  smtp_host?: string | null;
  smtp_port?: number | null;
  smtp_security?: string | null;
  smtp_username?: string | null;
  smtp_password?: string | null;
  clear_smtp_password?: boolean | null;
  from_address?: string | null;
  founded_on?: string | null;
  default_share_image_id?: number | null;
  hero_image_id?: number | null;
  banner_news_id?: number | null;
  banner_tournaments_id?: number | null;
  banner_scrims_id?: number | null;
  banner_teams_id?: number | null;
  banner_members_id?: number | null;
  qq_group_url?: string | null;
  team_max_members?: number | null;
  team_max_captained?: number | null;
  tournament_reminder_hours?: number | null;
  scrim_reminder_hours?: number | null;
  moderation_enabled?: boolean | null;
  moderation_provider?: string | null;
  moderation_api_key?: string | null;
  clear_moderation_api_key?: boolean | null;
  moderation_base_url?: string | null;
  moderation_model?: string | null;
  moderation_max_tokens?: number | null;
  moderation_timeout_seconds?: number | null;
  moderation_extra_params?: string | null;
  moderation_daily_limit?: number | null;
  moderation_notify_email?: string | null;
}

export interface PatchApiAdminSettingsOut {
  settings: {   id: number;   site_description: string;   from_name: string;   email_subject_prefix: string;   smtp_host: string;   smtp_port: number;   smtp_security: string;   smtp_username: string;   has_smtp_password: boolean;   from_address: string;   founded_on: string;   default_share_image_id: number | null;   hero_image_id: number | null;   banner_news_id: number | null;   banner_tournaments_id: number | null;   banner_scrims_id: number | null;   banner_teams_id: number | null;   banner_members_id: number | null;   qq_group_url: string;   team_max_members: number;   team_max_captained: number;   tournament_reminder_hours: number;   scrim_reminder_hours: number;   moderation_enabled: boolean;   moderation_configured: boolean;   moderation_provider: string;   has_moderation_api_key: boolean;   moderation_base_url: string;   moderation_model: string;   moderation_max_tokens: number;   moderation_timeout_seconds: number;   moderation_extra_params: string;   moderation_daily_limit: number;   moderation_notify_email: string;   version: number;   updated_at: string; } | null;
}

export function patchApiAdminSettings(r: Requester, body: PatchApiAdminSettingsIn, extras: CallExtras = {}): Promise<PatchApiAdminSettingsOut> {
  return r<PatchApiAdminSettingsOut>("PATCH", "/api/admin/settings", { ...extras, body })
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

export function patchApiAdminTeamsId(r: Requester, id: string | number, body: PatchApiAdminTeamsIdIn, extras: CallExtras = {}): Promise<PatchApiAdminTeamsIdOut> {
  return r<PatchApiAdminTeamsIdOut>("PATCH", "/api/admin/teams/{id}", { ...extras, params: { id }, body })
}

export interface PatchApiAdminTournamentsIdIn {
  base_version: number;
  changes: {   title?: string | null;   summary?: string | null;   description?: string | null;   cover_image_id?: number | null;   remove_cover?: boolean | null;   starts_at?: string | null;   registration_opens_at?: string | null;   registration_closes_at?: string | null;   roster_min?: number | null;   roster_max?: number | null;   sjtu_only?: boolean | null;   registration_mode?: string | null;   auto_approve?: boolean | null;   participant_contact?: string | null; };
}

export interface PatchApiAdminTournamentsIdOut {
  version: number;
  saved: string[];
  fields?: Record<string, string[]>;
  saved_at: string;
}

export function patchApiAdminTournamentsId(r: Requester, id: string | number, body: PatchApiAdminTournamentsIdIn, extras: CallExtras = {}): Promise<PatchApiAdminTournamentsIdOut> {
  return r<PatchApiAdminTournamentsIdOut>("PATCH", "/api/admin/tournaments/{id}", { ...extras, params: { id }, body })
}

export interface PatchApiAdminUsersIdRolesIn {
  roles: string[];
}

export interface PatchApiAdminUsersIdRolesOut {
  result: string;
  roles: string[];
  message: string;
}

export function patchApiAdminUsersIdRoles(r: Requester, id: string | number, body: PatchApiAdminUsersIdRolesIn, extras: CallExtras = {}): Promise<PatchApiAdminUsersIdRolesOut> {
  return r<PatchApiAdminUsersIdRolesOut>("PATCH", "/api/admin/users/{id}/roles", { ...extras, params: { id }, body })
}

export interface PatchApiAdminUsersIdRulesIn {
  rules: Record<string, boolean>;
}

export interface PatchApiAdminUsersIdRulesOut {
  result: string;
  message: string;
}

export function patchApiAdminUsersIdRules(r: Requester, id: string | number, body: PatchApiAdminUsersIdRulesIn, extras: CallExtras = {}): Promise<PatchApiAdminUsersIdRulesOut> {
  return r<PatchApiAdminUsersIdRulesOut>("PATCH", "/api/admin/users/{id}/rules", { ...extras, params: { id }, body })
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

export function patchApiArticlesId(r: Requester, id: string | number, body: PatchApiArticlesIdIn, extras: CallExtras = {}): Promise<PatchApiArticlesIdOut> {
  return r<PatchApiArticlesIdOut>("PATCH", "/api/articles/{id}", { ...extras, params: { id }, body })
}

export interface PatchApiCommentsIdIn {
  content: string;
}

export interface PatchApiCommentsIdOut {
  comment: {   id: number;   article_id: number;   user_id?: number | null;   author_name: string;   parent_id?: number | null;   reply_to_user_id?: number | null;   reply_to_user_name?: string;   content: string;   is_pinned: boolean;   is_hidden: boolean;   is_deleted: boolean;   is_tombstone?: boolean;   like_count: number;   liked_by_me?: boolean;   reply_count?: number;   replies?: (unknown | null)[];   version: number;   created_at: string;   updated_at: string;   edited_at: string | null; } | null;
}

export function patchApiCommentsId(r: Requester, id: string | number, body: PatchApiCommentsIdIn, extras: CallExtras = {}): Promise<PatchApiCommentsIdOut> {
  return r<PatchApiCommentsIdOut>("PATCH", "/api/comments/{id}", { ...extras, params: { id }, body })
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

export function patchApiMeGameAccountsId(r: Requester, id: string | number, body: PatchApiMeGameAccountsIdIn, extras: CallExtras = {}): Promise<PatchApiMeGameAccountsIdOut> {
  return r<PatchApiMeGameAccountsIdOut>("PATCH", "/api/me/game-accounts/{id}", { ...extras, params: { id }, body })
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

export function patchApiMeProfile(r: Requester, body: PatchApiMeProfileIn, extras: CallExtras = {}): Promise<PatchApiMeProfileOut> {
  return r<PatchApiMeProfileOut>("PATCH", "/api/me/profile", { ...extras, body })
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

export function patchApiTeamsId(r: Requester, id: string | number, body: PatchApiTeamsIdIn, extras: CallExtras = {}): Promise<PatchApiTeamsIdOut> {
  return r<PatchApiTeamsIdOut>("PATCH", "/api/teams/{id}", { ...extras, params: { id }, body })
}

export interface PostApiAdminAnnounceKindIdOut {
  broadcast_id: number;
  recipients: number;
  waiting: boolean;
}

export function postApiAdminAnnounceKindId(r: Requester, kind: string | number, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminAnnounceKindIdOut> {
  return r<PostApiAdminAnnounceKindIdOut>("POST", "/api/admin/announce/{kind}/{id}", { ...extras, params: { kind, id } })
}

export interface PostApiAdminAvatarsIdTakeDownIn {
  note: string;
}

export interface PostApiAdminAvatarsIdTakeDownOut {
  result: string;
}

export function postApiAdminAvatarsIdTakeDown(r: Requester, id: string | number, body: PostApiAdminAvatarsIdTakeDownIn, extras: CallExtras = {}): Promise<PostApiAdminAvatarsIdTakeDownOut> {
  return r<PostApiAdminAvatarsIdTakeDownOut>("POST", "/api/admin/avatars/{id}/take-down", { ...extras, params: { id }, body })
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

export function postApiAdminCategories(r: Requester, body: PostApiAdminCategoriesIn, extras: CallExtras = {}): Promise<PostApiAdminCategoriesOut> {
  return r<PostApiAdminCategoriesOut>("POST", "/api/admin/categories", { ...extras, body })
}

export interface PostApiAdminImagesUploadIn {
  title: string;
  collection_key: string;
  file_name: string;
  data_url: string;
}

export interface PostApiAdminImagesUploadOut {
  image: {   id: number;   collection_id: number | null;   title: string;   file_name: string;   file_size: number;   width: number;   height: number;   uploader_id: number | null;   created_at: string;   version: number; } | null;
}

export function postApiAdminImagesUpload(r: Requester, body: PostApiAdminImagesUploadIn, extras: CallExtras = {}): Promise<PostApiAdminImagesUploadOut> {
  return r<PostApiAdminImagesUploadOut>("POST", "/api/admin/images/upload", { ...extras, body })
}

export interface PostApiAdminMemberGroupPeopleIdMoveIn {
  step: number;
}

export interface PostApiAdminMemberGroupPeopleIdMoveOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function postApiAdminMemberGroupPeopleIdMove(r: Requester, id: string | number, body: PostApiAdminMemberGroupPeopleIdMoveIn, extras: CallExtras = {}): Promise<PostApiAdminMemberGroupPeopleIdMoveOut> {
  return r<PostApiAdminMemberGroupPeopleIdMoveOut>("POST", "/api/admin/member-group-people/{id}/move", { ...extras, params: { id }, body })
}

export interface PostApiAdminMemberGroupPeopleIdTitleIn {
  title: string;
}

export interface PostApiAdminMemberGroupPeopleIdTitleOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function postApiAdminMemberGroupPeopleIdTitle(r: Requester, id: string | number, body: PostApiAdminMemberGroupPeopleIdTitleIn, extras: CallExtras = {}): Promise<PostApiAdminMemberGroupPeopleIdTitleOut> {
  return r<PostApiAdminMemberGroupPeopleIdTitleOut>("POST", "/api/admin/member-group-people/{id}/title", { ...extras, params: { id }, body })
}

export interface PostApiAdminMemberGroupsOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminMemberGroups(r: Requester, extras: CallExtras = {}): Promise<PostApiAdminMemberGroupsOut> {
  return r<PostApiAdminMemberGroupsOut>("POST", "/api/admin/member-groups", { ...extras })
}

export interface PostApiAdminMemberGroupsIdPeopleIn {
  user_id: number;
}

export interface PostApiAdminMemberGroupsIdPeopleOut {
  group: {   id: number;   name: string;   description: string;   is_visible: boolean;   sort_order: number;   version: number;   created_at: string;   updated_at: string; };
  members: {   id: number;   user_id: number;   nickname: string;   email?: string;   title: string;   sort_order: number;   joined: boolean; }[];
}

export function postApiAdminMemberGroupsIdPeople(r: Requester, id: string | number, body: PostApiAdminMemberGroupsIdPeopleIn, extras: CallExtras = {}): Promise<PostApiAdminMemberGroupsIdPeopleOut> {
  return r<PostApiAdminMemberGroupsIdPeopleOut>("POST", "/api/admin/member-groups/{id}/people", { ...extras, params: { id }, body })
}

export interface PostApiAdminModerationIdAskAuthorIn {
  message: string;
}

export interface PostApiAdminModerationIdAskAuthorOut {
  item: {   id: number;   target_type: string;   target_label: string;   target_id: number;   field: string;   url: string;   author_id: number | null;   excerpt: string;   full_text?: string;   text_hash: string;   risk: string;   categories: string[];   reason: string;   quote: string;   status: string;   reviewed_by: number | null;   reviewed_at: string | null;   handling_note: string;   checked_at: string | null;   notified_at: string | null;   attempts: number;   last_error: string;   failed_at: string | null;   created_at: string; } | null;
}

export function postApiAdminModerationIdAskAuthor(r: Requester, id: string | number, body: PostApiAdminModerationIdAskAuthorIn, extras: CallExtras = {}): Promise<PostApiAdminModerationIdAskAuthorOut> {
  return r<PostApiAdminModerationIdAskAuthorOut>("POST", "/api/admin/moderation/{id}/ask-author", { ...extras, params: { id }, body })
}

export interface PostApiAdminModerationIdHandleIn {
  action: string;
  note: string;
}

export interface PostApiAdminModerationIdHandleOut {
  item: {   id: number;   target_type: string;   target_label: string;   target_id: number;   field: string;   url: string;   author_id: number | null;   excerpt: string;   full_text?: string;   text_hash: string;   risk: string;   categories: string[];   reason: string;   quote: string;   status: string;   reviewed_by: number | null;   reviewed_at: string | null;   handling_note: string;   checked_at: string | null;   notified_at: string | null;   attempts: number;   last_error: string;   failed_at: string | null;   created_at: string; } | null;
}

export function postApiAdminModerationIdHandle(r: Requester, id: string | number, body: PostApiAdminModerationIdHandleIn, extras: CallExtras = {}): Promise<PostApiAdminModerationIdHandleOut> {
  return r<PostApiAdminModerationIdHandleOut>("POST", "/api/admin/moderation/{id}/handle", { ...extras, params: { id }, body })
}

export interface PostApiAdminRegistrationsIdApproveOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminRegistrationsIdApprove(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminRegistrationsIdApproveOut> {
  return r<PostApiAdminRegistrationsIdApproveOut>("POST", "/api/admin/registrations/{id}/approve", { ...extras, params: { id } })
}

export interface PostApiAdminRegistrationsIdDissolveOut {
  result: string;
}

export function postApiAdminRegistrationsIdDissolve(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminRegistrationsIdDissolveOut> {
  return r<PostApiAdminRegistrationsIdDissolveOut>("POST", "/api/admin/registrations/{id}/dissolve", { ...extras, params: { id } })
}

export interface PostApiAdminRegistrationsIdRejectIn {
  note: string;
}

export interface PostApiAdminRegistrationsIdRejectOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminRegistrationsIdReject(r: Requester, id: string | number, body: PostApiAdminRegistrationsIdRejectIn, extras: CallExtras = {}): Promise<PostApiAdminRegistrationsIdRejectOut> {
  return r<PostApiAdminRegistrationsIdRejectOut>("POST", "/api/admin/registrations/{id}/reject", { ...extras, params: { id }, body })
}

export interface PostApiAdminScrimsOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrims(r: Requester, extras: CallExtras = {}): Promise<PostApiAdminScrimsOut> {
  return r<PostApiAdminScrimsOut>("POST", "/api/admin/scrims", { ...extras })
}

export interface PostApiAdminScrimsIdBoardGenerateIn {
  signup_ids: number[];
  base_board_version: number;
}

export interface PostApiAdminScrimsIdBoardGenerateOut {
  board: {   scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;   order: string;   signups: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[];   selected_count: number;   needed: number;   teams: ({   team: string;   label: string;   total: number;   problems: string[];   members: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[]; })[];   bench: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[];   gap: number;   has_teams: boolean;   teams_stale: boolean;   copy_text: string;   board_version: number;   warnings?: string[]; } | null;
  score: number[];
  unrated: string[];
}

export function postApiAdminScrimsIdBoardGenerate(r: Requester, id: string | number, body: PostApiAdminScrimsIdBoardGenerateIn, extras: CallExtras = {}): Promise<PostApiAdminScrimsIdBoardGenerateOut> {
  return r<PostApiAdminScrimsIdBoardGenerateOut>("POST", "/api/admin/scrims/{id}/board/generate", { ...extras, params: { id }, body })
}

export interface PostApiAdminScrimsIdBoardSelectionIn {
  signup_ids: number[];
  base_board_version: number;
}

export interface PostApiAdminScrimsIdBoardSelectionOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  order: string;
  signups: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[];
  selected_count: number;
  needed: number;
  teams: ({   team: string;   label: string;   total: number;   problems: string[];   members: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[]; })[];
  bench: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[];
  gap: number;
  has_teams: boolean;
  teams_stale: boolean;
  copy_text: string;
  board_version: number;
  warnings?: string[];
}

export function postApiAdminScrimsIdBoardSelection(r: Requester, id: string | number, body: PostApiAdminScrimsIdBoardSelectionIn, extras: CallExtras = {}): Promise<PostApiAdminScrimsIdBoardSelectionOut> {
  return r<PostApiAdminScrimsIdBoardSelectionOut>("POST", "/api/admin/scrims/{id}/board/selection", { ...extras, params: { id }, body })
}

export interface PostApiAdminScrimsIdBoardTeamsIn {
  placements: {   signup_id: number;   team: string;   role: string; }[];
  base_board_version: number;
}

export interface PostApiAdminScrimsIdBoardTeamsOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  order: string;
  signups: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[];
  selected_count: number;
  needed: number;
  teams: ({   team: string;   label: string;   total: number;   problems: string[];   members: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[]; })[];
  bench: ({   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; })[];
  gap: number;
  has_teams: boolean;
  teams_stale: boolean;
  copy_text: string;
  board_version: number;
  warnings?: string[];
}

export function postApiAdminScrimsIdBoardTeams(r: Requester, id: string | number, body: PostApiAdminScrimsIdBoardTeamsIn, extras: CallExtras = {}): Promise<PostApiAdminScrimsIdBoardTeamsOut> {
  return r<PostApiAdminScrimsIdBoardTeamsOut>("POST", "/api/admin/scrims/{id}/board/teams", { ...extras, params: { id }, body })
}

export interface PostApiAdminScrimsIdCancelOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrimsIdCancel(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminScrimsIdCancelOut> {
  return r<PostApiAdminScrimsIdCancelOut>("POST", "/api/admin/scrims/{id}/cancel", { ...extras, params: { id } })
}

export interface PostApiAdminScrimsIdCopyOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrimsIdCopy(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminScrimsIdCopyOut> {
  return r<PostApiAdminScrimsIdCopyOut>("POST", "/api/admin/scrims/{id}/copy", { ...extras, params: { id } })
}

export interface PostApiAdminScrimsIdFinishOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrimsIdFinish(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminScrimsIdFinishOut> {
  return r<PostApiAdminScrimsIdFinishOut>("POST", "/api/admin/scrims/{id}/finish", { ...extras, params: { id } })
}

export interface PostApiAdminScrimsIdNotifyIn {
  note: string;
}

export interface PostApiAdminScrimsIdNotifyOut {
  recipients: number;
}

export function postApiAdminScrimsIdNotify(r: Requester, id: string | number, body: PostApiAdminScrimsIdNotifyIn, extras: CallExtras = {}): Promise<PostApiAdminScrimsIdNotifyOut> {
  return r<PostApiAdminScrimsIdNotifyOut>("POST", "/api/admin/scrims/{id}/notify", { ...extras, params: { id }, body })
}

export interface PostApiAdminScrimsIdPublishOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrimsIdPublish(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminScrimsIdPublishOut> {
  return r<PostApiAdminScrimsIdPublishOut>("POST", "/api/admin/scrims/{id}/publish", { ...extras, params: { id } })
}

export interface PostApiAdminSettingsTestEmailOut {
  result: string;
  message: string;
}

export function postApiAdminSettingsTestEmail(r: Requester, extras: CallExtras = {}): Promise<PostApiAdminSettingsTestEmailOut> {
  return r<PostApiAdminSettingsTestEmailOut>("POST", "/api/admin/settings/test-email", { ...extras })
}

export interface PostApiAdminTeamsIdAssignCaptainIn {
  user_id: number;
}

export interface PostApiAdminTeamsIdAssignCaptainOut {
  result: string;
}

export function postApiAdminTeamsIdAssignCaptain(r: Requester, id: string | number, body: PostApiAdminTeamsIdAssignCaptainIn, extras: CallExtras = {}): Promise<PostApiAdminTeamsIdAssignCaptainOut> {
  return r<PostApiAdminTeamsIdAssignCaptainOut>("POST", "/api/admin/teams/{id}/assign-captain", { ...extras, params: { id }, body })
}

export interface PostApiAdminTeamsIdDisbandOut {
  result: string;
}

export function postApiAdminTeamsIdDisband(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminTeamsIdDisbandOut> {
  return r<PostApiAdminTeamsIdDisbandOut>("POST", "/api/admin/teams/{id}/disband", { ...extras, params: { id } })
}

export interface PostApiAdminTournamentsOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournaments(r: Requester, extras: CallExtras = {}): Promise<PostApiAdminTournamentsOut> {
  return r<PostApiAdminTournamentsOut>("POST", "/api/admin/tournaments", { ...extras })
}

export interface PostApiAdminTournamentsIdBoardIn {
  teams: ({   registration_id: number | null;   name: string;   signup_ids: number[];   base_version: number; })[];
}

export interface PostApiAdminTournamentsIdBoardOut {
  created: number;
  updated: number;
  dissolved: number;
  returned: number;
}

export function postApiAdminTournamentsIdBoard(r: Requester, id: string | number, body: PostApiAdminTournamentsIdBoardIn, extras: CallExtras = {}): Promise<PostApiAdminTournamentsIdBoardOut> {
  return r<PostApiAdminTournamentsIdBoardOut>("POST", "/api/admin/tournaments/{id}/board", { ...extras, params: { id }, body })
}

export interface PostApiAdminTournamentsIdCancelIn {
  reason: string;
}

export interface PostApiAdminTournamentsIdCancelOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournamentsIdCancel(r: Requester, id: string | number, body: PostApiAdminTournamentsIdCancelIn, extras: CallExtras = {}): Promise<PostApiAdminTournamentsIdCancelOut> {
  return r<PostApiAdminTournamentsIdCancelOut>("POST", "/api/admin/tournaments/{id}/cancel", { ...extras, params: { id }, body })
}

export interface PostApiAdminTournamentsIdCopyOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournamentsIdCopy(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminTournamentsIdCopyOut> {
  return r<PostApiAdminTournamentsIdCopyOut>("POST", "/api/admin/tournaments/{id}/copy", { ...extras, params: { id } })
}

export interface PostApiAdminTournamentsIdFinishOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournamentsIdFinish(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminTournamentsIdFinishOut> {
  return r<PostApiAdminTournamentsIdFinishOut>("POST", "/api/admin/tournaments/{id}/finish", { ...extras, params: { id } })
}

export interface PostApiAdminTournamentsIdNotifyIn {
  note: string;
}

export interface PostApiAdminTournamentsIdNotifyOut {
  recipients: number;
}

export function postApiAdminTournamentsIdNotify(r: Requester, id: string | number, body: PostApiAdminTournamentsIdNotifyIn, extras: CallExtras = {}): Promise<PostApiAdminTournamentsIdNotifyOut> {
  return r<PostApiAdminTournamentsIdNotifyOut>("POST", "/api/admin/tournaments/{id}/notify", { ...extras, params: { id }, body })
}

export interface PostApiAdminTournamentsIdPublishOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournamentsIdPublish(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminTournamentsIdPublishOut> {
  return r<PostApiAdminTournamentsIdPublishOut>("POST", "/api/admin/tournaments/{id}/publish", { ...extras, params: { id } })
}

export interface PostApiAdminUsersIdActivateOut {
  result: string;
  message: string;
}

export function postApiAdminUsersIdActivate(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiAdminUsersIdActivateOut> {
  return r<PostApiAdminUsersIdActivateOut>("POST", "/api/admin/users/{id}/activate", { ...extras, params: { id } })
}

export interface PostApiAdminUsersIdDeactivateIn {
  reason: string;
}

export interface PostApiAdminUsersIdDeactivateOut {
  result: string;
  message: string;
}

export function postApiAdminUsersIdDeactivate(r: Requester, id: string | number, body: PostApiAdminUsersIdDeactivateIn, extras: CallExtras = {}): Promise<PostApiAdminUsersIdDeactivateOut> {
  return r<PostApiAdminUsersIdDeactivateOut>("POST", "/api/admin/users/{id}/deactivate", { ...extras, params: { id }, body })
}

export interface PostApiAnnouncementsUnsubscribeTokenOut {
  nickname?: string;
  accepts: boolean;
}

export function postApiAnnouncementsUnsubscribeToken(r: Requester, token: string | number, extras: CallExtras = {}): Promise<PostApiAnnouncementsUnsubscribeTokenOut> {
  return r<PostApiAnnouncementsUnsubscribeTokenOut>("POST", "/api/announcements/unsubscribe/{token}", { ...extras, params: { token } })
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

export function postApiArticles(r: Requester, body: PostApiArticlesIn, extras: CallExtras = {}): Promise<PostApiArticlesOut> {
  return r<PostApiArticlesOut>("POST", "/api/articles", { ...extras, body })
}

export interface PostApiArticlesIdCommentsIn {
  parent_id?: number | null;
  content: string;
}

export interface PostApiArticlesIdCommentsOut {
  comment: {   id: number;   article_id: number;   user_id?: number | null;   author_name: string;   parent_id?: number | null;   reply_to_user_id?: number | null;   reply_to_user_name?: string;   content: string;   is_pinned: boolean;   is_hidden: boolean;   is_deleted: boolean;   is_tombstone?: boolean;   like_count: number;   liked_by_me?: boolean;   reply_count?: number;   replies?: (unknown | null)[];   version: number;   created_at: string;   updated_at: string;   edited_at: string | null; } | null;
}

export function postApiArticlesIdComments(r: Requester, id: string | number, body: PostApiArticlesIdCommentsIn, extras: CallExtras = {}): Promise<PostApiArticlesIdCommentsOut> {
  return r<PostApiArticlesIdCommentsOut>("POST", "/api/articles/{id}/comments", { ...extras, params: { id }, body })
}

export interface PostApiArticlesIdPublishIn {
  base_version: number;
}

export interface PostApiArticlesIdPublishOut {
  article: {   id: number;   kind: string;   slug: string;   title: string;   live: boolean;   has_unpublished_changes: boolean;   go_live_at?: string | null;   expire_at?: string | null;   first_published_at?: string | null;   last_published_at?: string | null;   live_revision_id?: number | null;   latest_revision_id?: number | null;   owner_id?: number | null;   seo_title: string;   search_description: string;   version: number;   created_at: string;   updated_at: string;   category_id?: number | null;   category_name?: string;   cover_image_id?: number | null;   summary: string;   body_md: string;   body_html: string;   body_plain: string;   char_count: number;   reading_time: number;   author_id?: number | null;   author_name?: string;   comments_enabled: boolean;   related_tournament_id?: number | null;   search_text: string;   renderer_version: number; } | null;
}

export function postApiArticlesIdPublish(r: Requester, id: string | number, body: PostApiArticlesIdPublishIn, extras: CallExtras = {}): Promise<PostApiArticlesIdPublishOut> {
  return r<PostApiArticlesIdPublishOut>("POST", "/api/articles/{id}/publish", { ...extras, params: { id }, body })
}

export interface PostApiArticlesIdUnpublishOut {
  result: string;
}

export function postApiArticlesIdUnpublish(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiArticlesIdUnpublishOut> {
  return r<PostApiArticlesIdUnpublishOut>("POST", "/api/articles/{id}/unpublish", { ...extras, params: { id } })
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

export function postApiAuthChangePassword(r: Requester, body: PostApiAuthChangePasswordIn, extras: CallExtras = {}): Promise<PostApiAuthChangePasswordOut> {
  return r<PostApiAuthChangePasswordOut>("POST", "/api/auth/change-password", { ...extras, body })
}

export interface PostApiAuthDeleteAccountIn {
  password: string;
}

export interface PostApiAuthDeleteAccountOut {
  result: string;
  message: string;
}

export function postApiAuthDeleteAccount(r: Requester, body: PostApiAuthDeleteAccountIn, extras: CallExtras = {}): Promise<PostApiAuthDeleteAccountOut> {
  return r<PostApiAuthDeleteAccountOut>("POST", "/api/auth/delete-account", { ...extras, body })
}

export interface PostApiAuthEmailChangeIn {
  new_email: string;
}

export interface PostApiAuthEmailChangeOut {
  result: string;
  message: string;
}

export function postApiAuthEmailChange(r: Requester, body: PostApiAuthEmailChangeIn, extras: CallExtras = {}): Promise<PostApiAuthEmailChangeOut> {
  return r<PostApiAuthEmailChangeOut>("POST", "/api/auth/email/change", { ...extras, body })
}

export interface PostApiAuthEmailChangeConfirmIn {
  code: string;
}

export interface PostApiAuthEmailChangeConfirmOut {
  result: string;
  message: string;
}

export function postApiAuthEmailChangeConfirm(r: Requester, body: PostApiAuthEmailChangeConfirmIn, extras: CallExtras = {}): Promise<PostApiAuthEmailChangeConfirmOut> {
  return r<PostApiAuthEmailChangeConfirmOut>("POST", "/api/auth/email/change/confirm", { ...extras, body })
}

export interface PostApiAuthLoginIn {
  email: string;
  password: string;
}

export interface PostApiAuthLoginOut {
  result: string;
  message: string;
}

export function postApiAuthLogin(r: Requester, body: PostApiAuthLoginIn, extras: CallExtras = {}): Promise<PostApiAuthLoginOut> {
  return r<PostApiAuthLoginOut>("POST", "/api/auth/login", { ...extras, body })
}

export interface PostApiAuthLogoutOut {
  result: string;
  message: string;
}

export function postApiAuthLogout(r: Requester, extras: CallExtras = {}): Promise<PostApiAuthLogoutOut> {
  return r<PostApiAuthLogoutOut>("POST", "/api/auth/logout", { ...extras })
}

export interface PostApiAuthReauthenticateIn {
  password: string;
}

export interface PostApiAuthReauthenticateOut {
  result: string;
  message: string;
}

export function postApiAuthReauthenticate(r: Requester, body: PostApiAuthReauthenticateIn, extras: CallExtras = {}): Promise<PostApiAuthReauthenticateOut> {
  return r<PostApiAuthReauthenticateOut>("POST", "/api/auth/reauthenticate", { ...extras, body })
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

export function postApiAuthRegister(r: Requester, body: PostApiAuthRegisterIn, extras: CallExtras = {}): Promise<PostApiAuthRegisterOut> {
  return r<PostApiAuthRegisterOut>("POST", "/api/auth/register", { ...extras, body })
}

export interface PostApiAuthResendCodeIn {
  email: string;
}

export interface PostApiAuthResendCodeOut {
  email: string;
  message: string;
}

export function postApiAuthResendCode(r: Requester, body: PostApiAuthResendCodeIn, extras: CallExtras = {}): Promise<PostApiAuthResendCodeOut> {
  return r<PostApiAuthResendCodeOut>("POST", "/api/auth/resend-code", { ...extras, body })
}

export interface PostApiAuthResetPasswordIn {
  email: string;
}

export interface PostApiAuthResetPasswordOut {
  email: string;
  message: string;
}

export function postApiAuthResetPassword(r: Requester, body: PostApiAuthResetPasswordIn, extras: CallExtras = {}): Promise<PostApiAuthResetPasswordOut> {
  return r<PostApiAuthResetPasswordOut>("POST", "/api/auth/reset-password", { ...extras, body })
}

export interface PostApiAuthResetPasswordCompleteIn {
  password: string;
  confirm_password: string;
}

export interface PostApiAuthResetPasswordCompleteOut {
  Result: string;
  Message: string;
}

export function postApiAuthResetPasswordComplete(r: Requester, body: PostApiAuthResetPasswordCompleteIn, extras: CallExtras = {}): Promise<PostApiAuthResetPasswordCompleteOut> {
  return r<PostApiAuthResetPasswordCompleteOut>("POST", "/api/auth/reset-password/complete", { ...extras, body })
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

export function postApiAuthResetPasswordConfirm(r: Requester, body: PostApiAuthResetPasswordConfirmIn, extras: CallExtras = {}): Promise<PostApiAuthResetPasswordConfirmOut> {
  return r<PostApiAuthResetPasswordConfirmOut>("POST", "/api/auth/reset-password/confirm", { ...extras, body })
}

export interface PostApiAuthResetPasswordVerifyIn {
  email: string;
  code: string;
}

export interface PostApiAuthResetPasswordVerifyOut {
  result: string;
  message: string;
}

export function postApiAuthResetPasswordVerify(r: Requester, body: PostApiAuthResetPasswordVerifyIn, extras: CallExtras = {}): Promise<PostApiAuthResetPasswordVerifyOut> {
  return r<PostApiAuthResetPasswordVerifyOut>("POST", "/api/auth/reset-password/verify", { ...extras, body })
}

export interface PostApiAuthVerifyEmailIn {
  email: string;
  code: string;
}

export interface PostApiAuthVerifyEmailOut {
  result: string;
  message: string;
}

export function postApiAuthVerifyEmail(r: Requester, body: PostApiAuthVerifyEmailIn, extras: CallExtras = {}): Promise<PostApiAuthVerifyEmailOut> {
  return r<PostApiAuthVerifyEmailOut>("POST", "/api/auth/verify-email", { ...extras, body })
}

export interface PostApiCommentsIdHideIn {
  hidden: boolean;
}

export interface PostApiCommentsIdHideOut {
  result: string;
}

export function postApiCommentsIdHide(r: Requester, id: string | number, body: PostApiCommentsIdHideIn, extras: CallExtras = {}): Promise<PostApiCommentsIdHideOut> {
  return r<PostApiCommentsIdHideOut>("POST", "/api/comments/{id}/hide", { ...extras, params: { id }, body })
}

export interface PostApiCommentsIdLikeOut {
  liked: boolean;
  like_count: number;
}

export function postApiCommentsIdLike(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiCommentsIdLikeOut> {
  return r<PostApiCommentsIdLikeOut>("POST", "/api/comments/{id}/like", { ...extras, params: { id } })
}

export interface PostApiCommentsIdPinIn {
  article_id: number;
  pinned: boolean;
}

export interface PostApiCommentsIdPinOut {
  result: string;
}

export function postApiCommentsIdPin(r: Requester, id: string | number, body: PostApiCommentsIdPinIn, extras: CallExtras = {}): Promise<PostApiCommentsIdPinOut> {
  return r<PostApiCommentsIdPinOut>("POST", "/api/comments/{id}/pin", { ...extras, params: { id }, body })
}

export interface PostApiLettersBatchIn {
  send: number[];
  skip: boolean;
}

export interface PostApiLettersBatchOut {
  letters: number;
  people: number;
}

export function postApiLettersBatch(r: Requester, batch: string | number, body: PostApiLettersBatchIn, extras: CallExtras = {}): Promise<PostApiLettersBatchOut> {
  return r<PostApiLettersBatchOut>("POST", "/api/letters/{batch}", { ...extras, params: { batch }, body })
}

export interface PostApiMeAnnouncementsIn {
  accepts: boolean;
}

export interface PostApiMeAnnouncementsOut {
  nickname?: string;
  accepts: boolean;
}

export function postApiMeAnnouncements(r: Requester, body: PostApiMeAnnouncementsIn, extras: CallExtras = {}): Promise<PostApiMeAnnouncementsOut> {
  return r<PostApiMeAnnouncementsOut>("POST", "/api/me/announcements", { ...extras, body })
}

export interface PostApiMeAvatarIn {
  file_name: string;
  data_url: string;
}

export interface PostApiMeAvatarOut {
  image: {   id: number;   collection_id: number | null;   title: string;   file_name: string;   file_size: number;   width: number;   height: number;   uploader_id: number | null;   created_at: string;   version: number; } | null;
}

export function postApiMeAvatar(r: Requester, body: PostApiMeAvatarIn, extras: CallExtras = {}): Promise<PostApiMeAvatarOut> {
  return r<PostApiMeAvatarOut>("POST", "/api/me/avatar", { ...extras, body })
}

export interface PostApiMeCalendarRenewOut {
  url: string;
  webcal: string;
}

export function postApiMeCalendarRenew(r: Requester, extras: CallExtras = {}): Promise<PostApiMeCalendarRenewOut> {
  return r<PostApiMeCalendarRenewOut>("POST", "/api/me/calendar/renew", { ...extras })
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

export function postApiMeContacts(r: Requester, body: PostApiMeContactsIn, extras: CallExtras = {}): Promise<PostApiMeContactsOut> {
  return r<PostApiMeContactsOut>("POST", "/api/me/contacts", { ...extras, body })
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

export function postApiMeGameAccounts(r: Requester, body: PostApiMeGameAccountsIn, extras: CallExtras = {}): Promise<PostApiMeGameAccountsOut> {
  return r<PostApiMeGameAccountsOut>("POST", "/api/me/game-accounts", { ...extras, body })
}

export interface PostApiRegistrationsIdLeaveOut {
  dissolved: boolean;
}

export function postApiRegistrationsIdLeave(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiRegistrationsIdLeaveOut> {
  return r<PostApiRegistrationsIdLeaveOut>("POST", "/api/registrations/{id}/leave", { ...extras, params: { id } })
}

export interface PostApiRegistrationsIdWithdrawOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
}

export function postApiRegistrationsIdWithdraw(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiRegistrationsIdWithdrawOut> {
  return r<PostApiRegistrationsIdWithdrawOut>("POST", "/api/registrations/{id}/withdraw", { ...extras, params: { id } })
}

export interface PostApiScrimsIdSignupIn {
  game_account_id: number;
  roles: string[];
}

export interface PostApiScrimsIdSignupOut {
  signup_id: number;
  roles: string[];
}

export function postApiScrimsIdSignup(r: Requester, id: string | number, body: PostApiScrimsIdSignupIn, extras: CallExtras = {}): Promise<PostApiScrimsIdSignupOut> {
  return r<PostApiScrimsIdSignupOut>("POST", "/api/scrims/{id}/signup", { ...extras, params: { id }, body })
}

export interface PostApiTeamAlumniIdRemoveOut {
  result: string;
}

export function postApiTeamAlumniIdRemove(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiTeamAlumniIdRemoveOut> {
  return r<PostApiTeamAlumniIdRemoveOut>("POST", "/api/team-alumni/{id}/remove", { ...extras, params: { id } })
}

export interface PostApiTeamApplicationsIdApproveOut {
  application: {   id: number;   team_id: number;   applicant_id: number;   role_tank: boolean;   role_damage: boolean;   role_support: boolean;   message: string;   status: string;   decided_by?: number | null;   decided_at?: string | null;   decision_note: string;   captain_reminded_at?: string | null;   created_at: string; } | null;
}

export function postApiTeamApplicationsIdApprove(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiTeamApplicationsIdApproveOut> {
  return r<PostApiTeamApplicationsIdApproveOut>("POST", "/api/team-applications/{id}/approve", { ...extras, params: { id } })
}

export interface PostApiTeamApplicationsIdCancelOut {
  application: {   id: number;   team_id: number;   applicant_id: number;   role_tank: boolean;   role_damage: boolean;   role_support: boolean;   message: string;   status: string;   decided_by?: number | null;   decided_at?: string | null;   decision_note: string;   captain_reminded_at?: string | null;   created_at: string; } | null;
}

export function postApiTeamApplicationsIdCancel(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiTeamApplicationsIdCancelOut> {
  return r<PostApiTeamApplicationsIdCancelOut>("POST", "/api/team-applications/{id}/cancel", { ...extras, params: { id } })
}

export interface PostApiTeamApplicationsIdRejectIn {
  note: string;
}

export interface PostApiTeamApplicationsIdRejectOut {
  application: {   id: number;   team_id: number;   applicant_id: number;   role_tank: boolean;   role_damage: boolean;   role_support: boolean;   message: string;   status: string;   decided_by?: number | null;   decided_at?: string | null;   decision_note: string;   captain_reminded_at?: string | null;   created_at: string; } | null;
}

export function postApiTeamApplicationsIdReject(r: Requester, id: string | number, body: PostApiTeamApplicationsIdRejectIn, extras: CallExtras = {}): Promise<PostApiTeamApplicationsIdRejectOut> {
  return r<PostApiTeamApplicationsIdRejectOut>("POST", "/api/team-applications/{id}/reject", { ...extras, params: { id }, body })
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

export function postApiTeams(r: Requester, body: PostApiTeamsIn, extras: CallExtras = {}): Promise<PostApiTeamsOut> {
  return r<PostApiTeamsOut>("POST", "/api/teams", { ...extras, body })
}

export interface PostApiTeamsIdApplicationsIn {
  roles: string[];
  message: string;
}

export interface PostApiTeamsIdApplicationsOut {
  application: {   id: number;   team_id: number;   applicant_id: number;   role_tank: boolean;   role_damage: boolean;   role_support: boolean;   message: string;   status: string;   decided_by?: number | null;   decided_at?: string | null;   decision_note: string;   captain_reminded_at?: string | null;   created_at: string; } | null;
}

export function postApiTeamsIdApplications(r: Requester, id: string | number, body: PostApiTeamsIdApplicationsIn, extras: CallExtras = {}): Promise<PostApiTeamsIdApplicationsOut> {
  return r<PostApiTeamsIdApplicationsOut>("POST", "/api/teams/{id}/applications", { ...extras, params: { id }, body })
}

export interface PostApiTeamsIdDisbandOut {
  result: string;
}

export function postApiTeamsIdDisband(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiTeamsIdDisbandOut> {
  return r<PostApiTeamsIdDisbandOut>("POST", "/api/teams/{id}/disband", { ...extras, params: { id } })
}

export interface PostApiTeamsIdLeaveOut {
  result: string;
}

export function postApiTeamsIdLeave(r: Requester, id: string | number, extras: CallExtras = {}): Promise<PostApiTeamsIdLeaveOut> {
  return r<PostApiTeamsIdLeaveOut>("POST", "/api/teams/{id}/leave", { ...extras, params: { id } })
}

export interface PostApiTeamsIdLogoIn {
  file_name: string;
  data_url: string;
}

export interface PostApiTeamsIdLogoOut {
  image: {   id: number;   collection_id: number | null;   title: string;   file_name: string;   file_size: number;   width: number;   height: number;   uploader_id: number | null;   created_at: string;   version: number; } | null;
}

export function postApiTeamsIdLogo(r: Requester, id: string | number, body: PostApiTeamsIdLogoIn, extras: CallExtras = {}): Promise<PostApiTeamsIdLogoOut> {
  return r<PostApiTeamsIdLogoOut>("POST", "/api/teams/{id}/logo", { ...extras, params: { id }, body })
}

export interface PostApiTeamsIdMembersUser_idRemoveOut {
  result: string;
}

export function postApiTeamsIdMembersUser_idRemove(r: Requester, id: string | number, user_id: string | number, extras: CallExtras = {}): Promise<PostApiTeamsIdMembersUser_idRemoveOut> {
  return r<PostApiTeamsIdMembersUser_idRemoveOut>("POST", "/api/teams/{id}/members/{user_id}/remove", { ...extras, params: { id, user_id } })
}

export interface PostApiTeamsIdTransferIn {
  user_id: number;
}

export interface PostApiTeamsIdTransferOut {
  result: string;
}

export function postApiTeamsIdTransfer(r: Requester, id: string | number, body: PostApiTeamsIdTransferIn, extras: CallExtras = {}): Promise<PostApiTeamsIdTransferOut> {
  return r<PostApiTeamsIdTransferOut>("POST", "/api/teams/{id}/transfer", { ...extras, params: { id }, body })
}

export interface PostApiTournamentsIdRegistrationsIn {
  team_id: number;
  accounts: Record<string, number>;
}

export interface PostApiTournamentsIdRegistrationsOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
}

export function postApiTournamentsIdRegistrations(r: Requester, id: string | number, body: PostApiTournamentsIdRegistrationsIn, extras: CallExtras = {}): Promise<PostApiTournamentsIdRegistrationsOut> {
  return r<PostApiTournamentsIdRegistrationsOut>("POST", "/api/tournaments/{id}/registrations", { ...extras, params: { id }, body })
}

export interface PostApiTournamentsIdSignupIn {
  game_account_id: number;
  roles: string[];
}

export interface PostApiTournamentsIdSignupOut {
  signup: {   id: number;   game_account_id: number | null;   roles: string[];   placed: boolean;   registration_id: number | null;   created_at: string; } | null;
}

export function postApiTournamentsIdSignup(r: Requester, id: string | number, body: PostApiTournamentsIdSignupIn, extras: CallExtras = {}): Promise<PostApiTournamentsIdSignupOut> {
  return r<PostApiTournamentsIdSignupOut>("POST", "/api/tournaments/{id}/signup", { ...extras, params: { id }, body })
}

export interface PutApiAdminFeatureRoleRestrictionsIn {
  restrictions: {   role: string;   feature: string; }[];
}

export interface PutApiAdminFeatureRoleRestrictionsOut {
  result: string;
  message: string;
}

export function putApiAdminFeatureRoleRestrictions(r: Requester, body: PutApiAdminFeatureRoleRestrictionsIn, extras: CallExtras = {}): Promise<PutApiAdminFeatureRoleRestrictionsOut> {
  return r<PutApiAdminFeatureRoleRestrictionsOut>("PUT", "/api/admin/feature-role-restrictions", { ...extras, body })
}

export interface PutApiAdminHomePinsIn {
  article_ids: number[];
}

export interface PutApiAdminHomePinsOut {
  result: string;
}

export function putApiAdminHomePins(r: Requester, body: PutApiAdminHomePinsIn, extras: CallExtras = {}): Promise<PutApiAdminHomePinsOut> {
  return r<PutApiAdminHomePinsOut>("PUT", "/api/admin/home-pins", { ...extras, body })
}

