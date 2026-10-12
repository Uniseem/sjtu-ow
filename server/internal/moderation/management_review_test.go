package moderation

import "testing"

func TestAllStatusesAndMottoClearRemainReviewerOnly(t *testing.T) {
	e := newEnv(t)
	e.enable()
	reviewer := e.reviewer()
	user := e.user("作者")
	e.exec(`UPDATE users SET motto='需要清空的宣言' WHERE id=?`, user)
	pending := e.seed(TargetMotto, user, "high", StatusPending, true, user)
	e.seed(TargetNickname, user, "low", StatusHandled, true, user)
	all, err := e.svc.List(reviewer, ListInput{All: true})
	if err != nil {
		t.Fatal(err)
	}
	if len(all.Items) != 2 {
		t.Fatal("all-states filter still only returned pending")
	}
	if all.Items[0].AuthorName != "作者" {
		t.Fatal("review list omitted author display name")
	}
	if _, err = e.svc.handle(reviewer, pending, "handled", "清空违规宣言", true); err != nil {
		t.Fatal(err)
	}
	var motto string
	var version int
	if err = e.d.ReadPool().QueryRow(`SELECT motto,version FROM users WHERE id=?`, user).Scan(&motto, &version); err != nil {
		t.Fatal(err)
	}
	if motto != "" || version != 2 {
		t.Fatal("motto disposition did not invalidate profile version")
	}
	detail, err := e.svc.Get(reviewer, pending)
	if err != nil {
		t.Fatal(err)
	}
	if detail.Item.ReviewerName != "内容编辑" || len(detail.HistoryRows) != 1 {
		t.Fatal("review audit projection omitted actor/history")
	}
}
