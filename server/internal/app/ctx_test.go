package app

import "testing"

func TestCanUse(t *testing.T) {
	member := &Viewer{ID: 1}
	if !member.CanUse("team_apply") {
		t.Fatal("普通成员默认允许")
	}

	var anon *Viewer
	if anon.CanUse("team_apply") {
		t.Fatal("访客（nil）应拒")
	}

	disabled := &Viewer{ID: 2, Disabled: true, Superuser: true}
	if disabled.CanUse("team_apply") {
		t.Fatal("停用一票否决，超管身份也救不了")
	}

	limited := &Viewer{ID: 3, FeatureDenied: map[Feature]struct{}{"team_apply": {}}}
	if limited.CanUse("team_apply") {
		t.Fatal("单人限制要拒")
	}
	if !limited.CanUse("article_submit") {
		t.Fatal("只拒被限的那项")
	}

	admin := &Viewer{ID: 4, Superuser: true, FeatureDenied: map[Feature]struct{}{"team_apply": {}}}
	if !admin.CanUse("team_apply") {
		t.Fatal("超管绕过单人限制（设计 4.2）")
	}
}

func TestHasCap(t *testing.T) {
	editor := &Viewer{ID: 1, Caps: map[Cap]struct{}{"content.edit_any": {}}}
	if !editor.HasCap("content.edit_any") {
		t.Fatal("有能力")
	}
	if editor.HasCap("teams.admin") {
		t.Fatal("没的能力不该有")
	}

	super := &Viewer{ID: 2, Superuser: true}
	if !super.HasCap("anything") {
		t.Fatal("超管全有")
	}

	var anon *Viewer
	if anon.HasCap("content.edit_any") {
		t.Fatal("访客没有后台能力")
	}
}
