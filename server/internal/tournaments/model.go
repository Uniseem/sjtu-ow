// Package tournaments 是赛事域（12 号文档 5、规则 R109–R143）：赛事的生命周期、整队报名的
// 预检/快照/状态机、个人报名与编队（散人池）、改期与提醒。
package tournaments

import "time"

// 赛事状态。
const (
	StatusDraft     = "draft"
	StatusPublished = "published"
	StatusFinished  = "finished"
	StatusCancelled = "cancelled"
)

// 报名方式（一项赛事只有一种，规则 111）。
const (
	ModeIndividual = "individual"
	ModeTeam       = "team"
)

// 报名状态。待审和已通过占名额。
const (
	RegPending   = "pending"
	RegApproved  = "approved"
	RegRejected  = "rejected"
	RegWithdrawn = "withdrawn"
)

// 状态日志里的操作。
const (
	ActSubmit     = "submit"
	ActResubmit   = "resubmit"
	ActSyncRoster = "sync_roster"
	ActApprove    = "approve"
	ActReject     = "reject"
	ActRevoke     = "revoke"
	ActWithdraw   = "withdraw"
	ActFormTeam   = "form_team"
	ActMemberLeft = "member_left"
	ActDissolve   = "dissolve"
)

// 操作方。
const (
	ActorCaptain = "captain"
	ActorAdmin   = "admin"
	ActorSystem  = "system"
	ActorMember  = "member"
)

const (
	// TeamNameMax 临时队伍名上限（规则 130）。
	TeamNameMax = 16
	// NoteMax 驳回备注上限（规则 125）。
	NoteMax = 300
	// NotifyNoteMax 「通知报名的人」的说明上限（规则 137）。
	NotifyNoteMax = 500
	// ReminderGrace 提醒落在窗口内保存的，至少推迟这么久再发（规则 139）。
	ReminderGrace = 10 * time.Minute
	// AutoApproveNote 自动通过写进日志的备注。
	AutoApproveNote = "自动通过"
)

// Tournament 是一项赛事。
type Tournament struct {
	ID                   int64      `json:"id"`
	Title                string     `json:"title"`
	Summary              string     `json:"summary"`
	Description          string     `json:"description"`
	CoverImageID         *int64     `json:"cover_image_id"`
	StartsAt             *time.Time `json:"starts_at"`
	RegistrationOpensAt  *time.Time `json:"registration_opens_at"`
	RegistrationClosesAt *time.Time `json:"registration_closes_at"`
	RosterMin            int        `json:"roster_min"`
	RosterMax            int        `json:"roster_max"`
	SjtuOnly             bool       `json:"sjtu_only"`
	RegistrationMode     string     `json:"registration_mode"`
	AutoApprove          bool       `json:"auto_approve"`
	Status               string     `json:"status"`
	CreatedBy            *int64     `json:"created_by,omitempty"`
	PublishedAt          *time.Time `json:"published_at,omitempty"`
	ReminderSentAt       *time.Time `json:"reminder_sent_at,omitempty"`
	MovedFrom            *time.Time `json:"moved_from,omitempty"`
	ParticipantContact   string     `json:"participant_contact,omitempty"`
	Version              int64      `json:"version"`
	CreatedAt            time.Time  `json:"created_at"`
	UpdatedAt            time.Time  `json:"updated_at"`
}

// Phase 赛事在列表页属于哪一组（设计 8.2）。
func (t *Tournament) Phase(now time.Time) string {
	switch t.Status {
	case StatusFinished:
		return "finished"
	case StatusCancelled:
		return "cancelled"
	}
	if t.RegistrationOpensAt == nil || t.RegistrationClosesAt == nil {
		return "upcoming"
	}
	if now.Before(*t.RegistrationOpensAt) {
		return "upcoming"
	}
	if !now.After(*t.RegistrationClosesAt) {
		return "open"
	}
	return "closed"
}

// RegistrationOpen 现在能不能报名。
func (t *Tournament) RegistrationOpen(now time.Time) bool {
	return t.Status == StatusPublished && t.Phase(now) == "open"
}

// IsPublic 草稿对前台不可达（设计 8.2）。
func (t *Tournament) IsPublic() bool { return t.Status != StatusDraft }

// TakesTeams 整队报名。
func (t *Tournament) TakesTeams() bool { return t.RegistrationMode == ModeTeam }

// TakesIndividuals 个人报名。
func (t *Tournament) TakesIndividuals() bool { return t.RegistrationMode == ModeIndividual }

// Registration 是一支队对一项赛事的一次报名；TeamID 为空是临时队伍。
type Registration struct {
	ID            int64     `json:"id"`
	TournamentID  int64     `json:"tournament_id"`
	TeamID        *int64    `json:"team_id"`
	Status        string    `json:"status"`
	TeamName      string    `json:"team_name"`
	RosterVersion int64     `json:"roster_version"`
	SubmittedBy   *int64    `json:"submitted_by,omitempty"`
	SubmittedAt   time.Time `json:"submitted_at"`
	StatusNote    string    `json:"status_note"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// Active 待审和已通过占名额。
func (r *Registration) Active() bool { return r.Status == RegPending || r.Status == RegApproved }

// Adhoc 临时队伍（管理员从散人池编的）。
func (r *Registration) Adhoc() bool { return r.TeamID == nil }

// RosterMember 是名单快照里的一个人。
type RosterMember struct {
	ID            int64  `json:"id"`
	UserID        int64  `json:"user_id"`
	GameAccountID *int64 `json:"game_account_id"`
	Nickname      string `json:"nickname"`
	Battletag     string `json:"battletag"`
	IsSJTU        bool   `json:"is_sjtu"`
	RankTank      *int   `json:"rank_tank"`
	RankDamage    *int   `json:"rank_damage"`
	RankSupport   *int   `json:"rank_support"`
	IsCaptain     bool   `json:"is_captain"`
	Active        bool   `json:"is_active"`
}

// StatusLog 是一条状态日志。
type StatusLog struct {
	ID            int64     `json:"id"`
	Action        string    `json:"action"`
	FromStatus    string    `json:"from_status"`
	ToStatus      string    `json:"to_status"`
	ActorType     string    `json:"actor_type"`
	ActorUserID   *int64    `json:"actor_user_id,omitempty"`
	RosterVersion int64     `json:"roster_version"`
	Note          string    `json:"note"`
	CreatedAt     time.Time `json:"created_at"`
}

// IndividualSignup 是散人池里的一个人。
type IndividualSignup struct {
	ID             int64     `json:"id"`
	TournamentID   int64     `json:"tournament_id"`
	UserID         int64     `json:"user_id"`
	GameAccountID  *int64    `json:"game_account_id"`
	RoleTank       bool      `json:"role_tank"`
	RoleDamage     bool      `json:"role_damage"`
	RoleSupport    bool      `json:"role_support"`
	RegistrationID *int64    `json:"registration_id"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// Placed 已被编入队伍。
func (s *IndividualSignup) Placed() bool { return s.RegistrationID != nil }
