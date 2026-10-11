import type { GetApiMeRegistrationsOut, GetApiMeCalendarOut } from "@sjtu-ow/api"

// [BE-12] Fields absent in the existing projection stay optional until apigen.
export type PersonalRegistration = GetApiMeRegistrationsOut["registrations"][number] & {
  starts_at?: string | null
  starts_label?: string
  team_id?: number | null
  status_label?: string
}

export type PersonalSignup = {
  id: number
  tournament_id: number
  title: string
  starts_at: string | null
  starts_label: string
  battletag: string | null
  role_tank: boolean
  role_damage: boolean
  role_support: boolean
  registration_id: number | null
  registration_team_name: string
  tournament_status: string
  registration_open: boolean
}

export type PersonalRegistrations = {
  registrations: PersonalRegistration[]
  individual_signups?: PersonalSignup[]
  calendar?: GetApiMeCalendarOut | null
}

export function registrationLabel(status: string, label?: string): string {
  if (label) return label
  const labels: Record<string, string> = {
    pending: "待审核",
    approved: "已通过",
    rejected: "已驳回",
    withdrawn: "已撤回",
  }
  return labels[status] ?? status
}

export function signupStatus(signup: PersonalSignup): { kind: string; label: string } {
  if (signup.registration_id !== null) return { kind: "ok", label: `已编入「${signup.registration_team_name}」` }
  if (signup.tournament_status === "cancelled") return { kind: "off", label: "赛事已取消" }
  if (signup.tournament_status === "finished") return { kind: "done", label: "赛事已结束，没有编队" }
  return { kind: "warn", label: "等待编队" }
}
