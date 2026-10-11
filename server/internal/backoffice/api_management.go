package backoffice

import "github.com/Uniseem/sjtu-ow/server/internal/app"

func (m *Module) home(ctx *app.Ctx, in struct{}) (HomeOut, error) { return m.svc.home(ctx, in) }
func (m *Module) patchUser(ctx *app.Ctx, in PatchUserIn) (SaveOut, error) {
	return m.svc.patchUser(ctx, in)
}
func (m *Module) userRules(ctx *app.Ctx, in IDIn) (UserRulesOut, error) {
	return m.svc.userRules(ctx, in)
}
func (m *Module) addUserRule(ctx *app.Ctx, in AddUserRuleIn) (UserRulesOut, error) {
	return m.svc.addUserRule(ctx, in)
}
func (m *Module) deleteUserRule(ctx *app.Ctx, in RuleIDIn) (UserRulesOut, error) {
	return m.svc.deleteUserRule(ctx, in)
}
func (m *Module) roles(ctx *app.Ctx, in struct{}) (RolesOut, error) { return m.svc.roles(ctx, in) }
func (m *Module) addRestriction(ctx *app.Ctx, in AddRestrictionIn) (RolesOut, error) {
	return m.svc.addRestriction(ctx, in)
}
func (m *Module) deleteRestriction(ctx *app.Ctx, in RuleIDIn) (RolesOut, error) {
	return m.svc.deleteRestriction(ctx, in)
}
func (m *Module) registrations(ctx *app.Ctx, in RegistrationQuery) (RegistrationListOut, error) {
	return m.svc.registrations(ctx, in)
}
func (m *Module) registration(ctx *app.Ctx, in IDIn) (RegistrationDetailOut, error) {
	return m.svc.registration(ctx, in)
}
func (m *Module) exportRegistrations(ctx *app.Ctx, in RegistrationQuery) (CSVOut, error) {
	return m.svc.exportRegistrations(ctx, in)
}
func (m *Module) bulkApprove(ctx *app.Ctx, in BulkApproveIn) (BulkApproveOut, error) {
	return m.svc.bulkApprove(ctx, in)
}
func (m *Module) searchUsers(ctx *app.Ctx, in UserSearchIn) (UserSearchOut, error) {
	return m.svc.searchUsers(ctx, in)
}
