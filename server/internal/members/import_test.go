package members

import (
	"context"
	"database/sql"
	"fmt"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

// 导入器：分组编号沿用，Orderable 的 sort_order 可以为空，反复跑结果一样
func TestImportLegacyGroups(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("甲"), e.user("乙")
	legacy, err := sql.Open("sqlite", "file:"+filepath.Join(t.TempDir(), "legacy.sqlite3"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, s := range []string{
		`CREATE TABLE members_membergroup (id INTEGER, name TEXT, description TEXT, is_visible INTEGER, sort_order INTEGER)`,
		`INSERT INTO members_membergroup VALUES (4, '社团干部', '简介', 1, 2), (9, '', '', 0, 0)`,
		`CREATE TABLE members_membergroupmembership (id INTEGER, group_id INTEGER, user_id INTEGER, title TEXT, sort_order INTEGER)`,
		`INSERT INTO members_membergroupmembership VALUES (1, 4, ` + itoa(a) + `, '社长', 0), (2, 4, ` + itoa(b) + `, '', NULL)`,
	} {
		if _, err := legacy.Exec(s); err != nil {
			t.Fatalf("%s: %v", s, err)
		}
	}
	for i := 0; i < 2; i++ {
		if err := ImportLegacyGroups(context.Background(), e.d, legacy); err != nil {
			t.Fatalf("第 %d 次导入：%v", i+1, err)
		}
	}
	if e.count(`SELECT COUNT(*) FROM member_groups`) != 2 || e.count(`SELECT COUNT(*) FROM member_group_memberships`) != 2 {
		t.Fatal("两个分组、两条成员关系")
	}
	res, _ := e.svc.Showcase(context.Background(), ShowcaseInput{}, t0)
	if len(res.Sections) != 1 || res.Sections[0].Name != "社团干部" || len(res.Sections[0].Entries) != 2 {
		t.Fatalf("导入后成员墙：%+v", res.Sections)
	}
	// 空的 sort_order 当 0，同序按昵称排：乙在前（没有职务），甲在后（社长）
	es := res.Sections[0].Entries
	if es[0].Member.UserID != b || len(es[0].Titles) != 0 || len(es[1].Titles) != 1 || es[1].Titles[0] != "社长" {
		t.Fatalf("组内顺序和职务：%+v", es)
	}
}

func itoa(n int64) string { return fmt.Sprintf("%d", n) }
