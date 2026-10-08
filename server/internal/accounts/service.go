package accounts

import (
	"context"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Service 是账号域的业务服务。
type Service struct {
	d     *db.DB
	store *Store
	clock clock.Clock
}

// NewService 创建账号服务。
func NewService(d *db.DB, c clock.Clock) *Service {
	if c == nil {
		c = clock.System{}
	}
	return &Service{
		d:     d,
		store: NewStore(d),
		clock: c,
	}
}

// Store 返回底层的 Store。
func (s *Service) Store() *Store {
	return s.store
}

// BuildViewer 根据用户 ID 从数据库组装 *app.Viewer（12 号文档 5.2、5.8）。
// 未登录或账号不存在返回 nil。停用账号返回 Disabled: true 的 Viewer。
func (s *Service) BuildViewer(ctx context.Context, userID int64) (*app.Viewer, error) {
	if userID <= 0 {
		return nil, nil
	}
	u, err := s.store.GetByID(ctx, userID)
	if err != nil {
		return nil, err
	}
	if u == nil {
		return nil, nil
	}
	if !u.IsActive {
		return &app.Viewer{
			ID:       u.ID,
			Disabled: true,
		}, nil
	}

	storedRoles, err := s.store.GetUserRoles(ctx, u.ID)
	if err != nil {
		return nil, err
	}
	userRules, err := s.store.GetFeatureUserRules(ctx, u.ID)
	if err != nil {
		return nil, err
	}
	roleRestrs, err := s.store.GetFeatureRoleRestrictions(ctx)
	if err != nil {
		return nil, err
	}

	// 判定投稿者资格所需的前提
	canSubmit, _ := CanUse(u, FeatureArticleSubmit, userRules, roleRestrs, storedRoles)
	derived := DerivedRoles(u.IsSJTU, u.IsActive, u.EmailVerified(), canSubmit)

	// 汇总所有角色拥有的后台能力（Caps）
	caps := make(map[app.Cap]struct{})
	allRoles := append([]string(nil), storedRoles...)
	allRoles = append(allRoles, derived...)
	for _, r := range allRoles {
		for _, c := range CapsForRole(r) {
			caps[c] = struct{}{}
		}
	}

	// 预先算好单人受限的所有 Feature
	deniedMap := make(map[app.Feature]struct{})
	for feat := range allFeatures {
		allowed, _ := CanUse(u, feat, userRules, roleRestrs, storedRoles)
		if !allowed {
			deniedMap[feat] = struct{}{}
		}
	}

	return &app.Viewer{
		ID:            u.ID,
		Disabled:      false,
		EmailVerified: u.EmailVerified(),
		Superuser:     u.IsSuperuser,
		Caps:          caps,
		FeatureDenied: deniedMap,
	}, nil
}
