package accounts

import (
	"context"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// ExportTeam 是导出里「我在哪些战队」的一条（现役）。
type ExportTeam struct {
	TeamID   int64     `json:"team_id"`
	Name     string    `json:"name"`
	Role     string    `json:"role"`
	JoinedAt time.Time `json:"joined_at"`
}

// ExportApplication 是导出里我提交过的一条入队申请。
type ExportApplication struct {
	ID        int64     `json:"id"`
	TeamID    int64     `json:"team_id"`
	TeamName  string    `json:"team_name"`
	Roles     []string  `json:"roles"`
	Message   string    `json:"message"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

// ExportAlumnus 是导出里我的一条退役记录。
type ExportAlumnus struct {
	TeamID   int64     `json:"team_id"`
	TeamName string    `json:"team_name"`
	Role     string    `json:"role"`
	JoinedAt time.Time `json:"joined_at"`
	LeftAt   time.Time `json:"left_at"`
	Reason   string    `json:"reason"`
}

// ExportGroup 是导出里我所在的一个成员分组。
type ExportGroup struct {
	GroupID int64  `json:"group_id"`
	Name    string `json:"name"`
	Title   string `json:"title"`
}

func (s *Store) fillTeamExport(ctx context.Context, userID int64, out *AccountExportData) error {
	rd := s.d.ReadPool()
	out.Teams, out.TeamApplications = []ExportTeam{}, []ExportApplication{}
	out.TeamAlumni, out.MemberGroups = []ExportAlumnus{}, []ExportGroup{}

	rows, err := rd.QueryContext(ctx, `SELECT t.id, t.name, m.role, m.joined_at FROM team_memberships m
		JOIN teams t ON t.id = m.team_id WHERE m.user_id = ? ORDER BY m.id`, userID)
	if err != nil {
		return err
	}
	for rows.Next() {
		var e ExportTeam
		var at string
		if err := rows.Scan(&e.TeamID, &e.Name, &e.Role, &at); err != nil {
			rows.Close()
			return err
		}
		e.JoinedAt, _ = db.ParseUTC(at)
		out.Teams = append(out.Teams, e)
	}
	rows.Close()

	rows, err = rd.QueryContext(ctx, `SELECT a.id, a.team_id, t.name, a.role_tank, a.role_damage, a.role_support,
		a.message, a.status, a.created_at FROM team_applications a JOIN teams t ON t.id = a.team_id
		WHERE a.applicant_id = ? ORDER BY a.id`, userID)
	if err != nil {
		return err
	}
	for rows.Next() {
		var e ExportApplication
		var tank, damage, support int
		var at string
		if err := rows.Scan(&e.ID, &e.TeamID, &e.TeamName, &tank, &damage, &support, &e.Message, &e.Status, &at); err != nil {
			rows.Close()
			return err
		}
		e.Roles = []string{}
		for i, on := range []int{tank, damage, support} {
			if on == 1 {
				e.Roles = append(e.Roles, RoleOrder[i])
			}
		}
		e.CreatedAt, _ = db.ParseUTC(at)
		out.TeamApplications = append(out.TeamApplications, e)
	}
	rows.Close()

	rows, err = rd.QueryContext(ctx, `SELECT a.team_id, t.name, a.role, a.joined_at, a.left_at, a.reason
		FROM team_alumni a JOIN teams t ON t.id = a.team_id WHERE a.user_id = ? ORDER BY a.id`, userID)
	if err != nil {
		return err
	}
	for rows.Next() {
		var e ExportAlumnus
		var joined, left string
		if err := rows.Scan(&e.TeamID, &e.TeamName, &e.Role, &joined, &left, &e.Reason); err != nil {
			rows.Close()
			return err
		}
		e.JoinedAt, _ = db.ParseUTC(joined)
		e.LeftAt, _ = db.ParseUTC(left)
		out.TeamAlumni = append(out.TeamAlumni, e)
	}
	rows.Close()

	rows, err = rd.QueryContext(ctx, `SELECT g.id, g.name, m.title FROM member_group_memberships m
		JOIN member_groups g ON g.id = m.group_id WHERE m.user_id = ? ORDER BY g.sort_order, g.id`, userID)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var e ExportGroup
		if err := rows.Scan(&e.GroupID, &e.Name, &e.Title); err != nil {
			return err
		}
		out.MemberGroups = append(out.MemberGroups, e)
	}
	return rows.Err()
}
