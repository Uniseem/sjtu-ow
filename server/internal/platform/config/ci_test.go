package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// 229：每次推送和测试机整组都只测新栈。
func TestCIOnlyRunsTheNewStack(t *testing.T) {
	root := repoRoot(t)
	ci := readText(t, filepath.Join(root, ".github", "workflows", "ci.yml"))
	script := readText(t, filepath.Join(root, "scripts", "check.sh"))
	remote := readText(t, filepath.Join(root, "scripts", "remote-check.sh"))
	for _, gone := range []string{"uv run pytest", "ruff check", "manage.py", "docker build", "CHECK_LEGACY", "CHECK_DOCKER"} {
		for _, name := range []string{"CI", "check.sh", "remote-check.sh"} {
			body := map[string]string{"CI": ci, "check.sh": script, "remote-check.sh": remote}[name]
			if strings.Contains(body, gone) {
				t.Fatalf("%s 不该再跑现行站：%s", name, gone)
			}
		}
	}
	for _, need := range []string{"gofmt -l", "go vet ./...", "staticcheck ./...", "govulncheck ./...", "go test ./..."} {
		if !strings.Contains(ci, need) || !strings.Contains(script, need) {
			t.Fatalf("新栈检查缺 %s", need)
		}
	}
	if !strings.Contains(remote, "sh scripts/check.sh") {
		t.Fatal("测试机整组应直接跑 check.sh")
	}
}

func repoRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, ".github", "workflows", "ci.yml")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			t.Fatal("找不到仓库根")
		}
		dir = parent
	}
}

func readText(t *testing.T, path string) string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}
