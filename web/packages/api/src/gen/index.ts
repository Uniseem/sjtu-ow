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

export interface DeleteApiAdminScrimsIdIn {
}

export interface DeleteApiAdminScrimsIdOut {
  result: string;
}

export function deleteApiAdminScrimsId(id: string): Promise<DeleteApiAdminScrimsIdOut> {
  return call<DeleteApiAdminScrimsIdOut>("DELETE", "/api/admin/scrims/{id}", { id }, undefined)
}

export interface DeleteApiAdminTournamentsIdIn {
}

export interface DeleteApiAdminTournamentsIdOut {
  result: string;
}

export function deleteApiAdminTournamentsId(id: string): Promise<DeleteApiAdminTournamentsIdOut> {
  return call<DeleteApiAdminTournamentsIdOut>("DELETE", "/api/admin/tournaments/{id}", { id }, undefined)
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

export interface DeleteApiMeAvatarIn {
}

export interface DeleteApiMeAvatarOut {
  result: string;
}

export function deleteApiMeAvatar(): Promise<DeleteApiMeAvatarOut> {
  return call<DeleteApiMeAvatarOut>("DELETE", "/api/me/avatar", {  }, undefined)
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

export interface DeleteApiScrimsIdSignupIn {
}

export interface DeleteApiScrimsIdSignupOut {
  result: string;
}

export function deleteApiScrimsIdSignup(id: string): Promise<DeleteApiScrimsIdSignupOut> {
  return call<DeleteApiScrimsIdSignupOut>("DELETE", "/api/scrims/{id}/signup", { id }, undefined)
}

export interface DeleteApiTournamentsIdSignupIn {
}

export interface DeleteApiTournamentsIdSignupOut {
  result: string;
}

export function deleteApiTournamentsIdSignup(id: string): Promise<DeleteApiTournamentsIdSignupOut> {
  return call<DeleteApiTournamentsIdSignupOut>("DELETE", "/api/tournaments/{id}/signup", { id }, undefined)
}

export interface GetApiAdminActivityIn {
}

export interface GetApiAdminActivityOut {
  period: {   start: string;   end: string; };
  notice?: string;
  totals: {   members: number;   sjtu_members: number;   scrims: number;   scrim_signups: number;   scrim_players: number;   scrim_people: number;   tournaments: number;   tournament_teams: number;   tournament_people: number;   articles: number;   comments: number;   teams: number; };
  events: {   when: string;   kind: string;   title: string;   status: string;   entries: number;   players: number;   url: string; }[];
  presets: string[];
}

export function getApiAdminActivity(): Promise<GetApiAdminActivityOut> {
  return call<GetApiAdminActivityOut>("GET", "/api/admin/activity", {  }, undefined)
}

export interface GetApiAdminAnnounceKindIdIn {
}

export interface GetApiAdminAnnounceKindIdOut {
  problem: string;
  recipients: number;
  will_wait: boolean;
  history: {   id: number;   audience: string;   subject: string;   recipient_count: number;   waiting: boolean;   created_at: string; }[];
}

export function getApiAdminAnnounceKindId(kind: string, id: string): Promise<GetApiAdminAnnounceKindIdOut> {
  return call<GetApiAdminAnnounceKindIdOut>("GET", "/api/admin/announce/{kind}/{id}", { kind, id }, undefined)
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

export interface GetApiAdminAvatarsIn {
}

export interface GetApiAdminAvatarsOut {
  items: {   id: number;   user_id: number;   user_nickname: string;   image_id: number | null;   status: string;   handling_note: string;   reviewed_at?: string | null;   created_at: string; }[];
  total: number;
  page: number;
  page_size: number;
}

export function getApiAdminAvatars(): Promise<GetApiAdminAvatarsOut> {
  return call<GetApiAdminAvatarsOut>("GET", "/api/admin/avatars", {  }, undefined)
}

export interface GetApiAdminCategoriesIn {
}

export interface GetApiAdminCategoriesOut {
  items: {   id: number;   name: string;   slug: string;   description: string;   sort_order: number;   allow_submission: boolean;   version: number;   created_at: string;   updated_at: string;   article_count?: number; } | null[];
}

export function getApiAdminCategories(): Promise<GetApiAdminCategoriesOut> {
  return call<GetApiAdminCategoriesOut>("GET", "/api/admin/categories", {  }, undefined)
}

export interface GetApiAdminCommentsIn {
}

export interface GetApiAdminCommentsOut {
  items: {   id: number;   article_id: number;   article_title: string;   author_id: number;   author_name: string;   content: string;   is_pinned: boolean;   is_hidden: boolean;   is_deleted: boolean;   like_count: number;   created_at: string; }[];
  total: number;
  page: number;
  page_size: number;
}

export function getApiAdminComments(): Promise<GetApiAdminCommentsOut> {
  return call<GetApiAdminCommentsOut>("GET", "/api/admin/comments", {  }, undefined)
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

export interface GetApiAdminImageCollectionsIn {
}

export interface GetApiAdminImageCollectionsOut {
  collections: {   id: number;   name: string;   key: string;   created_at: string; }[];
}

export function getApiAdminImageCollections(): Promise<GetApiAdminImageCollectionsOut> {
  return call<GetApiAdminImageCollectionsOut>("GET", "/api/admin/image-collections", {  }, undefined)
}

export interface GetApiAdminImagesIn {
}

export interface GetApiAdminImagesOut {
  items: {   id: number;   collection_id: number | null;   title: string;   file_name: string;   file_size: number;   width: number;   height: number;   uploader_id: number | null;   created_at: string;   version: number; }[];
  total: number;
  page: number;
  page_size: number;
}

export function getApiAdminImages(): Promise<GetApiAdminImagesOut> {
  return call<GetApiAdminImagesOut>("GET", "/api/admin/images", {  }, undefined)
}

export interface GetApiAdminLogIn {
}

export interface GetApiAdminLogOut {
  items: {   Entry: {   id: number;   actor_id: number | null;   action: string;   object_type: string;   object_id: number;   data: number[];   created_at: string; };   actor_nickname: string;   actor_email: string; }[];
  total: number;
  page: number;
  page_size: number;
}

export function getApiAdminLog(): Promise<GetApiAdminLogOut> {
  return call<GetApiAdminLogOut>("GET", "/api/admin/log", {  }, undefined)
}

export interface GetApiAdminManualIn {
}

export interface GetApiAdminManualOut {
  parts: {   key: string;   title: string;   steps: {   text: string;   link_url?: string;   link_label?: string; }[]; }[];
}

export function getApiAdminManual(): Promise<GetApiAdminManualOut> {
  return call<GetApiAdminManualOut>("GET", "/api/admin/manual", {  }, undefined)
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

export interface GetApiAdminModerationIn {
}

export interface GetApiAdminModerationOut {
  items: {   id: number;   target_type: string;   target_label: string;   target_id: number;   field: string;   url: string;   author_id: number | null;   excerpt: string;   full_text?: string;   text_hash: string;   risk: string;   categories: string[];   reason: string;   quote: string;   status: string;   reviewed_by: number | null;   reviewed_at: string | null;   handling_note: string;   checked_at: string | null;   notified_at: string | null;   attempts: number;   last_error: string;   failed_at: string | null;   created_at: string; } | null[];
  total: number;
  page: number;
  page_size: number;
  enabled: boolean;
  waiting: number;
  failed: number;
  last_error: string;
}

export function getApiAdminModeration(): Promise<GetApiAdminModerationOut> {
  return call<GetApiAdminModerationOut>("GET", "/api/admin/moderation", {  }, undefined)
}

export interface GetApiAdminModerationIdIn {
}

export interface GetApiAdminModerationIdOut {
  item: {   id: number;   target_type: string;   target_label: string;   target_id: number;   field: string;   url: string;   author_id: number | null;   excerpt: string;   full_text?: string;   text_hash: string;   risk: string;   categories: string[];   reason: string;   quote: string;   status: string;   reviewed_by: number | null;   reviewed_at: string | null;   handling_note: string;   checked_at: string | null;   notified_at: string | null;   attempts: number;   last_error: string;   failed_at: string | null;   created_at: string; } | null;
  author_flags: number;
  author_problem: string;
  history: {   id: number;   actor_id: number | null;   action: string;   object_type: string;   object_id: number;   data: number[];   created_at: string; }[];
}

export function getApiAdminModerationId(id: string): Promise<GetApiAdminModerationIdOut> {
  return call<GetApiAdminModerationIdOut>("GET", "/api/admin/moderation/{id}", { id }, undefined)
}

export interface GetApiAdminScrimsIn {
}

export interface GetApiAdminScrimsOut {
  scrims: {   Card: {   id: number;   title: string;   starts_at: string | null;   signup_deadline: string | null;   format: string;   format_label: string;   sjtu_only: boolean;   status: string;   signup_open: boolean;   signup_total: number;   players_needed: number; };   missing: string[];   can_delete: boolean;   teams_stale: boolean; }[];
}

export function getApiAdminScrims(): Promise<GetApiAdminScrimsOut> {
  return call<GetApiAdminScrimsOut>("GET", "/api/admin/scrims", {  }, undefined)
}

export interface GetApiAdminScrimsIdIn {
}

export interface GetApiAdminScrimsIdOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  row: {   Card: {   id: number;   title: string;   starts_at: string | null;   signup_deadline: string | null;   format: string;   format_label: string;   sjtu_only: boolean;   status: string;   signup_open: boolean;   signup_total: number;   players_needed: number; };   missing: string[];   can_delete: boolean;   teams_stale: boolean; } | null;
}

export function getApiAdminScrimsId(id: string): Promise<GetApiAdminScrimsIdOut> {
  return call<GetApiAdminScrimsIdOut>("GET", "/api/admin/scrims/{id}", { id }, undefined)
}

export interface GetApiAdminScrimsIdBoardIn {
}

export interface GetApiAdminScrimsIdBoardOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  order: string;
  signups: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[];
  selected_count: number;
  needed: number;
  teams: {   team: string;   label: string;   total: number;   problems: string[];   members: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[]; }[];
  bench: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[];
  gap: number;
  has_teams: boolean;
  teams_stale: boolean;
  copy_text: string;
  board_version: number;
  warnings?: string[];
}

export function getApiAdminScrimsIdBoard(id: string): Promise<GetApiAdminScrimsIdBoardOut> {
  return call<GetApiAdminScrimsIdBoardOut>("GET", "/api/admin/scrims/{id}/board", { id }, undefined)
}

export interface GetApiAdminSettingsIn {
}

export interface GetApiAdminSettingsOut {
  settings: {   id: number;   site_description: string;   from_name: string;   email_subject_prefix: string;   smtp_host: string;   smtp_port: number;   smtp_security: string;   smtp_username: string;   has_smtp_password: boolean;   from_address: string;   founded_on: string;   default_share_image_id: number | null;   hero_image_id: number | null;   banner_news_id: number | null;   banner_tournaments_id: number | null;   banner_scrims_id: number | null;   banner_teams_id: number | null;   banner_members_id: number | null;   qq_group_url: string;   team_max_members: number;   team_max_captained: number;   tournament_reminder_hours: number;   scrim_reminder_hours: number;   moderation_enabled: boolean;   moderation_configured: boolean;   moderation_provider: string;   has_moderation_api_key: boolean;   moderation_base_url: string;   moderation_model: string;   moderation_max_tokens: number;   moderation_timeout_seconds: number;   moderation_extra_params: string;   moderation_daily_limit: number;   moderation_notify_email: string;   version: number;   updated_at: string; } | null;
}

export function getApiAdminSettings(): Promise<GetApiAdminSettingsOut> {
  return call<GetApiAdminSettingsOut>("GET", "/api/admin/settings", {  }, undefined)
}

export interface GetApiAdminTeamsIn {
}

export interface GetApiAdminTeamsOut {
  teams: {   id: number;   name: string;   member_count: number;   captain_id: number | null;   captain_name: string;   captain_active: boolean;   no_captain: boolean;   disbanded_at?: string | null;   created_at: string; }[];
}

export function getApiAdminTeams(): Promise<GetApiAdminTeamsOut> {
  return call<GetApiAdminTeamsOut>("GET", "/api/admin/teams", {  }, undefined)
}

export interface GetApiAdminTodoIn {
}

export interface GetApiAdminTodoOut {
  has_duties: boolean;
  items: {   text: string;   url: string;   count: number; }[];
}

export function getApiAdminTodo(): Promise<GetApiAdminTodoOut> {
  return call<GetApiAdminTodoOut>("GET", "/api/admin/todo", {  }, undefined)
}

export interface GetApiAdminTournamentsIn {
}

export interface GetApiAdminTournamentsOut {
  tournaments: {   Card: {   id: number;   title: string;   summary: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   registration_mode: string;   sjtu_only: boolean;   status: string;   phase: string;   approved_count: number; };   pending_count: number;   waiting_for_team: number;   missing: string[]; }[];
}

export function getApiAdminTournaments(): Promise<GetApiAdminTournamentsOut> {
  return call<GetApiAdminTournamentsOut>("GET", "/api/admin/tournaments", {  }, undefined)
}

export interface GetApiAdminTournamentsIdIn {
}

export interface GetApiAdminTournamentsIdOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
  missing: string[];
  has_entries: boolean;
  has_registrations: boolean;
  can_delete: boolean;
  team_max_members: number;
}

export function getApiAdminTournamentsId(id: string): Promise<GetApiAdminTournamentsIdOut> {
  return call<GetApiAdminTournamentsIdOut>("GET", "/api/admin/tournaments/{id}", { id }, undefined)
}

export interface GetApiAdminTournamentsIdBoardIn {
}

export interface GetApiAdminTournamentsIdBoardOut {
  tournament: {   id: number;   title: string;   summary: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   registration_mode: string;   sjtu_only: boolean;   status: string;   phase: string;   approved_count: number; } | null;
  roster_max: number;
  entries: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   registration_id: number | null;   conflict?: string; }[];
  teams: {   registration_id: number;   name: string;   roster_version: number;   signup_ids: number[]; }[];
}

export function getApiAdminTournamentsIdBoard(id: string): Promise<GetApiAdminTournamentsIdBoardOut> {
  return call<GetApiAdminTournamentsIdBoardOut>("GET", "/api/admin/tournaments/{id}/board", { id }, undefined)
}

export interface GetApiAdminTournamentsIdRegistrationsIn {
}

export interface GetApiAdminTournamentsIdRegistrationsOut {
  registrations: {   registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; };   roster: {   id: number;   user_id: number;   game_account_id: number | null;   nickname: string;   battletag: string;   is_sjtu: boolean;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   is_captain: boolean;   is_active: boolean; }[];   logs: {   id: number;   action: string;   from_status: string;   to_status: string;   actor_type: string;   actor_user_id?: number | null;   roster_version: number;   note: string;   created_at: string; }[]; }[];
}

export function getApiAdminTournamentsIdRegistrations(id: string): Promise<GetApiAdminTournamentsIdRegistrationsOut> {
  return call<GetApiAdminTournamentsIdRegistrationsOut>("GET", "/api/admin/tournaments/{id}/registrations", { id }, undefined)
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
  user: {   ID: number;   Email: string;   EmailNorm: string;   PasswordHash: string;   Nickname: string;   IsSJTU: boolean;   AgreedTermsAt: string;   AgreedCrossBorderAt: string;   EmailVerifiedAt: string | null;   PasswordChangedAt: string | null;   Version: number;   IsActive: boolean;   IsSuperuser: boolean;   DeactivationNote: string;   Motto: string;   MainRole: string;   FlexRoles: string;   ShowRank: boolean;   AvatarImageID: number | null;   CreatedAt: string;   UpdatedAt: string; } | null;
  roles: string[];
  rules: Record<string, boolean>;
  game_accounts: {   id: number;   battletag: string;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   tank_label: string;   damage_label: string;   support_label: string;   ranks_updated_at: string; }[];
  contacts: {   id: number;   type: string;   type_label: string;   value: string;   created_at: string; }[];
}

export function getApiAdminUsersId(id: string): Promise<GetApiAdminUsersIdOut> {
  return call<GetApiAdminUsersIdOut>("GET", "/api/admin/users/{id}", { id }, undefined)
}

export interface GetApiAnnouncementsUnsubscribeTokenIn {
}

export interface GetApiAnnouncementsUnsubscribeTokenOut {
  nickname?: string;
  accepts: boolean;
}

export function getApiAnnouncementsUnsubscribeToken(token: string): Promise<GetApiAnnouncementsUnsubscribeTokenOut> {
  return call<GetApiAnnouncementsUnsubscribeTokenOut>("GET", "/api/announcements/unsubscribe/{token}", { token }, undefined)
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

export interface GetApiLettersIn {
}

export interface GetApiLettersOut {
  batches: {   batch: string;   subjects: string[];   people: number;   at: string;   in_back_office: boolean; }[];
}

export function getApiLetters(): Promise<GetApiLettersOut> {
  return call<GetApiLettersOut>("GET", "/api/letters", {  }, undefined)
}

export interface GetApiLettersBatchIn {
}

export interface GetApiLettersBatchOut {
  batch: string;
  state: string;
  letters: {   id: number;   subject: string;   who: string;   count: number; }[];
  back: string;
  in_back_office: boolean;
}

export function getApiLettersBatch(batch: string): Promise<GetApiLettersBatchOut> {
  return call<GetApiLettersBatchOut>("GET", "/api/letters/{batch}", { batch }, undefined)
}

export interface GetApiMeAgendaIn {
}

export interface GetApiMeAgendaOut {
  items: {   kind: string;   title: string;   url: string;   when: string | null;   note: string; }[];
}

export function getApiMeAgenda(): Promise<GetApiMeAgendaOut> {
  return call<GetApiMeAgendaOut>("GET", "/api/me/agenda", {  }, undefined)
}

export interface GetApiMeAnnouncementsIn {
}

export interface GetApiMeAnnouncementsOut {
  nickname?: string;
  accepts: boolean;
}

export function getApiMeAnnouncements(): Promise<GetApiMeAnnouncementsOut> {
  return call<GetApiMeAnnouncementsOut>("GET", "/api/me/announcements", {  }, undefined)
}

export interface GetApiMeCalendarIn {
}

export interface GetApiMeCalendarOut {
  url: string;
  webcal: string;
}

export function getApiMeCalendar(): Promise<GetApiMeCalendarOut> {
  return call<GetApiMeCalendarOut>("GET", "/api/me/calendar", {  }, undefined)
}

export interface GetApiMeExportIn {
}

export interface GetApiMeExportOut {
  user: {   ID: number;   Email: string;   EmailNorm: string;   PasswordHash: string;   Nickname: string;   IsSJTU: boolean;   AgreedTermsAt: string;   AgreedCrossBorderAt: string;   EmailVerifiedAt: string | null;   PasswordChangedAt: string | null;   Version: number;   IsActive: boolean;   IsSuperuser: boolean;   DeactivationNote: string;   Motto: string;   MainRole: string;   FlexRoles: string;   ShowRank: boolean;   AvatarImageID: number | null;   CreatedAt: string;   UpdatedAt: string; } | null;
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

export interface GetApiMeRegistrationsIn {
}

export interface GetApiMeRegistrationsOut {
  registrations: {   registration_id: number;   tournament_id: number;   title: string;   team_name: string;   status: string;   submitted_at: string; }[];
}

export function getApiMeRegistrations(): Promise<GetApiMeRegistrationsOut> {
  return call<GetApiMeRegistrationsOut>("GET", "/api/me/registrations", {  }, undefined)
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

export interface GetApiRegistrationsIdIn {
}

export interface GetApiRegistrationsIdOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
  tournament: {   id: number;   title: string;   summary: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   registration_mode: string;   sjtu_only: boolean;   status: string;   phase: string;   approved_count: number; } | null;
  roster: {   id: number;   user_id: number;   game_account_id: number | null;   nickname: string;   battletag: string;   is_sjtu: boolean;   rank_tank: number | null;   rank_damage: number | null;   rank_support: number | null;   is_captain: boolean;   is_active: boolean; }[];
  logs: {   id: number;   action: string;   from_status: string;   to_status: string;   actor_type: string;   actor_user_id?: number | null;   roster_version: number;   note: string;   created_at: string; }[];
  is_captain: boolean;
  can_withdraw: boolean;
  can_resubmit: boolean;
  roster_differs: boolean;
  can_leave: boolean;
  participant_contact?: string;
}

export function getApiRegistrationsId(id: string): Promise<GetApiRegistrationsIdOut> {
  return call<GetApiRegistrationsIdOut>("GET", "/api/registrations/{id}", { id }, undefined)
}

export interface GetApiScrimsIn {
}

export interface GetApiScrimsOut {
  scrims: {   id: number;   title: string;   starts_at: string | null;   signup_deadline: string | null;   format: string;   format_label: string;   sjtu_only: boolean;   status: string;   signup_open: boolean;   signup_total: number;   players_needed: number; }[];
}

export function getApiScrims(): Promise<GetApiScrimsOut> {
  return call<GetApiScrimsOut>("GET", "/api/scrims", {  }, undefined)
}

export interface GetApiScrimsIdIn {
}

export interface GetApiScrimsIdOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  card: {   id: number;   title: string;   starts_at: string | null;   signup_deadline: string | null;   format: string;   format_label: string;   sjtu_only: boolean;   status: string;   signup_open: boolean;   signup_total: number;   players_needed: number; };
  counts: {   total: number;   tank: number;   damage: number;   support: number; };
  signups: {   nickname: string;   roles: string[]; }[];
  mine: {   id: number;   game_account_id: number | null;   roles: string[];   placement: string;   can_cancel: boolean; } | null;
  problems: string[];
}

export function getApiScrimsId(id: string): Promise<GetApiScrimsIdOut> {
  return call<GetApiScrimsIdOut>("GET", "/api/scrims/{id}", { id }, undefined)
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
  user: {   id: number;   nickname: string;   email: string;   admin: boolean;   superuser: boolean;   caps: string[];   email_verified: boolean;   is_sjtu: boolean; } | null;
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

export interface GetApiTournamentsIn {
}

export interface GetApiTournamentsOut {
  groups: {   phase: string;   label: string;   tournaments: {   id: number;   title: string;   summary: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   registration_mode: string;   sjtu_only: boolean;   status: string;   phase: string;   approved_count: number; }[]; }[];
}

export function getApiTournaments(): Promise<GetApiTournamentsOut> {
  return call<GetApiTournamentsOut>("GET", "/api/tournaments", {  }, undefined)
}

export interface GetApiTournamentsIdIn {
}

export interface GetApiTournamentsIdOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
  phase: string;
  phase_label: string;
  approved_teams: {   registration_id: number;   team_id: number | null;   team_name: string;   member_count: number;   is_adhoc: boolean; }[];
  pool?: {   total: number;   tank: number;   damage: number;   support: number;   entries: {   signup_id: number;   user_id: number;   nickname: string;   roles: string[]; }[]; } | null;
  viewer: {   registration_open: boolean;   captain_teams: {   team_id: number;   name: string;   registration: {   id: number;   status: string; } | null;   problems: string[]; }[];   on_roster: {   id: number;   status: string; } | null;   my_signup: {   id: number;   game_account_id: number | null;   roles: string[];   placed: boolean;   registration_id: number | null;   created_at: string; } | null;   individual_problems: string[];   is_manager: boolean; };
}

export function getApiTournamentsId(id: string): Promise<GetApiTournamentsIdOut> {
  return call<GetApiTournamentsIdOut>("GET", "/api/tournaments/{id}", { id }, undefined)
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

export function patchApiAdminScrimsId(id: string, body: PatchApiAdminScrimsIdIn): Promise<PatchApiAdminScrimsIdOut> {
  return call<PatchApiAdminScrimsIdOut>("PATCH", "/api/admin/scrims/{id}", { id }, body)
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

export function patchApiAdminSettings(body: PatchApiAdminSettingsIn): Promise<PatchApiAdminSettingsOut> {
  return call<PatchApiAdminSettingsOut>("PATCH", "/api/admin/settings", {  }, body)
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

export function patchApiAdminTournamentsId(id: string, body: PatchApiAdminTournamentsIdIn): Promise<PatchApiAdminTournamentsIdOut> {
  return call<PatchApiAdminTournamentsIdOut>("PATCH", "/api/admin/tournaments/{id}", { id }, body)
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

export interface PostApiAdminAnnounceKindIdIn {
}

export interface PostApiAdminAnnounceKindIdOut {
  broadcast_id: number;
  recipients: number;
  waiting: boolean;
}

export function postApiAdminAnnounceKindId(kind: string, id: string): Promise<PostApiAdminAnnounceKindIdOut> {
  return call<PostApiAdminAnnounceKindIdOut>("POST", "/api/admin/announce/{kind}/{id}", { kind, id }, undefined)
}

export interface PostApiAdminAvatarsIdTakeDownIn {
  note: string;
}

export interface PostApiAdminAvatarsIdTakeDownOut {
  result: string;
}

export function postApiAdminAvatarsIdTakeDown(id: string, body: PostApiAdminAvatarsIdTakeDownIn): Promise<PostApiAdminAvatarsIdTakeDownOut> {
  return call<PostApiAdminAvatarsIdTakeDownOut>("POST", "/api/admin/avatars/{id}/take-down", { id }, body)
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

export interface PostApiAdminImagesUploadIn {
  title: string;
  collection_key: string;
  file_name: string;
  data_url: string;
}

export interface PostApiAdminImagesUploadOut {
  image: {   id: number;   collection_id: number | null;   title: string;   file_name: string;   file_size: number;   width: number;   height: number;   uploader_id: number | null;   created_at: string;   version: number; } | null;
}

export function postApiAdminImagesUpload(body: PostApiAdminImagesUploadIn): Promise<PostApiAdminImagesUploadOut> {
  return call<PostApiAdminImagesUploadOut>("POST", "/api/admin/images/upload", {  }, body)
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

export interface PostApiAdminModerationIdAskAuthorIn {
  message: string;
}

export interface PostApiAdminModerationIdAskAuthorOut {
  item: {   id: number;   target_type: string;   target_label: string;   target_id: number;   field: string;   url: string;   author_id: number | null;   excerpt: string;   full_text?: string;   text_hash: string;   risk: string;   categories: string[];   reason: string;   quote: string;   status: string;   reviewed_by: number | null;   reviewed_at: string | null;   handling_note: string;   checked_at: string | null;   notified_at: string | null;   attempts: number;   last_error: string;   failed_at: string | null;   created_at: string; } | null;
}

export function postApiAdminModerationIdAskAuthor(id: string, body: PostApiAdminModerationIdAskAuthorIn): Promise<PostApiAdminModerationIdAskAuthorOut> {
  return call<PostApiAdminModerationIdAskAuthorOut>("POST", "/api/admin/moderation/{id}/ask-author", { id }, body)
}

export interface PostApiAdminModerationIdHandleIn {
  action: string;
  note: string;
}

export interface PostApiAdminModerationIdHandleOut {
  item: {   id: number;   target_type: string;   target_label: string;   target_id: number;   field: string;   url: string;   author_id: number | null;   excerpt: string;   full_text?: string;   text_hash: string;   risk: string;   categories: string[];   reason: string;   quote: string;   status: string;   reviewed_by: number | null;   reviewed_at: string | null;   handling_note: string;   checked_at: string | null;   notified_at: string | null;   attempts: number;   last_error: string;   failed_at: string | null;   created_at: string; } | null;
}

export function postApiAdminModerationIdHandle(id: string, body: PostApiAdminModerationIdHandleIn): Promise<PostApiAdminModerationIdHandleOut> {
  return call<PostApiAdminModerationIdHandleOut>("POST", "/api/admin/moderation/{id}/handle", { id }, body)
}

export interface PostApiAdminRegistrationsIdApproveIn {
}

export interface PostApiAdminRegistrationsIdApproveOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminRegistrationsIdApprove(id: string): Promise<PostApiAdminRegistrationsIdApproveOut> {
  return call<PostApiAdminRegistrationsIdApproveOut>("POST", "/api/admin/registrations/{id}/approve", { id }, undefined)
}

export interface PostApiAdminRegistrationsIdDissolveIn {
}

export interface PostApiAdminRegistrationsIdDissolveOut {
  result: string;
}

export function postApiAdminRegistrationsIdDissolve(id: string): Promise<PostApiAdminRegistrationsIdDissolveOut> {
  return call<PostApiAdminRegistrationsIdDissolveOut>("POST", "/api/admin/registrations/{id}/dissolve", { id }, undefined)
}

export interface PostApiAdminRegistrationsIdRejectIn {
  note: string;
}

export interface PostApiAdminRegistrationsIdRejectOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminRegistrationsIdReject(id: string, body: PostApiAdminRegistrationsIdRejectIn): Promise<PostApiAdminRegistrationsIdRejectOut> {
  return call<PostApiAdminRegistrationsIdRejectOut>("POST", "/api/admin/registrations/{id}/reject", { id }, body)
}

export interface PostApiAdminScrimsIn {
}

export interface PostApiAdminScrimsOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrims(): Promise<PostApiAdminScrimsOut> {
  return call<PostApiAdminScrimsOut>("POST", "/api/admin/scrims", {  }, undefined)
}

export interface PostApiAdminScrimsIdBoardGenerateIn {
  signup_ids: number[];
  base_board_version: number;
}

export interface PostApiAdminScrimsIdBoardGenerateOut {
  board: {   scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;   order: string;   signups: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[];   selected_count: number;   needed: number;   teams: {   team: string;   label: string;   total: number;   problems: string[];   members: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[]; }[];   bench: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[];   gap: number;   has_teams: boolean;   teams_stale: boolean;   copy_text: string;   board_version: number;   warnings?: string[]; } | null;
  score: number[];
  unrated: string[];
}

export function postApiAdminScrimsIdBoardGenerate(id: string, body: PostApiAdminScrimsIdBoardGenerateIn): Promise<PostApiAdminScrimsIdBoardGenerateOut> {
  return call<PostApiAdminScrimsIdBoardGenerateOut>("POST", "/api/admin/scrims/{id}/board/generate", { id }, body)
}

export interface PostApiAdminScrimsIdBoardSelectionIn {
  signup_ids: number[];
  base_board_version: number;
}

export interface PostApiAdminScrimsIdBoardSelectionOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  order: string;
  signups: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[];
  selected_count: number;
  needed: number;
  teams: {   team: string;   label: string;   total: number;   problems: string[];   members: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[]; }[];
  bench: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[];
  gap: number;
  has_teams: boolean;
  teams_stale: boolean;
  copy_text: string;
  board_version: number;
  warnings?: string[];
}

export function postApiAdminScrimsIdBoardSelection(id: string, body: PostApiAdminScrimsIdBoardSelectionIn): Promise<PostApiAdminScrimsIdBoardSelectionOut> {
  return call<PostApiAdminScrimsIdBoardSelectionOut>("POST", "/api/admin/scrims/{id}/board/selection", { id }, body)
}

export interface PostApiAdminScrimsIdBoardTeamsIn {
  placements: {   signup_id: number;   team: string;   role: string; }[];
  base_board_version: number;
}

export interface PostApiAdminScrimsIdBoardTeamsOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
  order: string;
  signups: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[];
  selected_count: number;
  needed: number;
  teams: {   team: string;   label: string;   total: number;   problems: string[];   members: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[]; }[];
  bench: {   signup_id: number;   user_id: number;   nickname: string;   battletag: string;   roles: string[];   ratings: Record<string, number>;   rank_text: Record<string, string>;   best_rating: number | null;   is_selected: boolean;   team: string;   assigned_role: string;   rating_used: number | null;   contacts?: string[];   created_at: string; }[];
  gap: number;
  has_teams: boolean;
  teams_stale: boolean;
  copy_text: string;
  board_version: number;
  warnings?: string[];
}

export function postApiAdminScrimsIdBoardTeams(id: string, body: PostApiAdminScrimsIdBoardTeamsIn): Promise<PostApiAdminScrimsIdBoardTeamsOut> {
  return call<PostApiAdminScrimsIdBoardTeamsOut>("POST", "/api/admin/scrims/{id}/board/teams", { id }, body)
}

export interface PostApiAdminScrimsIdCancelIn {
}

export interface PostApiAdminScrimsIdCancelOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrimsIdCancel(id: string): Promise<PostApiAdminScrimsIdCancelOut> {
  return call<PostApiAdminScrimsIdCancelOut>("POST", "/api/admin/scrims/{id}/cancel", { id }, undefined)
}

export interface PostApiAdminScrimsIdCopyIn {
}

export interface PostApiAdminScrimsIdCopyOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrimsIdCopy(id: string): Promise<PostApiAdminScrimsIdCopyOut> {
  return call<PostApiAdminScrimsIdCopyOut>("POST", "/api/admin/scrims/{id}/copy", { id }, undefined)
}

export interface PostApiAdminScrimsIdFinishIn {
}

export interface PostApiAdminScrimsIdFinishOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrimsIdFinish(id: string): Promise<PostApiAdminScrimsIdFinishOut> {
  return call<PostApiAdminScrimsIdFinishOut>("POST", "/api/admin/scrims/{id}/finish", { id }, undefined)
}

export interface PostApiAdminScrimsIdNotifyIn {
  note: string;
}

export interface PostApiAdminScrimsIdNotifyOut {
  recipients: number;
}

export function postApiAdminScrimsIdNotify(id: string, body: PostApiAdminScrimsIdNotifyIn): Promise<PostApiAdminScrimsIdNotifyOut> {
  return call<PostApiAdminScrimsIdNotifyOut>("POST", "/api/admin/scrims/{id}/notify", { id }, body)
}

export interface PostApiAdminScrimsIdPublishIn {
}

export interface PostApiAdminScrimsIdPublishOut {
  scrim: {   id: number;   title: string;   description: string;   starts_at: string | null;   signup_closes_at: string | null;   format: string;   sjtu_only: boolean;   status: string;   teams_generated_at?: string | null;   roster_changed_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   created_by?: number | null;   version: number;   board_version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminScrimsIdPublish(id: string): Promise<PostApiAdminScrimsIdPublishOut> {
  return call<PostApiAdminScrimsIdPublishOut>("POST", "/api/admin/scrims/{id}/publish", { id }, undefined)
}

export interface PostApiAdminSettingsTestEmailIn {
}

export interface PostApiAdminSettingsTestEmailOut {
  result: string;
  message: string;
}

export function postApiAdminSettingsTestEmail(): Promise<PostApiAdminSettingsTestEmailOut> {
  return call<PostApiAdminSettingsTestEmailOut>("POST", "/api/admin/settings/test-email", {  }, undefined)
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

export interface PostApiAdminTournamentsIn {
}

export interface PostApiAdminTournamentsOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournaments(): Promise<PostApiAdminTournamentsOut> {
  return call<PostApiAdminTournamentsOut>("POST", "/api/admin/tournaments", {  }, undefined)
}

export interface PostApiAdminTournamentsIdBoardIn {
  teams: {   registration_id: number | null;   name: string;   signup_ids: number[];   base_version: number; }[];
}

export interface PostApiAdminTournamentsIdBoardOut {
  created: number;
  updated: number;
  dissolved: number;
  returned: number;
}

export function postApiAdminTournamentsIdBoard(id: string, body: PostApiAdminTournamentsIdBoardIn): Promise<PostApiAdminTournamentsIdBoardOut> {
  return call<PostApiAdminTournamentsIdBoardOut>("POST", "/api/admin/tournaments/{id}/board", { id }, body)
}

export interface PostApiAdminTournamentsIdCancelIn {
  reason: string;
}

export interface PostApiAdminTournamentsIdCancelOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournamentsIdCancel(id: string, body: PostApiAdminTournamentsIdCancelIn): Promise<PostApiAdminTournamentsIdCancelOut> {
  return call<PostApiAdminTournamentsIdCancelOut>("POST", "/api/admin/tournaments/{id}/cancel", { id }, body)
}

export interface PostApiAdminTournamentsIdCopyIn {
}

export interface PostApiAdminTournamentsIdCopyOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournamentsIdCopy(id: string): Promise<PostApiAdminTournamentsIdCopyOut> {
  return call<PostApiAdminTournamentsIdCopyOut>("POST", "/api/admin/tournaments/{id}/copy", { id }, undefined)
}

export interface PostApiAdminTournamentsIdFinishIn {
}

export interface PostApiAdminTournamentsIdFinishOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournamentsIdFinish(id: string): Promise<PostApiAdminTournamentsIdFinishOut> {
  return call<PostApiAdminTournamentsIdFinishOut>("POST", "/api/admin/tournaments/{id}/finish", { id }, undefined)
}

export interface PostApiAdminTournamentsIdNotifyIn {
  note: string;
}

export interface PostApiAdminTournamentsIdNotifyOut {
  recipients: number;
}

export function postApiAdminTournamentsIdNotify(id: string, body: PostApiAdminTournamentsIdNotifyIn): Promise<PostApiAdminTournamentsIdNotifyOut> {
  return call<PostApiAdminTournamentsIdNotifyOut>("POST", "/api/admin/tournaments/{id}/notify", { id }, body)
}

export interface PostApiAdminTournamentsIdPublishIn {
}

export interface PostApiAdminTournamentsIdPublishOut {
  tournament: {   id: number;   title: string;   summary: string;   description: string;   cover_image_id: number | null;   starts_at: string | null;   registration_opens_at: string | null;   registration_closes_at: string | null;   roster_min: number;   roster_max: number;   sjtu_only: boolean;   registration_mode: string;   auto_approve: boolean;   status: string;   created_by?: number | null;   published_at?: string | null;   reminder_sent_at?: string | null;   moved_from?: string | null;   participant_contact?: string;   version: number;   created_at: string;   updated_at: string; } | null;
}

export function postApiAdminTournamentsIdPublish(id: string): Promise<PostApiAdminTournamentsIdPublishOut> {
  return call<PostApiAdminTournamentsIdPublishOut>("POST", "/api/admin/tournaments/{id}/publish", { id }, undefined)
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

export interface PostApiAnnouncementsUnsubscribeTokenIn {
}

export interface PostApiAnnouncementsUnsubscribeTokenOut {
  nickname?: string;
  accepts: boolean;
}

export function postApiAnnouncementsUnsubscribeToken(token: string): Promise<PostApiAnnouncementsUnsubscribeTokenOut> {
  return call<PostApiAnnouncementsUnsubscribeTokenOut>("POST", "/api/announcements/unsubscribe/{token}", { token }, undefined)
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

export interface PostApiLettersBatchIn {
  send: number[];
  skip: boolean;
}

export interface PostApiLettersBatchOut {
  letters: number;
  people: number;
}

export function postApiLettersBatch(batch: string, body: PostApiLettersBatchIn): Promise<PostApiLettersBatchOut> {
  return call<PostApiLettersBatchOut>("POST", "/api/letters/{batch}", { batch }, body)
}

export interface PostApiMeAnnouncementsIn {
  accepts: boolean;
}

export interface PostApiMeAnnouncementsOut {
  nickname?: string;
  accepts: boolean;
}

export function postApiMeAnnouncements(body: PostApiMeAnnouncementsIn): Promise<PostApiMeAnnouncementsOut> {
  return call<PostApiMeAnnouncementsOut>("POST", "/api/me/announcements", {  }, body)
}

export interface PostApiMeAvatarIn {
  file_name: string;
  data_url: string;
}

export interface PostApiMeAvatarOut {
  image: {   id: number;   collection_id: number | null;   title: string;   file_name: string;   file_size: number;   width: number;   height: number;   uploader_id: number | null;   created_at: string;   version: number; } | null;
}

export function postApiMeAvatar(body: PostApiMeAvatarIn): Promise<PostApiMeAvatarOut> {
  return call<PostApiMeAvatarOut>("POST", "/api/me/avatar", {  }, body)
}

export interface PostApiMeCalendarRenewIn {
}

export interface PostApiMeCalendarRenewOut {
  url: string;
  webcal: string;
}

export function postApiMeCalendarRenew(): Promise<PostApiMeCalendarRenewOut> {
  return call<PostApiMeCalendarRenewOut>("POST", "/api/me/calendar/renew", {  }, undefined)
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

export interface PostApiRegistrationsIdLeaveIn {
}

export interface PostApiRegistrationsIdLeaveOut {
  dissolved: boolean;
}

export function postApiRegistrationsIdLeave(id: string): Promise<PostApiRegistrationsIdLeaveOut> {
  return call<PostApiRegistrationsIdLeaveOut>("POST", "/api/registrations/{id}/leave", { id }, undefined)
}

export interface PostApiRegistrationsIdWithdrawIn {
}

export interface PostApiRegistrationsIdWithdrawOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
}

export function postApiRegistrationsIdWithdraw(id: string): Promise<PostApiRegistrationsIdWithdrawOut> {
  return call<PostApiRegistrationsIdWithdrawOut>("POST", "/api/registrations/{id}/withdraw", { id }, undefined)
}

export interface PostApiScrimsIdSignupIn {
  game_account_id: number;
  roles: string[];
}

export interface PostApiScrimsIdSignupOut {
  signup_id: number;
  roles: string[];
}

export function postApiScrimsIdSignup(id: string, body: PostApiScrimsIdSignupIn): Promise<PostApiScrimsIdSignupOut> {
  return call<PostApiScrimsIdSignupOut>("POST", "/api/scrims/{id}/signup", { id }, body)
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

export interface PostApiTeamsIdLogoIn {
  file_name: string;
  data_url: string;
}

export interface PostApiTeamsIdLogoOut {
  image: {   id: number;   collection_id: number | null;   title: string;   file_name: string;   file_size: number;   width: number;   height: number;   uploader_id: number | null;   created_at: string;   version: number; } | null;
}

export function postApiTeamsIdLogo(id: string, body: PostApiTeamsIdLogoIn): Promise<PostApiTeamsIdLogoOut> {
  return call<PostApiTeamsIdLogoOut>("POST", "/api/teams/{id}/logo", { id }, body)
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

export interface PostApiTournamentsIdRegistrationsIn {
  team_id: number;
  accounts: Record<string, number>;
}

export interface PostApiTournamentsIdRegistrationsOut {
  registration: {   id: number;   tournament_id: number;   team_id: number | null;   status: string;   team_name: string;   roster_version: number;   submitted_by?: number | null;   submitted_at: string;   status_note: string;   created_at: string;   updated_at: string; } | null;
}

export function postApiTournamentsIdRegistrations(id: string, body: PostApiTournamentsIdRegistrationsIn): Promise<PostApiTournamentsIdRegistrationsOut> {
  return call<PostApiTournamentsIdRegistrationsOut>("POST", "/api/tournaments/{id}/registrations", { id }, body)
}

export interface PostApiTournamentsIdSignupIn {
  game_account_id: number;
  roles: string[];
}

export interface PostApiTournamentsIdSignupOut {
  signup: {   id: number;   game_account_id: number | null;   roles: string[];   placed: boolean;   registration_id: number | null;   created_at: string; } | null;
}

export function postApiTournamentsIdSignup(id: string, body: PostApiTournamentsIdSignupIn): Promise<PostApiTournamentsIdSignupOut> {
  return call<PostApiTournamentsIdSignupOut>("POST", "/api/tournaments/{id}/signup", { id }, body)
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
