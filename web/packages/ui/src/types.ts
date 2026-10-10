// Display-only projections: callers pass the public fields their page API
// supplies. Components never infer private ranks or account identifiers.
export interface AvatarPerson {
  id?: number | null
  nickname?: string | null
  is_active?: boolean
  avatar_image_id?: number | null
  default_avatar_image_id?: number | null
  avatar_url?: string | null
  default_avatar_url?: string | null
}
export type RoleCode = "tank" | "damage" | "support"
export interface RoleItem { code: RoleCode; label: string; main: boolean }
export interface PublicPlay {
  roles: RoleItem[]
  is_flex?: boolean
  main_rank?: { label: string; role_label: string; stale: boolean; updated_at?: string | null } | null
}
