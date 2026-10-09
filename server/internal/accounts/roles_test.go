package accounts

import (
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

func TestCapsForRole(t *testing.T) {
	matrix := map[string][]app.Cap{
		RoleContentEditor: {
			CapAdminEnter,
			CapArticlesPublishOwn,
			CapArticlesEditAny,
			CapArticlesEditAuthor,
			CapArticleCategories,
			CapSitePages,
			CapImagesContribute,
			CapImagesManage,
			CapCommentsModerate,
			CapModerationReview,
			CapMemberGroups,
			CapActivityView,
		},
		RoleCertifiedAuthor: {
			CapAdminEnter,
			CapArticlesPublishOwn,
			CapImagesContribute,
			CapActivityView,
		},
		RoleTournamentAdmin: {
			CapAdminEnter,
			CapTournamentsManage,
			CapContactsView,
			CapActivityView,
		},
		RoleScrimAdmin: {
			CapAdminEnter,
			CapScrimsManage,
			CapContactsView,
			CapActivityView,
		},
		RoleContributor: {
			CapAdminEnter,
			CapArticlesPublishOwn,
			CapImagesContribute,
		},
		RoleSJTU:     nil,
		RoleExternal: nil,
		"unknown":    nil,
	}

	for role, expected := range matrix {
		got := CapsForRole(role)
		if len(got) != len(expected) {
			t.Fatalf("角色 %s 的能力数量=%d，期望=%d", role, len(got), len(expected))
		}
		gotSet := make(map[app.Cap]struct{})
		for _, c := range got {
			gotSet[c] = struct{}{}
		}
		for _, exp := range expected {
			if _, ok := gotSet[exp]; !ok {
				t.Fatalf("角色 %s 缺少能力 %s", role, exp)
			}
		}
	}
}

// 契约 R009、R013、R014：派生角色与投稿者组资格同步
func TestDerivedRoles(t *testing.T) {
	cases := []struct {
		name             string
		isSJTU           bool
		isActive         bool
		emailVerified    bool
		canSubmitArticle bool
		wantRoles        []string
		doNotWant        []string
	}{
		{
			name:             "交大普通用户",
			isSJTU:           true,
			isActive:         true,
			emailVerified:    false,
			canSubmitArticle: true,
			wantRoles:        []string{RoleSJTU},
			doNotWant:        []string{RoleExternal, RoleContributor},
		},
		{
			name:             "校外已验证投稿者",
			isSJTU:           false,
			isActive:         true,
			emailVerified:    true,
			canSubmitArticle: true,
			wantRoles:        []string{RoleExternal, RoleContributor},
			doNotWant:        []string{RoleSJTU},
		},
		{
			name:             "投稿功能被禁的交大用户",
			isSJTU:           true,
			isActive:         true,
			emailVerified:    true,
			canSubmitArticle: false,
			wantRoles:        []string{RoleSJTU},
			doNotWant:        []string{RoleExternal, RoleContributor},
		},
		{
			name:             "未激活的交大用户不能获得投稿者角色",
			isSJTU:           true,
			isActive:         false,
			emailVerified:    true,
			canSubmitArticle: true,
			wantRoles:        []string{RoleSJTU},
			doNotWant:        []string{RoleExternal, RoleContributor},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			roles := DerivedRoles(tc.isSJTU, tc.isActive, tc.emailVerified, tc.canSubmitArticle)
			roleSet := make(map[string]bool)
			for _, r := range roles {
				roleSet[r] = true
			}
			for _, want := range tc.wantRoles {
				if !roleSet[want] {
					t.Fatalf("缺少期望派生角色 %s", want)
				}
			}
			for _, bad := range tc.doNotWant {
				if roleSet[bad] {
					t.Fatalf("不应包含派生角色 %s", bad)
				}
			}
		})
	}
}

// 契约 R011、R012：can_use 判定顺序（停用拒、单人优先、组限制、默认允许）与固定拒绝文案
func TestCanUse(t *testing.T) {
	verified := time.Now()
	activeUser := &User{ID: 1, IsActive: true, IsSJTU: true, EmailVerifiedAt: &verified}
	inactiveUser := &User{ID: 2, IsActive: false}
	superUser := &User{ID: 3, IsActive: true, IsSuperuser: true}

	// 1. 未登录 / 停用
	if allowed, err := CanUse(nil, FeatureArticleSubmit, nil, nil, nil); err != nil || allowed {
		t.Fatalf("未登录应拒绝且无错误，得到 allowed=%v, err=%v", allowed, err)
	}
	if allowed, err := CanUse(inactiveUser, FeatureArticleSubmit, nil, nil, nil); err != nil || allowed {
		t.Fatalf("停用用户应拒绝且无错误，得到 allowed=%v, err=%v", allowed, err)
	}

	// 2. 未知 feature
	if _, err := CanUse(activeUser, "unknown_feature", nil, nil, nil); err == nil {
		t.Fatal("未知 feature 应报错")
	}

	// 3. 超管一律允许
	roleRestrs := map[string]map[app.Feature]bool{
		RoleSJTU: {FeatureTeamCreate: true},
	}
	userRules := map[app.Feature]bool{
		FeatureTeamCreate: false,
	}
	if allowed, err := CanUse(superUser, FeatureTeamCreate, userRules, roleRestrs, []string{RoleSJTU}); err != nil || !allowed {
		t.Fatalf("超管应始终允许，得到 allowed=%v, err=%v", allowed, err)
	}

	// 4. 单用户规则优先于角色限制
	// 4a. 角色限制禁止，但单用户单独放行 (userRule=true)
	userRuleAllow := map[app.Feature]bool{FeatureTournamentRegister: true}
	externalRestr := map[string]map[app.Feature]bool{
		RoleExternal: {FeatureTournamentRegister: true},
	}
	extUser := &User{ID: 4, IsActive: true, IsSJTU: false}
	if allowed, err := CanUse(extUser, FeatureTournamentRegister, userRuleAllow, externalRestr, nil); err != nil || !allowed {
		t.Fatalf("单用户放行应覆盖角色限制，得到 allowed=%v, err=%v", allowed, err)
	}

	// 4b. 单用户规则禁止 (userRule=false)，角色没有限制
	userRuleDeny := map[app.Feature]bool{FeatureArticleComment: false}
	if allowed, err := CanUse(activeUser, FeatureArticleComment, userRuleDeny, nil, nil); err != nil || allowed {
		t.Fatalf("单用户禁止应生效，得到 allowed=%v, err=%v", allowed, err)
	}

	// 5. 角色限制拒绝
	if allowed, err := CanUse(extUser, FeatureTournamentRegister, nil, externalRestr, nil); err != nil || allowed {
		t.Fatalf("角色受限用户应拒绝，得到 allowed=%v, err=%v", allowed, err)
	}

	// 6. 默认全开
	if allowed, err := CanUse(activeUser, FeatureAvatarUpload, nil, nil, nil); err != nil || !allowed {
		t.Fatalf("默认应全开，得到 allowed=%v, err=%v", allowed, err)
	}
}

func TestRunsAdmin(t *testing.T) {
	u := &User{ID: 1, IsActive: true}
	vSuper := &app.Viewer{ID: 1, Superuser: true}
	vStaff := &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{CapAdminEnter: {}}}
	vPlain := &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{}}
	vDisabled := &app.Viewer{ID: 1, Disabled: true, Superuser: true}

	if !RunsAdmin(u, vSuper) {
		t.Fatal("超管应有后台入口")
	}
	if !RunsAdmin(u, vStaff) {
		t.Fatal("拥有 CapAdminEnter 应有后台入口")
	}
	if RunsAdmin(u, vPlain) {
		t.Fatal("普通成员不应有后台入口")
	}
	if RunsAdmin(u, vDisabled) {
		t.Fatal("停用用户不应有后台入口")
	}
	if RunsAdmin(nil, vSuper) {
		t.Fatal("nil 用户不应有后台入口")
	}
}
