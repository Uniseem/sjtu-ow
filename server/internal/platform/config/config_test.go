package config

import (
	"net"
	"strings"
	"testing"
)

func parseIPMust(t *testing.T, s string) net.IP {
	t.Helper()
	ip := net.ParseIP(s)
	if ip == nil {
		t.Fatalf("测试自己写的 IP 不合法：%s", s)
	}
	return ip
}

func validEnv() map[string]string {
	return map[string]string{
		"SITE_URL":             "https://sjtu.ow-shanghaiuniversity.com",
		"SIGNING_KEY":          "test-signing-key-at-least-some-length-0123456789",
		"FIELD_ENCRYPTION_KEY": "test-field-key-at-least-some-length-0123456789",
	}
}

func getenv(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func TestLoadRefusesWhenRequiredMissing(t *testing.T) {
	for _, name := range []string{"SITE_URL", "SIGNING_KEY", "FIELD_ENCRYPTION_KEY"} {
		env := validEnv()
		delete(env, name)
		_, err := Load(getenv(env))
		if err == nil {
			t.Fatalf("缺 %s 应拒绝启动", name)
		}
		if !strings.Contains(err.Error(), name) {
			t.Fatalf("报错应指出缺哪个，得到：%v", err)
		}
	}
}

func TestLoadAllMissingNamesAtOnce(t *testing.T) {
	_, err := Load(getenv(map[string]string{}))
	if err == nil || !strings.Contains(err.Error(), "SITE_URL") || !strings.Contains(err.Error(), "SIGNING_KEY") {
		t.Fatalf("应一次报出所有缺项，得到：%v", err)
	}
}

func TestLoadParsesAndDefaults(t *testing.T) {
	env := validEnv()
	env["TRUSTED_PROXIES"] = "10.0.0.0/8, fd00::/8"
	env["EMAIL_ALLOWLIST"] = "a@example.com, b@example.com"
	env["TEST_ENVIRONMENT"] = "1"
	c, err := Load(getenv(env))
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if c.DataDir != "data" || c.MediaDir != "media" || c.AssetsDir != "assets" {
		t.Fatalf("目录默认值不对：%s %s %s", c.DataDir, c.MediaDir, c.AssetsDir)
	}
	if c.Prod {
		t.Fatal("默认应是 dev")
	}
	if !c.TestEnvironment {
		t.Fatal("TEST_ENVIRONMENT=1 没认出来")
	}
	if len(c.TrustedProxies) != 2 || len(c.EmailAllowlist) != 2 {
		t.Fatalf("列表解析不对：proxies=%v allowlist=%v", c.TrustedProxies, c.EmailAllowlist)
	}
	if !c.TrustedProxies[0].Contains(parseIPMust(t, "10.1.2.3")) {
		t.Fatal("10.0.0.0/8 应包含 10.1.2.3")
	}
}

func TestLoadRejectsBadSiteURL(t *testing.T) {
	for _, bad := range []string{"不是地址", "ftp://example.com", "example.com"} {
		env := validEnv()
		env["SITE_URL"] = bad
		if _, err := Load(getenv(env)); err == nil {
			t.Fatalf("SITE_URL=%q 应被拒", bad)
		}
	}
}

func TestLoadRejectsBadCIDR(t *testing.T) {
	env := validEnv()
	env["TRUSTED_PROXIES"] = "10.0.0.0/8; nonsense"
	if _, err := Load(getenv(env)); err == nil {
		t.Fatal("坏网段应被拒")
	}
}

func TestLoadProdWantsLongKeys(t *testing.T) {
	env := validEnv()
	env["SJTUOW_ENV"] = "prod"
	env["SIGNING_KEY"] = "short"
	if _, err := Load(getenv(env)); err == nil {
		t.Fatal("生产环境短 SIGNING_KEY 应被拒")
	}
	// 同样的短钥匙在 dev 下没有意见
	if _, err := Load(getenv(validEnv())); err != nil {
		t.Fatalf("dev 下不应检查钥匙长度：%v", err)
	}
}

func TestLoadTrimsSpaces(t *testing.T) {
	env := validEnv()
	env["SIGNING_KEY"] = "  " + env["SIGNING_KEY"] + "  "
	c, err := Load(getenv(env))
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if c.SigningKey != validEnv()["SIGNING_KEY"] {
		t.Fatal("取值应去掉首尾空白")
	}
}
