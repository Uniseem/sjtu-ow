// Package teams 是战队域（12 号文档 5、规则 R083–R108）：建队、入队申请、成员变动、
// 队长转让与指定、解散、退役记录，以及夜里的提醒和自动关闭。
package teams

import "time"

// 战队里的身份。
const (
	RoleCaptain = "captain"
	RoleMember  = "member"
)

// 入队申请的状态。
const (
	StatusPending   = "pending"
	StatusApproved  = "approved"
	StatusRejected  = "rejected"
	StatusCancelled = "cancelled"
)

// 离队方式。
const (
	LeaveLeft    = "left"
	LeaveRemoved = "removed"
)

// 申请里的几个固定文案（现行站 teams/services.py）。
const (
	NameTaken      = "已经有同名的战队了，换一个队名吧。"
	GoneNote       = "申请人的账号已注销或停用"
	CaptainStopped = "这支战队的队长账号已停用，等管理员指定新队长后再申请。"
)

const (
	// StaleApplicationDays 待审超过这么多天自动关闭（规则 95）。
	StaleApplicationDays = 14
	// RemindCaptainDays 待审满这么多天给队长发一封汇总提醒（规则 94）。
	RemindCaptainDays = 7
	// NameMin / NameMax 队名长度（规则 83，按字数）。
	NameMin = 2
	NameMax = 16
	// DescriptionMax 简介字数上限。
	DescriptionMax = 500
	// MemberContactMax 队内联系方式字数上限。
	MemberContactMax = 100
	// MessageMax 申请留言字数上限（规则 90）。
	MessageMax = 200
	// LogoMaxBytes 队标文件上限（规则 106）。
	LogoMaxBytes = 5 * 1024 * 1024
)

// Team 是一支战队。解散是软删除：报名还指着它。
type Team struct {
	ID              int64      `json:"id"`
	Name            string     `json:"name"`
	Description     string     `json:"description"`
	LogoImageID     *int64     `json:"logo_image_id"`
	IsRecruiting    bool       `json:"is_recruiting"`
	RecruitingRoles []string   `json:"recruiting_roles"`
	MemberContact   string     `json:"member_contact,omitempty"`
	DisbandedAt     *time.Time `json:"disbanded_at,omitempty"`
	Version         int64      `json:"version"`
	CreatedAt       time.Time  `json:"created_at"`
	UpdatedAt       time.Time  `json:"updated_at"`
}

// Disbanded 报这支队是不是已经解散。
func (t *Team) Disbanded() bool { return t.DisbandedAt != nil }

// Membership 是一个人在一支队里的身份。
type Membership struct {
	ID       int64     `json:"id"`
	TeamID   int64     `json:"team_id"`
	UserID   int64     `json:"user_id"`
	Role     string    `json:"role"`
	JoinedAt time.Time `json:"joined_at"`
}

// Application 是一条入队申请。
type Application struct {
	ID                int64      `json:"id"`
	TeamID            int64      `json:"team_id"`
	ApplicantID       int64      `json:"applicant_id"`
	RoleTank          bool       `json:"role_tank"`
	RoleDamage        bool       `json:"role_damage"`
	RoleSupport       bool       `json:"role_support"`
	Message           string     `json:"message"`
	Status            string     `json:"status"`
	DecidedBy         *int64     `json:"decided_by,omitempty"`
	DecidedAt         *time.Time `json:"decided_at,omitempty"`
	DecisionNote      string     `json:"decision_note"`
	CaptainRemindedAt *time.Time `json:"captain_reminded_at,omitempty"`
	CreatedAt         time.Time  `json:"created_at"`
}

// Positions 是申请里勾的位置（坦克、输出、支援的固定顺序）。
func (a *Application) Positions() []string {
	var out []string
	if a.RoleTank {
		out = append(out, "tank")
	}
	if a.RoleDamage {
		out = append(out, "damage")
	}
	if a.RoleSupport {
		out = append(out, "support")
	}
	return out
}

// Alumnus 是退役成员：离队或被移除后还留在战队页上的记录（解散不写）。
type Alumnus struct {
	ID       int64     `json:"id"`
	TeamID   int64     `json:"team_id"`
	UserID   int64     `json:"user_id"`
	Role     string    `json:"role"`
	JoinedAt time.Time `json:"joined_at"`
	LeftAt   time.Time `json:"left_at"`
	Reason   string    `json:"reason"`
}
