package accounts

import "strings"

// RoleOrder 是三个位置的固定顺序（现行站 accounts/roles.py 的 ROLE_ORDER）。
var RoleOrder = []string{"tank", "damage", "support"}

// RoleLabels 是位置代码对应的中文名。
var RoleLabels = map[string]string{"tank": "坦克", "damage": "输出", "support": "支援"}

// ParseRoles 从「support,tank」这样的逗号分隔串取出认得的位置，按坦克、输出、支援的
// 固定顺序，每个一次；不认得的丢掉。
func ParseRoles(value string) []string {
	wanted := map[string]struct{}{}
	for _, code := range strings.Split(value, ",") {
		wanted[strings.TrimSpace(code)] = struct{}{}
	}
	out := make([]string, 0, len(RoleOrder))
	for _, role := range RoleOrder {
		if _, ok := wanted[role]; ok {
			out = append(out, role)
		}
	}
	return out
}

// JoinRoles 把一组位置代码整理成存库的逗号分隔串（去重、定序、丢掉不认得的）。
func JoinRoles(codes []string) string {
	return strings.Join(ParseRoles(strings.Join(codes, ",")), ",")
}

// PublicPositions 是一个人公开的位置：主位置在前，补位置接在后面，每个一次。
func PublicPositions(main, flex string) []string {
	out := []string{}
	if _, ok := RoleLabels[main]; !ok {
		main = ""
	}
	if main != "" {
		out = append(out, main)
	}
	for _, r := range ParseRoles(flex) {
		if r != main {
			out = append(out, r)
		}
	}
	return out
}
