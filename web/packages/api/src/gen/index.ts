// 由 sjtuow apigen 生成。不要手改。

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

export interface GetApiAdminFeatureRoleRestrictionsIn {
}

export interface GetApiAdminFeatureRoleRestrictionsOut {
  restrictions: {   role: string;   feature: string; }[];
}

export function getApiAdminFeatureRoleRestrictions(): Promise<GetApiAdminFeatureRoleRestrictionsOut> {
  return call<GetApiAdminFeatureRoleRestrictionsOut>("GET", "/api/admin/feature-role-restrictions", {  }, undefined)
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

export interface GetApiSessionIn {
}

export interface GetApiSessionOut {
  user: {   id: number;   nickname: string;   email: string;   admin: boolean;   email_verified: boolean;   is_sjtu: boolean; } | null;
}

export function getApiSession(): Promise<GetApiSessionOut> {
  return call<GetApiSessionOut>("GET", "/api/session", {  }, undefined)
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
