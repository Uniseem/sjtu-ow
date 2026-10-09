package ratelimit

import (
	"testing"
	"time"
)

// 表里的数字和设计附录 C、规则 214–223、规则 6（allauth 那组，241 起进表）
// 里钉住的条目对上。改一个数字这里就红。还没进表的（规则 6 剩下的、215、216、
// 221、223）写在 limits.go 的注释里。
func TestTableMatchesDesign(t *testing.T) {
	want := []Decl{
		{Name: "auth_signup", Kind: PerIP, N: 20, Window: time.Minute},
		{Name: "auth_login", Kind: PerIP, N: 30, Window: time.Minute},
		{Name: "auth_login_failed_key", Kind: PerKey, N: 5, Window: 5 * time.Minute},
		{Name: "auth_verify_email", Kind: PerIP, N: 10, Window: time.Minute},
		{Name: "auth_resend_email_code", Kind: PerIP, N: 10, Window: time.Minute},
		{Name: "auth_resend_email_code_key", Kind: PerKey, N: 1, Window: 10 * time.Second},
		{Name: "auth_reset_password", Kind: PerIP, N: 20, Window: time.Minute},
		{Name: "auth_reset_password_key", Kind: PerKey, N: 5, Window: time.Minute},
		{Name: "auth_reset_password_confirm", Kind: PerIP, N: 20, Window: time.Minute},
		{Name: "auth_change_password", Kind: PerUser, N: 5, Window: time.Minute},
		{Name: "team_apply", Kind: PerUser, N: 20, Window: 24 * time.Hour},
		{Name: "team_create", Kind: PerUser, N: 3, Window: 24 * time.Hour},
		{Name: "comment_create_minute", Kind: PerUser, N: 3, Window: time.Minute},
		{Name: "comment_create_daily", Kind: PerUser, N: 100, Window: 24 * time.Hour},
		{Name: "comment_vote", Kind: PerUser, N: 60, Window: time.Minute},
		{Name: "search", Kind: PerIP, N: 30, Window: time.Minute},
		{Name: "account_export", Kind: PerUser, N: 5, Window: time.Hour},
	}
	got := []Decl{
		AuthSignup, AuthLogin, AuthLoginFailedKey, AuthVerifyEmail,
		AuthResendEmailCode, AuthResendEmailCodeKey,
		AuthResetPassword, AuthResetPasswordKey, AuthResetPasswordConfirm,
		AuthChangePassword,
		TeamApply, TeamCreate, CommentCreateMinute, CommentCreateDaily,
		CommentVote, Search, AccountExport,
	}
	if len(got) != len(want) {
		t.Fatalf("表有 %d 条，对照 %d 条", len(got), len(want))
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("第 %d 条：得到 %+v，要 %+v", i, got[i], want[i])
		}
	}
}

// 三种窗口各落进对应的时间片。小时级若被算成分钟，account_export 就每分钟 5 次。
func TestSliceMatchesWindow(t *testing.T) {
	t0 := time.Date(2026, 10, 8, 12, 34, 56, 0, time.UTC)
	if g := sliceOf(t0, 10*time.Second); g != "20261008T123450" {
		t.Errorf("10秒片：%s", g)
	}
	if d := untilNextSlice(t0, 10*time.Second); d != 4*time.Second {
		t.Errorf("到下一10秒片应是 4 秒，得到 %s", d)
	}
	if g := sliceOf(t0, time.Minute); g != "20261008T1234" {
		t.Errorf("分钟片：%s", g)
	}
	if g := sliceOf(t0, time.Hour); g != "20261008T12" {
		t.Errorf("小时片：%s", g)
	}
	if g := sliceOf(t0, 24*time.Hour); g != "20261008" {
		t.Errorf("天片：%s", g)
	}
	if d := untilNextSlice(t0, time.Hour); d != 25*time.Minute+4*time.Second {
		t.Errorf("到下一小时应是 25 分 4 秒，得到 %s", d)
	}
}
