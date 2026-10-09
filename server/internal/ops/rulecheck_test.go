package ops

import (
	"os"
	"path/filepath"
	"testing"
)

func TestParseRules(t *testing.T) {
	tmpFile := filepath.Join(t.TempDir(), "rules.md")
	content := `# 05 业务规则
1. 注册必填：邮箱、密码
2. 邮箱验证为强制
15. 服务端背书直接验证
237. 最后一项规则
`
	if err := os.WriteFile(tmpFile, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}

	rules, err := ParseRules(tmpFile)
	if err != nil {
		t.Fatalf("ParseRules 失败: %v", err)
	}
	if len(rules) != 4 {
		t.Fatalf("预期 4 条规则，实际解析出 %d 条", len(rules))
	}
	if rules[0].ID != "R001" || rules[2].ID != "R015" || rules[3].ID != "R237" {
		t.Errorf("规则编号解析有误: %+v", rules)
	}
}

func TestRuleCheck(t *testing.T) {
	dir := t.TempDir()
	docFile := filepath.Join(dir, "rules.md")
	rulesDoc := `1. 第一条
2. 第二条
3. 第三条
4. 第四条
`
	if err := os.WriteFile(docFile, []byte(rulesDoc), 0644); err != nil {
		t.Fatal(err)
	}

	testFile := filepath.Join(dir, "sample_test.go")
	testSrc := `package sample
// 契约 R001：测试第一条
// 契约 R002–R003：批量覆盖
func TestSomething() {}
`
	if err := os.WriteFile(testFile, []byte(testSrc), 0644); err != nil {
		t.Fatal(err)
	}

	res, err := RuleCheck(docFile, dir)
	if err != nil {
		t.Fatalf("RuleCheck 失败: %v", err)
	}
	if res.TotalRules != 4 {
		t.Errorf("预期总数 4，实际 %d", res.TotalRules)
	}
	if res.CoveredRules != 3 {
		t.Errorf("预期覆盖 3，实际 %d", res.CoveredRules)
	}
	if len(res.Uncovered) != 1 || res.Uncovered[0].ID != "R004" {
		t.Errorf("未覆盖规则识别错误: %+v", res.Uncovered)
	}

	report := res.FormatReport()
	if report == "" {
		t.Errorf("生成的报告为空")
	}
}
