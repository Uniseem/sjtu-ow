// Package scrims 是内战域（12 号文档 5、规则 R144–R170）：内战的生命周期、报名、分队算法、
// 分队板和提醒。
package scrims

import "time"

// 规格。
const (
	FormatRQ5 = "rq_5v5"
	FormatRQ6 = "rq_6v6"
	Open5     = "open_5v5"
	Open6     = "open_6v6"
)

// 状态，只能向前走（规则 144）。
const (
	StatusDraft     = "draft"
	StatusPublished = "published"
	StatusFinished  = "finished"
	StatusCancelled = "cancelled"
)

// 位置。
const (
	Tank    = "tank"
	Damage  = "damage"
	Support = "support"
)

// RoleOrder 是三个位置的固定顺序。
var RoleOrder = []string{Tank, Damage, Support}

// RoleLabels 位置的中文名。
var RoleLabels = map[string]string{Tank: "坦克", Damage: "输出", Support: "支援"}

// FormatLabels 规格的中文名。
var FormatLabels = map[string]string{
	FormatRQ5: "角色限定 5v5", FormatRQ6: "角色限定 6v6", Open5: "不限位置 5v5", Open6: "不限位置 6v6",
}

// TeamSize 每队人数。
func TeamSize(format string) int {
	switch format {
	case FormatRQ6, Open6:
		return 6
	}
	return 5
}

// RoleQueue 是不是角色限定。
func RoleQueue(format string) bool { return format == FormatRQ5 || format == FormatRQ6 }

// Requirements 每队每个位置的人数（规则 160）：5v5 是 1/2/2，6v6 是 2/2/2；不限位置没有要求。
func Requirements(format string) map[string]int {
	switch format {
	case FormatRQ5:
		return map[string]int{Tank: 1, Damage: 2, Support: 2}
	case FormatRQ6:
		return map[string]int{Tank: 2, Damage: 2, Support: 2}
	}
	return nil
}

const (
	// FinishedVisibleDays 已结束的内战在公开列表保留多少天（规则 149）。
	FinishedVisibleDays = 30
	// FinishAfter 开始后多久自动结束（规则 147）。
	FinishAfter = 6 * time.Hour
	// ReminderGrace 提醒窗口内刚保存的，至少再等这么久（规则 139 同款）。
	ReminderGrace = 10 * time.Minute
	// NotifyNoteMax 「通知报名的人」的说明上限。
	NotifyNoteMax = 500
)

// Scrim 是一场内战。
type Scrim struct {
	ID               int64      `json:"id"`
	Title            string     `json:"title"`
	Description      string     `json:"description"`
	StartsAt         *time.Time `json:"starts_at"`
	SignupClosesAt   *time.Time `json:"signup_closes_at"`
	Format           string     `json:"format"`
	SjtuOnly         bool       `json:"sjtu_only"`
	Status           string     `json:"status"`
	TeamsGeneratedAt *time.Time `json:"teams_generated_at,omitempty"`
	RosterChangedAt  *time.Time `json:"roster_changed_at,omitempty"`
	ReminderSentAt   *time.Time `json:"reminder_sent_at,omitempty"`
	MovedFrom        *time.Time `json:"moved_from,omitempty"`
	CreatedBy        *int64     `json:"created_by,omitempty"`
	Version          int64      `json:"version"`
	BoardVersion     int64      `json:"board_version"`
	CreatedAt        time.Time  `json:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at"`
}

// PlayersNeeded 分队需要的人数（规则 159）。
func (s *Scrim) PlayersNeeded() int { return TeamSize(s.Format) * 2 }

// RoleQueue 是不是角色限定。
func (s *Scrim) RoleQueue() bool { return RoleQueue(s.Format) }

// Deadline 报名截止：留空表示开赛前都能报（规则 154）。
func (s *Scrim) Deadline() *time.Time {
	if s.SignupClosesAt != nil {
		return s.SignupClosesAt
	}
	return s.StartsAt
}

// SignupOpen 现在能不能报名。
func (s *Scrim) SignupOpen(now time.Time) bool {
	d := s.Deadline()
	return s.Status == StatusPublished && d != nil && !now.After(*d)
}

// IsPublic 草稿对外是 404（规则 148）。
func (s *Scrim) IsPublic() bool { return s.Status != StatusDraft }

// Signup 是一个人的报名和他在分队里的去向。
type Signup struct {
	ID            int64
	ScrimID       int64
	UserID        int64
	GameAccountID *int64
	RoleTank      bool
	RoleDamage    bool
	RoleSupport   bool
	IsSelected    bool
	Team          string
	AssignedRole  string
	RatingUsed    *int
	CreatedAt     time.Time
	UpdatedAt     time.Time
}

// Roles 勾选的位置，按坦克、输出、支援。
func (s *Signup) Roles() []string {
	out := []string{}
	if s.RoleTank {
		out = append(out, Tank)
	}
	if s.RoleDamage {
		out = append(out, Damage)
	}
	if s.RoleSupport {
		out = append(out, Support)
	}
	return out
}

// HasRole 是否勾了某个位置。
func (s *Signup) HasRole(role string) bool {
	switch role {
	case Tank:
		return s.RoleTank
	case Damage:
		return s.RoleDamage
	case Support:
		return s.RoleSupport
	}
	return false
}

// Placed 已经被分到队里或进了替补（规则 157、158）。
func (s *Signup) Placed() bool { return s.IsSelected || s.Team != "" }
