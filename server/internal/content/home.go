package content

import (
	"github.com/Uniseem/sjtu-ow/server/internal/agenda"
)

// HomeAge 社区成立年龄。
type HomeAge struct {
	Years int `json:"years"`
	Days  int `json:"days"`
}

// HomeStatsOut 首页社区统计指标。
type HomeStatsOut struct {
	MemberCount int      `json:"member_count"`
	TeamCount   int      `json:"team_count"`
	ScrimsHeld  int      `json:"scrims_held"`
	FoundedOn   string   `json:"founded_on,omitempty"`
	Age         *HomeAge `json:"age,omitempty"`
	HeroImageID *int64   `json:"hero_image_id,omitempty"`
	QQGroupURL  string   `json:"qq_group_url,omitempty"`
}

// HomeFeatureTournament 近期大图推荐赛事。
type HomeFeatureTournament struct {
	ID                   int64  `json:"id"`
	Title                string `json:"title"`
	Phase                string `json:"phase"`
	PhaseLabel           string `json:"phase_label"`
	RegistrationMode     string `json:"registration_mode"`
	TakesIndividuals     bool   `json:"takes_individuals"`
	ApprovedTeams        int    `json:"approved_teams"`
	StartsAt             string `json:"starts_at,omitempty"`
	RegistrationOpensAt  string `json:"registration_opens_at,omitempty"`
	RegistrationClosesAt string `json:"registration_closes_at,omitempty"`
	CoverImageID         *int64 `json:"cover_image_id,omitempty"`
	Facts                string `json:"facts"`
	DefaultCoverImageID  *int64 `json:"default_cover_image_id"`
}

// HomeScrimItem 近期内战行项目。
type HomeScrimItem struct {
	ID         int64  `json:"id"`
	Title      string `json:"title"`
	StartsAt   string `json:"starts_at"`
	Month      int    `json:"month"`
	Day        int    `json:"day"`
	Weekday    string `json:"weekday"`
	Time       string `json:"time"`
	Count      int    `json:"count"`
	Capacity   int    `json:"capacity"`
	SignupOpen bool   `json:"signup_open"`
}

// HomeNoticeItem 公告行项目。
type HomeNoticeItem struct {
	ID             int64  `json:"id"`
	Slug           string `json:"slug"`
	Title          string `json:"title"`
	Month          int    `json:"month"`
	Day            int    `json:"day"`
	PublishedAtRaw string `json:"published_at_raw"`
}

// HomeTeamItem 战队卡片项目。
type HomeTeamItem struct {
	ID             int64  `json:"id"`
	Name           string `json:"name"`
	LogoImageID    *int64 `json:"logo_image_id,omitempty"`
	MemberCount    int    `json:"member_count"`
	IsRecruiting   bool   `json:"is_recruiting"`
	WantedRoles    string `json:"wanted_roles,omitempty"`
	CreatedAtMonth string `json:"created_at_month"`
}

// HomePageIn 是 GET /api/page/home 的入参（空）。
type HomePageIn struct{}

// HomePageOut 是 GET /api/page/home 的出参。
type HomePageOut struct {
	Stats             *HomeStatsOut          `json:"stats"`
	FeatureTournament *HomeFeatureTournament `json:"feature_tournament,omitempty"`
	Scrims            []*HomeScrimItem       `json:"scrims"`
	News              []*NewsItemOut         `json:"news"`
	Notices           []*HomeNoticeItem      `json:"notices"`
	Teams             []*HomeTeamItem        `json:"teams"`
	Agenda            []agenda.Item          `json:"agenda"`
}
