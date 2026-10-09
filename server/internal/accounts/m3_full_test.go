package accounts

import (
	"context"
	"database/sql"
	"fmt"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// helper 造一个带 Session 的 app.Ctx
func newTestCtx(ctx context.Context, u *User, token string, superuser bool, caps ...app.Cap) *app.Ctx {
	cMap := make(map[app.Cap]struct{})
	for _, c := range caps {
		cMap[c] = struct{}{}
	}
	var viewer *app.Viewer
	if u != nil {
		viewer = &app.Viewer{
			ID:            u.ID,
			Disabled:      !u.IsActive,
			EmailVerified: u.EmailVerified(),
			Superuser:     superuser || u.IsSuperuser,
			Caps:          cMap,
		}
	} else if superuser || len(caps) > 0 {
		viewer = &app.Viewer{
			ID:            999999,
			Disabled:      false,
			EmailVerified: true,
			Superuser:     superuser,
			Caps:          cMap,
		}
	}
	return &app.Ctx{
		Context:      ctx,
		Viewer:       viewer,
		Clock:        clock.System{},
		SessionToken: token,
	}
}

// 契约 R006, R007: 重新认证与 5 分钟重认证窗口
func TestReauthenticateAndEmailChange(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	sessStore := auth.NewStore(d, clk)
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", sessStore, nil)
	svc.codeGen = fixedCode("123456")

	u := newVerifiedUser(t, d, "old@sjtu.edu.cn", "老邮箱用户", "Password123!@#", true)
	token, err := sessStore.Create(ctx, u.ID)
	if err != nil {
		t.Fatalf("Create session: %v", err)
	}

	appCtx := newTestCtx(ctx, u, token, false)

	// 1. 输错密码重认证 -> 失败
	_, err = svc.Reauthenticate(appCtx, ReauthInput{Password: "WrongPassword!@#"})
	if err == nil {
		t.Fatal("密码错误应重认证失败")
	}

	// 2. 未重认证换邮箱 -> 拒绝 (规则 7)
	_, err = svc.RequestEmailChange(appCtx, RequestEmailChangeInput{NewEmail: "new@sjtu.edu.cn"})
	if err == nil {
		t.Fatal("未重认证应拒绝换邮箱")
	}

	// 3. 输对密码重认证 -> 成功并记录 ReauthAt
	reauthRes, err := svc.Reauthenticate(appCtx, ReauthInput{Password: "Password123!@#"})
	if err != nil || reauthRes.Result != "ok" {
		t.Fatalf("重认证失败: %+v, err=%v", reauthRes, err)
	}

	sess, err := sessStore.Lookup(ctx, token)
	if err != nil || sess == nil || !sess.RecentlyReauthed(clk.Now()) {
		t.Fatalf("会话应在重认证窗口内: %+v", sess)
	}

	// 4. 换成相同邮箱 -> 报错
	_, err = svc.RequestEmailChange(appCtx, RequestEmailChangeInput{NewEmail: "OLD@sjtu.edu.cn"})
	if err == nil {
		t.Fatal("换成相同邮箱应报错")
	}

	// 5. 换成已被他人绑定的邮箱 -> 报错
	newVerifiedUser(t, d, "taken@sjtu.edu.cn", "别人", "Password123!@#", true)
	_, err = svc.RequestEmailChange(appCtx, RequestEmailChangeInput{NewEmail: "taken@sjtu.edu.cn"})
	if err == nil {
		t.Fatal("换成他人已占用邮箱应报错")
	}

	// 6. 申请换绑 -> 成功发码入库
	reqRes, err := svc.RequestEmailChange(appCtx, RequestEmailChangeInput{NewEmail: "new@sjtu.edu.cn"})
	if err != nil || reqRes.Result != "ok" {
		t.Fatalf("申请换邮箱失败: %+v, err=%v", reqRes, err)
	}

	// 7. 核验错误验证码 -> 尝试次数 +1
	_, err = svc.ConfirmEmailChange(appCtx, ConfirmEmailChangeInput{Code: "000000"})
	if err == nil {
		t.Fatal("错误验证码应报错")
	}

	// 8. 核验正确验证码 -> 邮箱成功替换
	confirmRes, err := svc.ConfirmEmailChange(appCtx, ConfirmEmailChangeInput{Code: "123456"})
	if err != nil || confirmRes.Result != "ok" {
		t.Fatalf("核验新邮箱失败: %+v, err=%v", confirmRes, err)
	}

	updatedUser, err := svc.Store().GetByID(ctx, u.ID)
	if err != nil || updatedUser == nil {
		t.Fatalf("读取更新后用户失败: %v", err)
	}
	if updatedUser.Email != "new@sjtu.edu.cn" || updatedUser.EmailNorm != "new@sjtu.edu.cn" {
		t.Fatalf("邮箱未正确替换: %+v", updatedUser)
	}
}

// 契约 R018, R020, R021: 个人资料、宣言防外链、公开段位与过期
func TestProfileMottoAndPublicRanks(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := clock.Fixed(now)
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	u := newVerifiedUser(t, d, "profile@sjtu.edu.cn", "资料测试", "Password123!@#", true)
	appCtx := newTestCtx(ctx, u, "", false)

	// 1. 个人资料修改：非法昵称 (<2 字符 或 >16 字符)
	_, err := svc.UpdateProfile(appCtx, UpdateProfileInput{Nickname: "A"})
	if err == nil {
		t.Fatal("昵称太短应拒绝")
	}

	// 2. 个人资料修改：宣言含外链拦截 (规则 20)
	for _, badMotto := range []string{
		"看视频 http://bilibili.com",
		"访问 www.mysite.com",
		"加群 qq.top",
	} {
		_, err := svc.UpdateProfile(appCtx, UpdateProfileInput{Nickname: "正常昵称", Motto: badMotto})
		if err == nil || !strings.Contains(err.Error(), "链接") {
			t.Fatalf("宣言含链接 %q 应被拦截: err=%v", badMotto, err)
		}
	}

	// 3. 正常修改资料
	updateRes, err := svc.UpdateProfile(appCtx, UpdateProfileInput{
		Nickname:  "守望先锋先锋",
		Motto:     "这是合法的个人宣言",
		MainRole:  "tank",
		FlexRoles: "damage,support",
		ShowRank:  true,
	})
	if err != nil || updateRes.Result != "ok" {
		t.Fatalf("更新资料失败: %+v, err=%v", updateRes, err)
	}

	// 4. 读取个人中心：当前无游戏 ID，无联系方式 -> IsComplete 应为 false (规则 18)
	p, err := svc.GetProfile(appCtx)
	if err != nil {
		t.Fatalf("GetProfile: %v", err)
	}
	if p.IsComplete {
		t.Fatal("无游戏ID和联系方式时资料不完整")
	}
	if p.Nickname != "守望先锋先锋" || p.Motto != "这是合法的个人宣言" {
		t.Fatalf("资料未持久化: %+v", p)
	}

	// 5. 绑定一个游戏 ID（坦克 20 = 钻石5，输出 25 = 大师5）
	t20 := 20
	d25 := 25
	_, err = svc.AddGameAccount(appCtx, AddGameAccountInput{
		Battletag:  "Hero#1234",
		RankTank:   &t20,
		RankDamage: &d25,
	})
	if err != nil {
		t.Fatalf("AddGameAccount: %v", err)
	}

	// 绑定联系方式
	_, err = svc.AddContact(appCtx, AddContactInput{
		Type:  ContactQQ,
		Value: "12345678",
	})
	if err != nil {
		t.Fatalf("AddContact: %v", err)
	}

	// 此时资料应该完整 (规则 18)
	p, err = svc.GetProfile(appCtx)
	if err != nil || !p.IsComplete {
		t.Fatalf("有游戏ID和联系方式后资料应完整: %+v", p)
	}
	if p.PublicRanks.Tank.Label != "钻石 5" || p.PublicRanks.Damage.Label != "大师 5" {
		t.Fatalf("公开最高段位计算错误: %+v", p.PublicRanks)
	}

	// 6. 段位超过 180 天过期标记 (规则 21)
	oldTime := now.Add(-181 * 24 * time.Hour)
	_, err = d.WritePool().ExecContext(ctx, `UPDATE game_accounts SET ranks_updated_at = ? WHERE user_id = ?`,
		db.FormatUTC(oldTime), u.ID)
	if err != nil {
		t.Fatal(err)
	}

	p, err = svc.GetProfile(appCtx)
	if err != nil || !p.PublicRanks.Tank.IsExpired || !p.PublicRanks.Damage.IsExpired {
		t.Fatalf("超过 180 天的段位应被标记为过期: %+v", p.PublicRanks)
	}
}

// 契约 R016, R017: 游戏 ID 格式校验、小写唯一、上限 5 个
func TestGameAccountsConstraints(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	u1 := newVerifiedUser(t, d, "u1@sjtu.edu.cn", "用户1", "Password123!@#", true)
	u2 := newVerifiedUser(t, d, "u2@sjtu.edu.cn", "用户2", "Password123!@#", true)
	ctx1 := newTestCtx(ctx, u1, "", false)
	ctx2 := newTestCtx(ctx, u2, "", false)

	// 1. 格式校验
	for _, badTag := range []string{"NoHash", "Space Tag#1234", "X#12", "WayTooLongNicknameHere#1234", "Name#1234567"} {
		_, err := svc.AddGameAccount(ctx1, AddGameAccountInput{Battletag: badTag})
		if err == nil {
			t.Fatalf("非法 BattleTag %q 应被拒绝", badTag)
		}
	}

	// 2. 正常绑定
	ga1, err := svc.AddGameAccount(ctx1, AddGameAccountInput{Battletag: "Player#1234"})
	if err != nil {
		t.Fatalf("AddGameAccount: %v", err)
	}

	// 3. 大小写不敏感全局唯一 (规则 17)
	_, err = svc.AddGameAccount(ctx2, AddGameAccountInput{Battletag: "PLAYER#1234"})
	if err == nil || !strings.Contains(err.Error(), "已被其他账号绑定") {
		t.Fatalf("重复绑定（大小写不敏感）应拒绝: %v", err)
	}

	// 4. 上限 5 个 (规则 16)
	for i := 2; i <= 5; i++ {
		tag := fmt.Sprintf("Extra#100%d", i)
		_, err := svc.AddGameAccount(ctx1, AddGameAccountInput{Battletag: tag})
		if err != nil {
			t.Fatalf("第 %d 个绑定失败: %v", i, err)
		}
	}
	_, err = svc.AddGameAccount(ctx1, AddGameAccountInput{Battletag: "Extra#1006"})
	if err == nil || !strings.Contains(err.Error(), "最多绑定 5 个") {
		t.Fatalf("第 6 个游戏 ID 应被拒绝: %v", err)
	}

	// 5. 更新段位
	newRank := 30
	updated, err := svc.UpdateGameAccount(ctx1, UpdateGameAccountInput{
		ID:       api.ID(ga1.ID),
		RankTank: &newRank,
	})
	if err != nil || updated.TankLabel != "宗师 5" {
		t.Fatalf("UpdateGameAccount 失败: %+v, err=%v", updated, err)
	}

	// 6. 删除游戏 ID
	delRes, err := svc.DeleteGameAccount(ctx1, ga1.ID)
	if err != nil || delRes.Result != "ok" {
		t.Fatalf("DeleteGameAccount: %v", err)
	}
}

// 契约 R019: 联系方式类型校验与每种仅限 1 条
func TestContactsConstraints(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	u := newVerifiedUser(t, d, "contact@sjtu.edu.cn", "联系人", "Password123!@#", true)
	appCtx := newTestCtx(ctx, u, "", false)

	// 1. 格式校验
	_, err := svc.AddContact(appCtx, AddContactInput{Type: ContactQQ, Value: "123"}) // qq太短
	if err == nil {
		t.Fatal("QQ 号太短应报错")
	}
	_, err = svc.AddContact(appCtx, AddContactInput{Type: ContactPhone, Value: "22345678901"}) // 不是 1 开头
	if err == nil {
		t.Fatal("非大陆手机号应报错")
	}

	// 2. 正常添加 QQ
	c1, err := svc.AddContact(appCtx, AddContactInput{Type: ContactQQ, Value: "12345678"})
	if err != nil {
		t.Fatalf("AddContact: %v", err)
	}

	// 3. 重复添加相同类型 -> 拒绝 (规则 19)
	_, err = svc.AddContact(appCtx, AddContactInput{Type: ContactQQ, Value: "87654321"})
	if err == nil || !strings.Contains(err.Error(), "只能填写一次") {
		t.Fatalf("每种类型只能填一条: %v", err)
	}

	// 4. 删除联系方式
	delRes, err := svc.DeleteContact(appCtx, c1.ID)
	if err != nil || delRes.Result != "ok" {
		t.Fatalf("DeleteContact: %v", err)
	}
}

// 契约 R028–R032: 账号原地匿名化注销、不可用密码、级联清理
func TestAccountDeletion(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	sessStore := auth.NewStore(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", sessStore, nil)

	u := newVerifiedUser(t, d, "delete-me@sjtu.edu.cn", "待注销用户", "Password123!@#", true)
	token, _ := sessStore.Create(ctx, u.ID)
	appCtx := newTestCtx(ctx, u, token, false)

	// 绑定游戏 ID 和联系方式
	_, _ = svc.AddGameAccount(appCtx, AddGameAccountInput{Battletag: "Player#1234"})
	_, _ = svc.AddContact(appCtx, AddContactInput{Type: ContactQQ, Value: "12345678"})

	// 1. 密码错误 -> 拒绝
	_, err := svc.DeleteAccount(appCtx, DeleteAccountInput{Password: "WrongPass!@#"})
	if err == nil {
		t.Fatal("密码错误应拒绝注销")
	}

	// 2. 正常注销
	delRes, err := svc.DeleteAccount(appCtx, DeleteAccountInput{Password: "Password123!@#"})
	if err != nil || delRes.Result != "ok" {
		t.Fatalf("注销失败: %+v, err=%v", delRes, err)
	}

	// 3. 校验原地匿名化 (规则 30)
	deletedUser, err := svc.Store().GetByID(ctx, u.ID)
	if err != nil || deletedUser == nil {
		t.Fatalf("用户行不应删除: %v", err)
	}
	expectedEmail := fmt.Sprintf("deleted-%d@deleted.invalid", u.ID)
	if deletedUser.Email != expectedEmail || deletedUser.Nickname != "已注销用户" || deletedUser.IsActive {
		t.Fatalf("用户匿名化数据不符合预期: %+v", deletedUser)
	}
	if !strings.HasPrefix(deletedUser.PasswordHash, "!") {
		t.Fatalf("密码应被置为不可用 (!): %s", deletedUser.PasswordHash)
	}

	// 4. 校验自有数据清理 (规则 31)
	gas, _ := svc.Store().GetGameAccountsByUserID(ctx, u.ID)
	if len(gas) != 0 {
		t.Fatalf("游戏 ID 应已清理: %v", gas)
	}
	contacts, _ := svc.Store().GetContactsByUserID(ctx, u.ID)
	if len(contacts) != 0 {
		t.Fatalf("联系方式应已清理: %v", contacts)
	}

	// 5. 校验会话已作废
	sess, _ := sessStore.Lookup(ctx, token)
	if sess != nil {
		t.Fatal("注销后会话应已删除")
	}
}

// 契约 R033–R036: 停用必须填原因、清会话、注销账号不可重新启用、启用清空原因
func TestDeactivationAndReactivation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	sessStore := auth.NewStore(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", sessStore, nil)

	u := newVerifiedUser(t, d, "suspect@sjtu.edu.cn", "嫌疑人", "Password123!@#", true)
	token, _ := sessStore.Create(ctx, u.ID)
	adminCtx := newTestCtx(ctx, nil, "", true)

	// 1. 停用不填原因 -> 报错 (规则 33)
	_, err := svc.DeactivateUser(adminCtx, DeactivateUserInput{ID: api.ID(u.ID), Reason: ""})
	if err == nil {
		t.Fatal("停用未填原因应报错")
	}

	// 2. 正常停用 -> is_active=0，会话作废 (规则 34)
	deactRes, err := svc.DeactivateUser(adminCtx, DeactivateUserInput{ID: api.ID(u.ID), Reason: "涉嫌作弊"})
	if err != nil || deactRes.Result != "ok" {
		t.Fatalf("停用失败: %+v, err=%v", deactRes, err)
	}

	target, _ := svc.Store().GetByID(ctx, u.ID)
	if target.IsActive || target.DeactivationNote != "涉嫌作弊" {
		t.Fatalf("停用状态不符: %+v", target)
	}

	sess, _ := sessStore.Lookup(ctx, token)
	if sess != nil {
		t.Fatal("停用后会话应已被删除")
	}

	// 3. 重新启用 -> is_active=1, 原因清空 (规则 36)
	reactRes, err := svc.ReactivateUser(adminCtx, ReactivateUserInput{ID: api.ID(u.ID)})
	if err != nil || reactRes.Result != "ok" {
		t.Fatalf("重新启用失败: %+v, err=%v", reactRes, err)
	}

	target, _ = svc.Store().GetByID(ctx, u.ID)
	if !target.IsActive || target.DeactivationNote != "" {
		t.Fatalf("重新启用后状态不符: %+v", target)
	}

	// 4. 注销过的账号不能启用 (规则 35)
	deletedUser := newVerifiedUser(t, d, "del@sjtu.edu.cn", "注销人", "Password123!@#", true)
	userCtx := newTestCtx(ctx, deletedUser, "", false)
	_, _ = svc.DeleteAccount(userCtx, DeleteAccountInput{Password: "Password123!@#"})

	_, err = svc.ReactivateUser(adminCtx, ReactivateUserInput{ID: api.ID(deletedUser.ID)})
	if err == nil || !strings.Contains(err.Error(), "注销账号不能重新启用") {
		t.Fatalf("注销账号启用应报错: %v", err)
	}
}

// 契约 R037, R038: 导出个人数据
func TestExportAccount(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	u := newVerifiedUser(t, d, "exporter@sjtu.edu.cn", "导出者", "Password123!@#", true)
	appCtx := newTestCtx(ctx, u, "", false)

	_, _ = svc.AddGameAccount(appCtx, AddGameAccountInput{Battletag: "Player#1234"})
	_, _ = svc.AddContact(appCtx, AddContactInput{Type: ContactQQ, Value: "12345678"})

	data, err := svc.ExportAccount(appCtx)
	if err != nil {
		t.Fatalf("ExportAccount: %v", err)
	}
	if data.User.ID != u.ID || len(data.GameAccounts) != 1 || len(data.Contacts) != 1 {
		t.Fatalf("导出数据不全: %+v", data)
	}
}

// 契约 R039–R042: 后台用户管理、邮箱隐私、联系方式权限
func TestAdminUsersVisibilityAndRoles(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	u1 := newVerifiedUser(t, d, "admin_test1@sjtu.edu.cn", "用户甲", "Password123!@#", true)
	appCtx := newTestCtx(ctx, u1, "", false)
	_, _ = svc.AddContact(appCtx, AddContactInput{Type: ContactQQ, Value: "12345678"})

	// 1. 超管查看用户列表：能看到邮箱 (规则 39)
	superCtx := newTestCtx(ctx, nil, "", true)
	listRes, err := svc.ListUsers(superCtx, ListUsersInput{Page: 1, PageSize: 10})
	if err != nil || len(listRes.Users) == 0 {
		t.Fatalf("ListUsers: %v", err)
	}
	if listRes.Users[0].Email == "" {
		t.Fatal("超管应能看到邮箱")
	}

	// 非超管管理员查看用户列表：看不到邮箱 (规则 39)
	editorCtx := newTestCtx(ctx, nil, "", false, CapAdminEnter)
	editorList, err := svc.ListUsers(editorCtx, ListUsersInput{Page: 1, PageSize: 10})
	if err != nil || len(editorList.Users) == 0 {
		t.Fatalf("ListUsers: %v", err)
	}
	if editorList.Users[0].Email != "" {
		t.Fatal("非超管管理员不应看到邮箱")
	}

	// 2. 联系方式权限 (规则 40)
	// 赛事管理员（拥有 CapContactsView）：可见联系方式
	tournAdminCtx := newTestCtx(ctx, nil, "", false, CapContactsView)
	detail, err := svc.GetUserDetail(tournAdminCtx, UserDetailInput{ID: api.ID(u1.ID)})
	if err != nil {
		t.Fatalf("GetUserDetail: %v", err)
	}
	if len(detail.Contacts) == 0 {
		t.Fatal("拥有 CapContactsView 的赛事管理员应可见联系方式")
	}

	// 普通编辑：不可见联系方式
	detailEditor, err := svc.GetUserDetail(editorCtx, UserDetailInput{ID: api.ID(u1.ID)})
	if err != nil {
		t.Fatalf("GetUserDetail: %v", err)
	}
	if len(detailEditor.Contacts) != 0 {
		t.Fatal("无 contacts.view 的编辑不应看到联系方式")
	}

	// 3. 管理员更新角色 (规则 42)
	rolesRes, err := svc.UpdateUserRoles(superCtx, UpdateUserRolesInput{
		ID:    api.ID(u1.ID),
		Roles: []string{RoleTournamentAdmin, RoleScrimAdmin},
	})
	if err != nil || len(rolesRes.Roles) != 2 {
		t.Fatalf("UpdateUserRoles 失败: %+v, err=%v", rolesRes, err)
	}

	// 4. 管理员配置角色功能限制 (规则 11)
	restrRes, err := svc.SetFeatureRoleRestrictions(superCtx, SetFeatureRoleRestrictionsInput{
		Restrictions: []RoleRestrictionItem{
			{Role: RoleExternal, Feature: string(FeatureTournamentRegister)},
		},
	})
	if err != nil || restrRes.Result != "ok" {
		t.Fatalf("SetFeatureRoleRestrictions 失败: %+v, err=%v", restrRes, err)
	}

	restrictions, err := svc.GetFeatureRoleRestrictions(superCtx)
	if err != nil || len(restrictions.Restrictions) != 1 {
		t.Fatalf("GetFeatureRoleRestrictions 失败: %+v, err=%v", restrictions, err)
	}
}

// 契约 8.1: 从现行 Django SQLite 导入存量账号
func TestImportLegacyAccounts(t *testing.T) {
	newDB := newTestDB(t)
	ctx := context.Background()

	// 造一个模拟 Django 结构的临时 SQLite 旧库
	legacyPath := filepath.Join(t.TempDir(), "legacy.sqlite")
	legacyDB, err := sql.Open("sqlite", legacyPath)
	if err != nil {
		t.Fatal(err)
	}
	defer legacyDB.Close()

	initSQL := `
	CREATE TABLE accounts_user (
		id INTEGER PRIMARY KEY,
		password TEXT NOT NULL,
		nickname TEXT NOT NULL,
		is_sjtu INTEGER NOT NULL DEFAULT 0,
		agreed_terms_at TEXT NOT NULL,
		agreed_cross_border_at TEXT NOT NULL,
		date_joined TEXT NOT NULL,
		is_active INTEGER NOT NULL DEFAULT 1,
		is_superuser INTEGER NOT NULL DEFAULT 0,
		deactivation_note TEXT NOT NULL DEFAULT '',
		motto TEXT NOT NULL DEFAULT '',
		main_role TEXT NOT NULL DEFAULT '',
		flex_roles TEXT NOT NULL DEFAULT '',
		show_rank INTEGER NOT NULL DEFAULT 0,
		accepts_announcements INTEGER NOT NULL DEFAULT 1,
		calendar_version INTEGER NOT NULL DEFAULT 0,
		email TEXT NOT NULL
	);
	CREATE TABLE account_emailaddress (
		id INTEGER PRIMARY KEY,
		user_id INTEGER NOT NULL,
		email TEXT NOT NULL,
		verified INTEGER NOT NULL,
		"primary" INTEGER NOT NULL
	);
	CREATE TABLE accounts_gameaccount (
		id INTEGER PRIMARY KEY,
		user_id INTEGER NOT NULL,
		battletag TEXT NOT NULL,
		rank_tank INTEGER,
		rank_damage INTEGER,
		rank_support INTEGER,
		ranks_updated_at TEXT NOT NULL
	);
	CREATE TABLE accounts_contactmethod (
		id INTEGER PRIMARY KEY,
		user_id INTEGER NOT NULL,
		type TEXT NOT NULL,
		value TEXT NOT NULL
	);
	CREATE TABLE auth_group (
		id INTEGER PRIMARY KEY,
		name TEXT NOT NULL
	);
	CREATE TABLE accounts_user_groups (
		id INTEGER PRIMARY KEY,
		user_id INTEGER NOT NULL,
		group_id INTEGER NOT NULL
	);
	CREATE TABLE accounts_featuregrouprestriction (
		id INTEGER PRIMARY KEY,
		group_id INTEGER NOT NULL,
		feature TEXT NOT NULL
	);
	CREATE TABLE accounts_featureuserrule (
		id INTEGER PRIMARY KEY,
		user_id INTEGER NOT NULL,
		feature TEXT NOT NULL,
		allowed INTEGER NOT NULL
	);
	`
	if _, err := legacyDB.ExecContext(ctx, initSQL); err != nil {
		t.Fatal(err)
	}

	// 灌入模拟旧数据
	nowStr := "2026-09-18 10:00:00"
	_, err = legacyDB.ExecContext(ctx, `
		INSERT INTO accounts_user (id, password, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at, date_joined, is_active, is_superuser, email)
		VALUES (42, 'argon2$old...', '老玩家', 1, ?, ?, ?, 1, 0, 'legacy@sjtu.edu.cn');
		INSERT INTO account_emailaddress (id, user_id, email, verified, "primary")
		VALUES (1, 42, 'legacy@sjtu.edu.cn', 1, 1);
		INSERT INTO accounts_gameaccount (id, user_id, battletag, rank_tank, rank_damage, rank_support, ranks_updated_at)
		VALUES (101, 42, 'OldPlayer#1234', 25, 30, NULL, ?);
		INSERT INTO accounts_contactmethod (id, user_id, type, value)
		VALUES (201, 42, 'qq', '12345678');
		INSERT INTO auth_group (id, name) VALUES (1, '内容编辑');
		INSERT INTO accounts_user_groups (id, user_id, group_id) VALUES (1, 42, 1);
		INSERT INTO accounts_featuregrouprestriction (id, group_id, feature) VALUES (1, 1, 'team_create');
		INSERT INTO accounts_featureuserrule (id, user_id, feature, allowed) VALUES (1, 42, 'scrim_signup', 0);
	`, nowStr, nowStr, nowStr, nowStr)
	if err != nil {
		t.Fatal(err)
	}

	// 执行导入
	err = ImportLegacyAccounts(ctx, newDB, legacyDB)
	if err != nil {
		t.Fatalf("ImportLegacyAccounts 失败: %v", err)
	}

	// 验证编号和数据完整
	store := NewStore(newDB)
	u, err := store.GetByID(ctx, 42)
	if err != nil || u == nil || u.Nickname != "老玩家" || !u.EmailVerified() {
		t.Fatalf("导入用户校验失败: %+v, err=%v", u, err)
	}

	gas, err := store.GetGameAccountsByUserID(ctx, 42)
	if err != nil || len(gas) != 1 || gas[0].ID != 101 || gas[0].Battletag != "OldPlayer#1234" {
		t.Fatalf("导入游戏 ID 校验失败: %+v", gas)
	}

	contacts, err := store.GetContactsByUserID(ctx, 42)
	if err != nil || len(contacts) != 1 || contacts[0].ID != 201 || contacts[0].Value != "12345678" {
		t.Fatalf("导入联系方式校验失败: %+v", contacts)
	}

	roles, err := store.GetUserRoles(ctx, 42)
	if err != nil || len(roles) != 1 || roles[0] != RoleContentEditor {
		t.Fatalf("导入角色校验失败: %v", roles)
	}

	restrs, err := store.GetFeatureRoleRestrictions(ctx)
	if err != nil || !restrs[RoleContentEditor][FeatureTeamCreate] {
		t.Fatalf("导入角色限制校验失败: %+v", restrs)
	}

	rules, err := store.GetFeatureUserRules(ctx, 42)
	if err != nil || rules[FeatureScrimSignup] { // allowed=0 -> denied
		t.Fatalf("导入单人规则校验失败: %+v", rules)
	}
}
