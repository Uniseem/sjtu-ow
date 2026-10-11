package scrims

import (
	"net/http"
	"testing"
	"time"
)

func TestFormatChangeRejectsPreviouslyLoadedBoard(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	users := e.tenPlayers(sid, FormatRQ5)
	board, err := e.svc.GetBoard(e.mgr(), sid, "")
	if err != nil {
		t.Fatal(err)
	}
	sc := e.get(sid)
	if _, err := e.svc.UpdateScrim(e.mgr(), sid, sc.Version, Changes{Format: str(FormatRQ6)}); err != nil {
		t.Fatal(err)
	}
	if got := e.get(sid); got.BoardVersion != board.BoardVersion+1 || got.RosterChangedAt != nil {
		t.Fatalf("uncompiled board: %+v", got)
	}
	_, err = e.svc.Generate(e.mgr(), sid, signupIDs(e, sid, users), board.BoardVersion)
	wantErr(t, err, http.StatusConflict, "分队板刚被改过")
	if e.count(`SELECT COUNT(*) FROM scrim_signups WHERE scrim_id=? AND is_selected=1`, sid) != 0 {
		t.Fatal("stale generate must not persist selection")
	}
}

func TestFormatChangeMarksSavedTeamsStaleEvenWithinSameClockTick(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	users := e.tenPlayers(sid, FormatRQ5)
	board, err := e.svc.GetBoard(e.mgr(), sid, "")
	if err != nil {
		t.Fatal(err)
	}
	generated, err := e.svc.Generate(e.mgr(), sid, signupIDs(e, sid, users), board.BoardVersion)
	if err != nil {
		t.Fatal(err)
	}
	sc := e.get(sid)
	if _, err := e.svc.UpdateScrim(e.mgr(), sid, sc.Version, Changes{Format: str(Open5)}); err != nil {
		t.Fatal(err)
	}
	board, err = e.svc.GetBoard(e.mgr(), sid, "")
	if err != nil || !board.TeamsStale {
		t.Fatalf("format must invalidate saved split: %+v %v", board, err)
	}
	// Models the generator's final transaction after a concurrent format edit.
	err = e.svc.saveTeams(e.mgr(), sid, nil, e.now, generated.Board.BoardVersion)
	wantErr(t, err, http.StatusConflict, "分队板刚被改过")
	if e.count(`SELECT COUNT(*) FROM scrim_signups WHERE scrim_id=? AND team<>''`, sid) != 10 {
		t.Fatal("rejected stale write must preserve saved teams")
	}
	sc = e.get(sid)
	before := sc.BoardVersion
	e.patch(sc, Changes{Format: str(Open5), Title: str("换标题")})
	if e.get(sid).BoardVersion != before {
		t.Fatal("unchanged format and unrelated fields must not invalidate board")
	}
	e.patch(e.get(sid), Changes{Format: str("invalid")})
	if e.get(sid).BoardVersion != before {
		t.Fatal("rejected format must not invalidate board")
	}
}

func TestGameInputsInvalidateOnlyBoardsUsingThatAccount(t *testing.T) {
	for _, change := range []struct {
		name string
		sql  string
	}{
		{"tank", `UPDATE game_accounts SET rank_tank=rank_tank+1 WHERE id=?`},
		{"damage", `UPDATE game_accounts SET rank_damage=rank_damage+1 WHERE id=?`},
		{"support", `UPDATE game_accounts SET rank_support=NULL WHERE id=?`},
		{"tag", `UPDATE game_accounts SET battletag='Changed#1234',battletag_norm='changed#1234' WHERE id=?`},
		{"delete", `DELETE FROM game_accounts WHERE id=?`},
	} {
		t.Run(change.name, func(t *testing.T) {
			e := newEnv(t)
			sid := e.scrim()
			uid := e.user("甲", 2000, 2100, 2200)
			e.signup(sid, uid, Tank, Damage, Support)
			account := e.account(uid)
			other := e.scrim()
			e.exec(`INSERT INTO game_accounts (user_id,battletag,battletag_norm,ranks_updated_at,created_at,updated_at)
				VALUES (?,'Other#1234','other#1234',?,?,?)`, uid, ts(t0), ts(t0), ts(t0))
			var otherAccount int64
			if err := e.d.ReadPool().QueryRow(`SELECT id FROM game_accounts WHERE battletag='Other#1234'`).Scan(&otherAccount); err != nil {
				t.Fatal(err)
			}
			e.exec(`INSERT INTO scrim_signups (scrim_id,user_id,game_account_id,role_tank,created_at,updated_at)
				VALUES (?,?,?,1,?,?)`, other, uid, otherAccount, ts(t0), ts(t0))
			e.exec(`UPDATE scrims SET teams_generated_at=? WHERE id=?`, ts(t0.Add(-time.Hour)), sid)
			before, otherBefore := e.get(sid).BoardVersion, e.get(other).BoardVersion
			e.exec(change.sql, account)
			current := e.get(sid)
			if current.BoardVersion != before+1 || !teamsStale(current) {
				t.Fatalf("changed board not invalidated: %+v", current)
			}
			if e.get(other).BoardVersion != otherBefore {
				t.Fatal("another game ID belonging to the same user must not invalidate its board")
			}
			_, err := e.svc.SaveTeams(e.mgr(), sid, nil, before)
			wantErr(t, err, http.StatusConflict, "分队板刚被改过")
		})
	}
}

func TestGameMetadataAndNoOpRanksPreserveBoardVersion(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	uid := e.user("甲", 2000, 2100, 2200)
	e.signup(sid, uid, Tank)
	before := e.get(sid).BoardVersion
	e.exec(`UPDATE game_accounts SET rank_tank=rank_tank,rank_support=rank_support,
		ranks_updated_at=?,updated_at=?,version=version+1 WHERE id=?`, ts(t0.Add(time.Hour)), ts(t0.Add(time.Hour)), e.account(uid))
	if e.get(sid).BoardVersion != before {
		t.Fatal("metadata-only/no-op update must not invalidate board")
	}
}
