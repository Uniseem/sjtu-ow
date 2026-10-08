// Package config 读环境变量：必填项缺了就拒绝启动，并指出缺哪个
// （12 号文档 5.16「缺必填项拒绝启动；镜像里不带任何默认密钥」）。
package config

import (
	"fmt"
	"net"
	"net/url"
	"os"
	"strings"
)

// Config 是进程需要的全部环境配置。字段对应 12 号文档 5.16 的表；
// 这轮用到的字段会被消费，其余（APIInternalURL 等）先存着等后续里程碑。
type Config struct {
	SiteURL             string
	SigningKey          string // = 现在的 DJANGO_SECRET_KEY（djsign、会话等签名用）
	FieldEncryptionKey  string // 全站设置里密文的加密钥匙，沿用
	BackupEncryptionKey string // 可空：不设就不传异地备份
	DataDir             string
	MediaDir            string
	AssetsDir           string
	TrustedProxies      []*net.IPNet
	EmailAllowlist      []string
	TestEnvironment     bool
	Prod                bool // SJTUOW_ENV=prod；默认 dev（开发和测试）
	APIInternalURL      string
}

// Load 从 getenv（生产是 os.Getenv，测试传自己的函数）读配置。
func Load(getenv func(string) string) (*Config, error) {
	c := &Config{}

	var missing []string
	need := func(name string) string {
		v := strings.TrimSpace(getenv(name))
		if v == "" {
			missing = append(missing, name)
		}
		return v
	}

	siteURL := need("SITE_URL")
	c.SigningKey = need("SIGNING_KEY")
	c.FieldEncryptionKey = need("FIELD_ENCRYPTION_KEY")
	if len(missing) > 0 {
		return nil, fmt.Errorf("缺必填环境变量：%s", strings.Join(missing, "、"))
	}

	u, err := url.Parse(siteURL)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		return nil, fmt.Errorf("SITE_URL 得是 http(s):// 开头的完整地址，现在是 %q", siteURL)
	}
	c.SiteURL = siteURL

	c.Prod = strings.EqualFold(strings.TrimSpace(getenv("SJTUOW_ENV")), "prod")
	if c.Prod {
		for name, key := range map[string]string{"SIGNING_KEY": c.SigningKey, "FIELD_ENCRYPTION_KEY": c.FieldEncryptionKey} {
			if len(key) < 32 {
				return nil, fmt.Errorf("生产环境（SJTUOW_ENV=prod）的 %s 太短（%d 字符），至少 32", name, len(key))
			}
		}
	}

	c.BackupEncryptionKey = strings.TrimSpace(getenv("BACKUP_ENCRYPTION_KEY"))
	c.DataDir = defaultStr(getenv("DATA_DIR"), "data")
	c.MediaDir = defaultStr(getenv("MEDIA_DIR"), "media")
	c.AssetsDir = defaultStr(getenv("ASSETS_DIR"), "assets")
	c.APIInternalURL = strings.TrimSpace(getenv("API_INTERNAL_URL"))

	for _, cidr := range splitList(getenv("TRUSTED_PROXIES")) {
		_, net_, err := net.ParseCIDR(cidr)
		if err != nil {
			return nil, fmt.Errorf("TRUSTED_PROXIES 里的 %q 不是合法网段", cidr)
		}
		c.TrustedProxies = append(c.TrustedProxies, net_)
	}
	c.EmailAllowlist = splitList(getenv("EMAIL_ALLOWLIST"))
	c.TestEnvironment = isTrue(getenv("TEST_ENVIRONMENT"))

	return c, nil
}

// FromEnv 从进程环境读配置，main 用。
func FromEnv() (*Config, error) { return Load(os.Getenv) }

func defaultStr(v, def string) string {
	if strings.TrimSpace(v) == "" {
		return def
	}
	return strings.TrimSpace(v)
}

func splitList(v string) []string {
	var out []string
	for _, item := range strings.Split(strings.TrimSpace(v), ",") {
		if item = strings.TrimSpace(item); item != "" {
			out = append(out, item)
		}
	}
	return out
}

func isTrue(v string) bool {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}
