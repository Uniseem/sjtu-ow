package accounts

import (
	"fmt"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// 4 个存储角色（12 号文档 5.8）。
const (
	RoleContentEditor   = "content_editor"
	RoleCertifiedAuthor = "certified_author"
	RoleTournamentAdmin = "tournament_admin"
	RoleScrimAdmin      = "scrim_admin"
)

// 3 个派生角色（不存库，实时计算，12 号文档 5.8）。
const (
	RoleSJTU        = "sjtu_user"
	RoleExternal    = "external_user"
	RoleContributor = "contributor"
)

// 功能标识（设计 4.3.1，规则 11）。
const (
	FeatureTeamCreate         app.Feature = "team_create"
	FeatureTeamApply          app.Feature = "team_apply"
	FeatureTournamentRegister app.Feature = "tournament_register"
	FeatureScrimSignup        app.Feature = "scrim_signup"
	FeatureArticleSubmit      app.Feature = "article_submit"
	FeatureArticleComment     app.Feature = "article_comment"
	FeatureAvatarUpload       app.Feature = "avatar_upload"
)

// 后台能力（12 号文档 5.8、docs/admin.md 4）。
const (
	CapAdminEnter         app.Cap = "admin.enter"
	CapArticlesPublishOwn app.Cap = "articles.publish_own"
	CapArticlesEditAny    app.Cap = "articles.edit_any"
	CapArticlesEditAuthor app.Cap = "articles.edit_author"
	CapArticleCategories  app.Cap = "article_categories.manage"
	CapSitePages          app.Cap = "site_pages.manage"
	CapImagesContribute   app.Cap = "images.contribute"
	CapImagesManage       app.Cap = "images.manage"
	CapTournamentsManage  app.Cap = "tournaments.manage"
	CapScrimsManage       app.Cap = "scrims.manage"
	CapContactsView       app.Cap = "contacts.view"
	CapCommentsModerate   app.Cap = "comments.moderate"
	CapModerationReview   app.Cap = "moderation.review"
	CapMemberGroups       app.Cap = "member_groups.manage"
	CapActivityView       app.Cap = "activity.view"
)

// FeatureDeniedMessage 被拒时的固定文案（规则 12，绝不透露具体原因）。
const FeatureDeniedMessage = "你暂时无法使用此功能，如有疑问请联系管理员"

var allFeatures = map[app.Feature]struct{}{
	FeatureTeamCreate:         {},
	FeatureTeamApply:          {},
	FeatureTournamentRegister: {},
	FeatureScrimSignup:        {},
	FeatureArticleSubmit:      {},
	FeatureArticleComment:     {},
	FeatureAvatarUpload:       {},
}

// IsValidFeature 检查功能标识是否合法。
func IsValidFeature(f app.Feature) bool {
	_, ok := allFeatures[f]
	return ok
}

// AllStoredRoles 全部存库的管理角色。
var AllStoredRoles = []string{
	RoleContentEditor,
	RoleCertifiedAuthor,
	RoleTournamentAdmin,
	RoleScrimAdmin,
}

// roleCaps 角色 → 能力对照表（12 号文档 5.8，照设计第 4 章的权限矩阵逐格搬）。
var roleCaps = map[string][]app.Cap{
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
}

// CapsForRole 返回某个角色拥有的能力。
func CapsForRole(role string) []app.Cap {
	caps, ok := roleCaps[role]
	if !ok {
		return nil
	}
	out := make([]app.Cap, len(caps))
	copy(out, caps)
	return out
}

// DerivedRoles 计算派生角色（规则 9、13）。
// - 交大/校外用户看 isSJTU。
// - 投稿者资格 = 账号启用 + 邮箱已验证 + can_use(article_submit)。
func DerivedRoles(isSJTU bool, isActive bool, emailVerified bool, canSubmitArticle bool) []string {
	var roles []string
	if isSJTU {
		roles = append(roles, RoleSJTU)
	} else {
		roles = append(roles, RoleExternal)
	}
	if isActive && emailVerified && canSubmitArticle {
		roles = append(roles, RoleContributor)
	}
	return roles
}

// CanUse 检查用户是否可以使用某项功能（规则 11）。
// 判定顺序：
// 1. 未登录/停用 → 一律拒绝 (false)
// 2. 未知 feature → 返回错误
// 3. 超管 → 一律允许 (true)
// 4. 单用户规则（feature_user_rules）优先：明确允许/禁止
// 5. 所在角色（含派生角色）任一有限制 → 拒绝
// 6. 默认允许 (true)
func CanUse(
	user *User,
	feature app.Feature,
	userRules map[app.Feature]bool,
	roleRestrictions map[string]map[app.Feature]bool,
	storedRoles []string,
) (bool, error) {
	if user == nil || !user.IsActive {
		return false, nil
	}
	if !IsValidFeature(feature) {
		return false, fmt.Errorf("unknown feature: %s", feature)
	}
	if user.IsSuperuser {
		return true, nil
	}

	// 1. 单用户规则优先
	if userRules != nil {
		if allowed, ok := userRules[feature]; ok {
			return allowed, nil
		}
	}

	// 2. 检查所在角色的限制（含派生角色，计算时假定 canSubmitArticle 为 true 避免递归）
	derived := DerivedRoles(user.IsSJTU, user.IsActive, user.EmailVerified(), true)
	allRoles := append([]string(nil), storedRoles...)
	allRoles = append(allRoles, derived...)

	for _, r := range allRoles {
		if restr, ok := roleRestrictions[r]; ok {
			if restricted := restr[feature]; restricted {
				return false, nil
			}
		}
	}

	// 3. 默认允许
	return true, nil
}

// RunsAdmin 判断用户是否有后台管理权限（用于前台菜单展示，viewer.user.admin）。
// 能进后台 = 超管 || 拥有 CapAdminEnter 能力。
func RunsAdmin(user *User, viewer *app.Viewer) bool {
	if user == nil || !user.IsActive || viewer == nil || viewer.Disabled {
		return false
	}
	if user.IsSuperuser || viewer.Superuser {
		return true
	}
	return viewer.HasCap(CapAdminEnter)
}
