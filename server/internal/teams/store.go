package teams

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Store 是战队域的读写层。读用只读池、写用事务，两边都认 db.DBTX。
type Store struct {
	d *db.DB
}

// NewStore 造战队存储；d 可以是 nil（apigen 只要注册路由）。
func NewStore(d *db.DB) *Store { return &Store{d: d} }

func nullTime(ns sql.NullString) *time.Time {
	if !ns.Valid || ns.String == "" {
		return nil
	}
	t, err := db.ParseUTC(ns.String)
	if err != nil {
		return nil
	}
	return &t
}

func parseTime(s string) time.Time {
	t, _ := db.ParseUTC(s)
	return t
}

func b2i(b bool) int {
	if b {
		return 1
	}
	return 0
}

const teamCols = `id, name, description, logo_image_id, is_recruiting, recruiting_roles,
	member_contact, disbanded_at, version, created_at, updated_at`

func scanTeam(row interface{ Scan(...any) error }) (*Team, error) {
	var t Team
	var logo sql.NullInt64
	var recruiting int
	var roles string
	var disbanded sql.NullString
	var created, updated string
	if err := row.Scan(&t.ID, &t.Name, &t.Description, &logo, &recruiting, &roles,
		&t.MemberContact, &disbanded, &t.Version, &created, &updated); err != nil {
		return nil, err
	}
	if logo.Valid {
		v := logo.Int64
		t.LogoImageID = &v
	}
	t.IsRecruiting = recruiting == 1
	t.RecruitingRoles = accounts.ParseRoles(roles)
	t.DisbandedAt = nullTime(disbanded)
	t.CreatedAt = parseTime(created)
	t.UpdatedAt = parseTime(updated)
	return &t, nil
}

// GetTeam 读一支战队（含已解散的）；不存在返回 nil。
func (s *Store) GetTeam(ctx context.Context, q db.DBTX, id int64) (*Team, error) {
	t, err := scanTeam(q.QueryRowContext(ctx, `SELECT `+teamCols+` FROM teams WHERE id = ?`, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return t, err
}

// NameTaken 报队名（不分大小写）是不是被某支未解散的战队占了；exclude 是改名时排除自己。
func (s *Store) NameTaken(ctx context.Context, q db.DBTX, name string, exclude int64) (bool, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM teams
		WHERE disbanded_at IS NULL AND lower(name) = lower(?) AND id <> ?`, name, exclude).Scan(&n)
	return n > 0, err
}

// Limits 是全站设置里战队的两个上限（规则 85、86）。
type Limits struct {
	MaxMembers   int
	MaxCaptained int
}

// GetLimits 读上限；设置行缺了就用默认的 10 和 3。
func (s *Store) GetLimits(ctx context.Context, q db.DBTX) (Limits, error) {
	l := Limits{MaxMembers: 10, MaxCaptained: 3}
	var members, captained int
	err := q.QueryRowContext(ctx, `SELECT team_max_members, team_max_captained FROM site_settings WHERE id = 1`).
		Scan(&members, &captained)
	if errors.Is(err, sql.ErrNoRows) {
		return l, nil
	}
	if err != nil {
		return l, err
	}
	if members > 0 {
		l.MaxMembers = members
	}
	if captained > 0 {
		l.MaxCaptained = captained
	}
	return l, nil
}

// MemberCount 数一支队现在有几个人。
func (s *Store) MemberCount(ctx context.Context, q db.DBTX, teamID int64) (int, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM team_memberships WHERE team_id = ?`, teamID).Scan(&n)
	return n, err
}

// CaptainedCount 数一个人现在担任几支未解散战队的队长（规则 85）。
func (s *Store) CaptainedCount(ctx context.Context, q db.DBTX, userID int64) (int, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM team_memberships m
		JOIN teams t ON t.id = m.team_id
		WHERE m.user_id = ? AND m.role = 'captain' AND t.disbanded_at IS NULL`, userID).Scan(&n)
	return n, err
}

// GetMembership 读一个人在一支队里的身份；不在队里返回 nil。
func (s *Store) GetMembership(ctx context.Context, q db.DBTX, teamID, userID int64) (*Membership, error) {
	var m Membership
	var joined string
	err := q.QueryRowContext(ctx, `SELECT id, team_id, user_id, role, joined_at
		FROM team_memberships WHERE team_id = ? AND user_id = ?`, teamID, userID).
		Scan(&m.ID, &m.TeamID, &m.UserID, &m.Role, &joined)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	m.JoinedAt = parseTime(joined)
	return &m, nil
}

// CaptainOf 读一支队的队长成员关系；没有队长返回 nil。
func (s *Store) CaptainOf(ctx context.Context, q db.DBTX, teamID int64) (*Membership, error) {
	var m Membership
	var joined string
	err := q.QueryRowContext(ctx, `SELECT id, team_id, user_id, role, joined_at
		FROM team_memberships WHERE team_id = ? AND role = 'captain'`, teamID).
		Scan(&m.ID, &m.TeamID, &m.UserID, &m.Role, &joined)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	m.JoinedAt = parseTime(joined)
	return &m, nil
}

// CaptainStopped 报这支未解散的战队有没有「无队长」的问题：没有队长，或队长账号已停用（规则 108）。
func (s *Store) CaptainStopped(ctx context.Context, q db.DBTX, teamID int64) (bool, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM team_memberships m
		JOIN users u ON u.id = m.user_id
		WHERE m.team_id = ? AND m.role = 'captain' AND u.is_active = 1`, teamID).Scan(&n)
	return n == 0, err
}

// UserBrief 是战队页上一个人的最少信息。
type UserBrief struct {
	ID       int64
	Nickname string
	Email    string
	Active   bool
	Verified bool
	MainRole string
	Flex     string
	ShowRank bool
	Motto    string
}

// GetUserBrief 读用户的基本信息；不存在返回 nil。
func (s *Store) GetUserBrief(ctx context.Context, q db.DBTX, id int64) (*UserBrief, error) {
	var u UserBrief
	var active, show int
	var verified sql.NullString
	err := q.QueryRowContext(ctx, `SELECT id, nickname, email, is_active, email_verified_at,
		main_role, flex_roles, show_rank, motto FROM users WHERE id = ?`, id).
		Scan(&u.ID, &u.Nickname, &u.Email, &active, &verified, &u.MainRole, &u.Flex, &show, &u.Motto)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	u.Active = active == 1
	u.Verified = verified.Valid && verified.String != ""
	u.ShowRank = show == 1
	return &u, nil
}

// GameAccountCount 数一个人绑了几个游戏 ID。
func (s *Store) GameAccountCount(ctx context.Context, q db.DBTX, userID int64) (int, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM game_accounts WHERE user_id = ?`, userID).Scan(&n)
	return n, err
}

// GameAccountsFor 一次取一批人的游戏 ID（战队页每个人的段位，不做 N+1）。
func (s *Store) GameAccountsFor(ctx context.Context, q db.DBTX, userIDs []int64) (map[int64][]accounts.GameAccount, error) {
	return accounts.LoadGameAccounts(ctx, q, userIDs)
}

const appCols = `id, team_id, applicant_id, role_tank, role_damage, role_support, message, status,
	decided_by, decided_at, decision_note, captain_reminded_at, created_at`

func scanApplication(row interface{ Scan(...any) error }) (*Application, error) {
	var a Application
	var tank, damage, support int
	var by sql.NullInt64
	var decided, reminded sql.NullString
	var created string
	if err := row.Scan(&a.ID, &a.TeamID, &a.ApplicantID, &tank, &damage, &support, &a.Message, &a.Status,
		&by, &decided, &a.DecisionNote, &reminded, &created); err != nil {
		return nil, err
	}
	a.RoleTank, a.RoleDamage, a.RoleSupport = tank == 1, damage == 1, support == 1
	if by.Valid {
		v := by.Int64
		a.DecidedBy = &v
	}
	a.DecidedAt = nullTime(decided)
	a.CaptainRemindedAt = nullTime(reminded)
	a.CreatedAt = parseTime(created)
	return &a, nil
}

// GetApplication 读一条申请；不存在返回 nil。
func (s *Store) GetApplication(ctx context.Context, q db.DBTX, id int64) (*Application, error) {
	a, err := scanApplication(q.QueryRowContext(ctx, `SELECT `+appCols+` FROM team_applications WHERE id = ?`, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return a, err
}

// HasPendingApplication 报这个人对这支队有没有待审申请。
func (s *Store) HasPendingApplication(ctx context.Context, q db.DBTX, teamID, userID int64) (bool, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM team_applications
		WHERE team_id = ? AND applicant_id = ? AND status = 'pending'`, teamID, userID).Scan(&n)
	return n > 0, err
}

// DecideApplication 把申请改成终态（通过、拒绝、取消）。
func (s *Store) DecideApplication(ctx context.Context, tx *db.Tx, id int64, status string, by *int64, at time.Time, note string) error {
	var byArg any
	if by != nil {
		byArg = *by
	}
	_, err := tx.ExecContext(ctx, `UPDATE team_applications
		SET status = ?, decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?`,
		status, byArg, db.FormatUTC(at), note, id)
	return err
}

// RetireTx 写退役记录（同一个人同一支队只留一条，再退再覆盖）。
func (s *Store) RetireTx(ctx context.Context, tx *db.Tx, m *Membership, reason string, at time.Time) error {
	_, err := tx.ExecContext(ctx, `INSERT INTO team_alumni (team_id, user_id, role, joined_at, left_at, reason)
		VALUES (?, ?, ?, ?, ?, ?)
		ON CONFLICT (team_id, user_id) DO UPDATE SET
			role = excluded.role, joined_at = excluded.joined_at,
			left_at = excluded.left_at, reason = excluded.reason`,
		m.TeamID, m.UserID, m.Role, db.FormatUTC(m.JoinedAt), db.FormatUTC(at), reason)
	return err
}

// UnretireTx 重新入队：一个人不同时是现役和退役（规则 93、98）。
func (s *Store) UnretireTx(ctx context.Context, tx *db.Tx, teamID, userID int64) error {
	_, err := tx.ExecContext(ctx, `DELETE FROM team_alumni WHERE team_id = ? AND user_id = ?`, teamID, userID)
	return err
}

// Touch 给战队加一版（改资料、改成员后让编辑中的页面发现过期）。
func (s *Store) Touch(ctx context.Context, tx *db.Tx, teamID int64, at time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE teams SET version = version + 1, updated_at = ? WHERE id = ?`,
		db.FormatUTC(at), teamID)
	return err
}
