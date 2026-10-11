/** Compatibility names for management consumers; every HTTP contract comes from apigen. */
import type { CallExtras, Requester } from "@sjtu-ow/api"
import type { SaveRequest } from "@sjtu-ow/shared/autosave"
import * as generated from "@sjtu-ow/api"
import { formReceipt } from "./save-projection"

export type UserBasics = NonNullable<generated.PatchApiAdminUsersIdIn['changes']> & { nickname: string; is_sjtu: boolean }
export type RolesPage = generated.GetApiAdminRolesOut
export type Role = RolesPage['groups'][number]
export type Rule = Role['restrictions'][number]
export type Feature = RolesPage['features'][number]
export type UserRulesPage = generated.GetApiAdminUsersIdFeatureRulesOut
export type TeamAdminPage = generated.GetApiAdminTeamsIdOut
export type RegistrationList = generated.GetApiAdminRegistrationsOut
export type Registration = RegistrationList['items'][number]
export type RegistrationDetail = generated.GetApiAdminRegistrationsIdOut
export type RegistrationQuery = generated.GetApiAdminRegistrationsQuery
export type BulkReceipt = generated.PostApiAdminRegistrationsBulkApproveOut
export type HomePage = generated.GetApiAdminHomeOut
export type SetupCheck = NonNullable<HomePage['setup']>['required'][number]
export type FontsPage = generated.GetApiAdminFontsOut
export type Font = FontsPage['fonts'][number]
export type FontDetail = generated.GetApiAdminFontsIdOut
export type TypographyPage = generated.GetApiAdminTypographyOut
export type TypographyRegion = TypographyPage['regions'][number]
export type TypographyRegionValues = Pick<TypographyRegion, 'region' | 'mode' | 'family_id' | 'weight' | 'size_rem' | 'line_height' | 'letter_spacing_em'>
export type TypographyValues = { regions: TypographyRegionValues[] }
export type BackupPage = generated.GetApiAdminSettingsBackupOut
export type BackupValues = BackupPage['values']
export type CheckReceipt = generated.PostApiAdminSettingsTestStorageOut
export type AdminUserDetailOut = generated.GetApiAdminUsersIdOut

export const getHome = generated.getApiAdminHome
export const getRoles = generated.getApiAdminRoles
export const getUserRules = generated.getApiAdminUsersIdFeatureRules
export const addUserRule = generated.postApiAdminUsersIdFeatureRules
export const deleteUserRule = generated.deleteApiAdminUsersIdFeatureRulesRule
export const addRestriction = generated.postApiAdminRolesIdRestrictions
export const deleteRestriction = generated.deleteApiAdminRolesIdRestrictionsRule
export const getTeamAdmin = generated.getApiAdminTeamsId
export const getRegistrations = generated.getApiAdminRegistrations
export const getRegistration = generated.getApiAdminRegistrationsId
export const exportRegistrations = generated.postApiAdminRegistrationsExport
export const getFonts = generated.getApiAdminFonts
export const getFont = generated.getApiAdminFontsId
export const importFont = generated.postApiAdminFonts
export const deleteFont = generated.deleteApiAdminFontsId
export const getTypography = generated.getApiAdminTypography
export const getBackup = generated.getApiAdminSettingsBackup
export const testStorage = generated.postApiAdminSettingsTestStorage
export const getAdminUser = generated.getApiAdminUsersId

export async function patchUser(api: Requester, id: string, body: SaveRequest<UserBasics>, extras: CallExtras = {}) {
  const response = await generated.patchApiAdminUsersId(api, id, body, extras)
  return formReceipt(response, { nickname: '', is_sjtu: false })
}
export function bulkApprove(api: Requester, ids: number[], extras: CallExtras = {}) {
  return generated.postApiAdminRegistrationsBulkApprove(api, { ids }, extras)
}
/** Go's Region includes display metadata; supply it from the same generated shape. */
export function fullRegion(row: TypographyRegionValues): TypographyRegion {
  return { ...row, label: '', available_weights: [], slices: 0, bytes: 0 }
}
function isRegion(value: unknown): value is TypographyRegionValues {
  if (!value || typeof value !== 'object') return false
  const row: Record<string, unknown> = { ...value }
  const nullableNumber = (value: unknown) => value === null || typeof value === 'number' && Number.isFinite(value)
  return typeof row.region === 'string' && typeof row.mode === 'string'
    && nullableNumber(row.family_id) && typeof row.weight === 'number' && Number.isFinite(row.weight)
    && nullableNumber(row.size_rem) && nullableNumber(row.line_height) && nullableNumber(row.letter_spacing_em)
}
export async function patchTypography(api: Requester, body: SaveRequest<TypographyValues>, extras: CallExtras = {}) {
  const response = await generated.patchApiAdminTypography(api, {
    base_version: body.base_version,
    changes: { regions: body.changes.regions?.map(fullRegion) },
  }, extras)
  return formReceipt<TypographyValues>(response, { regions: [] }, (_key, value): value is TypographyValues['regions'] => Array.isArray(value) && value.every(isRegion))
}
