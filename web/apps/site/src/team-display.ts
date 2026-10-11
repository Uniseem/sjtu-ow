import type { GetApiMeTeamsOut } from "@sjtu-ow/api"

// [BE-12] A missing private field differs from an empty private field.
export type PersonalAlumnus = {
  id: number
  team_id: number
  team_name: string
  joined_at: string
  left_at: string
}

export type PersonalMemberships = Omit<GetApiMeTeamsOut, "teams"> & {
  teams: (GetApiMeTeamsOut["teams"][number] & { member_contact?: string })[]
  alumni?: PersonalAlumnus[]
}

export function applicationStatus(status: string): { kind: string; label: string } {
  switch (status) {
    case "approved": return { kind: "ok", label: "已同意" }
    case "pending": return { kind: "warn", label: "待处理" }
    case "rejected": return { kind: "rejected", label: "已拒绝" }
    case "cancelled": return { kind: "off", label: "已撤回" }
    default: return { kind: "off", label: status }
  }
}
