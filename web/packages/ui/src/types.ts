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

// One comment as the comments API sends it (server/internal/comments/model.go),
// replies nested one level. `edited_at` waits for the backend (STATUS BE-8);
// until then nothing prints 已编辑.
export interface CommentView {
  id: number
  user_id?: number | null
  author_name: string
  reply_to_user_name?: string
  content: string
  is_pinned: boolean
  is_hidden: boolean
  is_deleted: boolean
  is_tombstone?: boolean
  like_count: number
  liked_by_me?: boolean
  replies?: CommentView[]
  edited_at?: string | null
  created_at: string
  updated_at: string
}
