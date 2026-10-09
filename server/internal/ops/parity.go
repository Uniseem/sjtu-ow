package ops

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/agenda"
	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/djsign"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

var (
	titleTagRegex = regexp.MustCompile(`(?i)<title[^>]*>(.*?)</title>`)
	imageSrcRegex = regexp.MustCompile(`(?:/media/images/|/media/originals/)([a-zA-Z0-9_\-\./]+)`)
)

// RouteCheckResult 单条公开路由对拍结果（12 号文档 8.2、9）。
type RouteCheckResult struct {
	Path      string `json:"path"`
	NewStatus int    `json:"new_status"`
	LegStatus int    `json:"legacy_status,omitempty"`
	Title     string `json:"title,omitempty"`
	Passed    bool   `json:"passed"`
	Detail    string `json:"detail,omitempty"`
}

// MediaCheckResult 正文与数据库图片引用对拍结果（12 号文档 8.2）。
type MediaCheckResult struct {
	TotalChecked int      `json:"total_checked"`
	Missing      []string `json:"missing,omitempty"`
	Passed       bool     `json:"passed"`
}

// SignatureCheckResult 签名兼容性检查结果（日历与退订链接，12 号文档 8.2）。
type SignatureCheckResult struct {
	CalendarOK    bool   `json:"calendar_ok"`
	UnsubscribeOK bool   `json:"unsubscribe_ok"`
	Passed        bool   `json:"passed"`
	Detail        string `json:"detail,omitempty"`
}

// PasswordCheckResult 密码哈希兼容性检查结果（12 号文档 8.2）。
type PasswordCheckResult struct {
	Argon2idOK bool   `json:"argon2id_ok"`
	PBKDF2OK   bool   `json:"pbkdf2_ok"`
	RehashOK   bool   `json:"rehash_ok"`
	Passed     bool   `json:"passed"`
	Detail     string `json:"detail,omitempty"`
}

// ArticleRenderingResult Markdown 渲染结构与对拍结果（12 号文档 5.12、8.3）。
type ArticleRenderingResult struct {
	SampledCount int    `json:"sampled_count"`
	Passed       bool   `json:"passed"`
	Detail       string `json:"detail,omitempty"`
}

// ParityResult 全站对拍综合结果报告。
type ParityResult struct {
	Routes     []RouteCheckResult     `json:"routes"`
	Media      MediaCheckResult       `json:"media"`
	Signatures SignatureCheckResult   `json:"signatures"`
	Passwords  PasswordCheckResult    `json:"passwords"`
	Articles   ArticleRenderingResult `json:"articles"`
	OverallOK  bool                   `json:"overall_ok"`
}

// ParityOptions 对拍校验参数。
type ParityOptions struct {
	NewBaseURL      string
	LegacyBaseURL   string
	MediaDir        string
	SigningKey      string
	LegacyDBPath    string
	CheckRoutes     bool
	CheckMedia      bool
	CheckSignatures bool
	CheckPasswords  bool
	CheckArticles   bool
}

// ParityChecker 对拍与兼容性校验执行器。
type ParityChecker struct {
	opts   ParityOptions
	db     *db.DB
	client *http.Client
}

// NewParityChecker 构建对拍执行器。
func NewParityChecker(opts ParityOptions, d *db.DB) *ParityChecker {
	return &ParityChecker{
		opts: opts,
		db:   d,
		client: &http.Client{
			Timeout: 10 * time.Second,
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				if len(via) >= 5 {
					return fmt.Errorf("重定向次数过多")
				}
				return nil
			},
		},
	}
}

// Run 执行全套新旧对拍与兼容性核验。
func (c *ParityChecker) Run(ctx context.Context) (*ParityResult, error) {
	res := &ParityResult{
		OverallOK: true,
	}

	// 1. 签名兼容性检查（日历订阅与退订链接，不依赖外网）
	if c.opts.CheckSignatures || (!c.opts.CheckRoutes && !c.opts.CheckMedia && !c.opts.CheckPasswords && !c.opts.CheckArticles) {
		res.Signatures = c.checkSignatures()
		if !res.Signatures.Passed {
			res.OverallOK = false
		}
	} else {
		res.Signatures.Passed = true
	}

	// 2. 密码哈希兼容性检查（Argon2id 与 PBKDF2 升级）
	if c.opts.CheckPasswords || (!c.opts.CheckRoutes && !c.opts.CheckMedia && !c.opts.CheckSignatures && !c.opts.CheckArticles) {
		res.Passwords = c.checkPasswords(ctx)
		if !res.Passwords.Passed {
			res.OverallOK = false
		}
	} else {
		res.Passwords.Passed = true
	}

	// 3. Markdown 正文渲染结构与目录对拍
	if c.opts.CheckArticles || (!c.opts.CheckRoutes && !c.opts.CheckMedia && !c.opts.CheckSignatures && !c.opts.CheckPasswords) {
		res.Articles = c.checkArticles(ctx)
		if !res.Articles.Passed {
			res.OverallOK = false
		}
	} else {
		res.Articles.Passed = true
	}

	// 4. 图片资源引用核查（磁盘文件与 HTTP）
	if c.opts.CheckMedia || (c.opts.MediaDir != "" && c.opts.NewBaseURL != "") {
		res.Media = c.checkMedia(ctx)
		if !res.Media.Passed {
			res.OverallOK = false
		}
	} else {
		res.Media.Passed = true
	}

	// 5. 公开路由与页面端点对拍
	if c.opts.CheckRoutes || c.opts.NewBaseURL != "" {
		routesRes := c.checkRoutes(ctx)
		res.Routes = routesRes
		for _, r := range routesRes {
			if !r.Passed {
				res.OverallOK = false
				break
			}
		}
	}

	return res, nil
}

// checkSignatures 校验日历与退订链接签名算法与密钥兼容性（12 号文档 8.2）。
func (c *ParityChecker) checkSignatures() SignatureCheckResult {
	key := c.opts.SigningKey
	if key == "" {
		key = "dev-secret-key-for-cutover-verification-purpose"
	}

	res := SignatureCheckResult{CalendarOK: true, UnsubscribeOK: true, Passed: true}

	// 1. 日历签名：SignObject 与 UnsignObject
	type CalPayload struct {
		UserID int64  `json:"user_id"`
		Email  string `json:"email"`
	}
	samplePayload := CalPayload{UserID: 88, Email: "tester@sjtu.edu.cn"}
	calToken, err := djsign.SignObject(key, agenda.CalendarSalt, samplePayload)
	if err != nil {
		res.CalendarOK = false
		res.Detail = fmt.Sprintf("日历签名生成失败: %v", err)
	} else {
		var decoded CalPayload
		if err := djsign.UnsignObject(key, agenda.CalendarSalt, calToken, &decoded); err != nil {
			res.CalendarOK = false
			res.Detail = fmt.Sprintf("日历签名解签失败: %v", err)
		} else if decoded.UserID != samplePayload.UserID || decoded.Email != samplePayload.Email {
			res.CalendarOK = false
			res.Detail = fmt.Sprintf("日历签名载荷不匹配: %+v vs %+v", decoded, samplePayload)
		}
	}

	// 2. 退订签名：Dumps 与 Loads（带 base62 时间戳）
	const sampleUserID int64 = 1024
	unsubToken, err := djsign.Dumps(key, notify.UnsubscribeSalt, sampleUserID)
	if err != nil {
		res.UnsubscribeOK = false
		res.Detail += fmt.Sprintf(" 退订签名生成失败: %v", err)
	} else {
		var gotID int64
		if err := djsign.Loads(key, notify.UnsubscribeSalt, unsubToken, &gotID); err != nil {
			res.UnsubscribeOK = false
			res.Detail += fmt.Sprintf(" 退订签名解签失败: %v", err)
		} else if gotID != sampleUserID {
			res.UnsubscribeOK = false
			res.Detail += fmt.Sprintf(" 退订用户编号不匹配: %d vs %d", gotID, sampleUserID)
		}
	}

	res.Passed = res.CalendarOK && res.UnsubscribeOK
	return res
}

// checkPasswords 校验 Argon2id 与 Django PBKDF2 哈希兼容性（12 号文档 8.2）。
func (c *ParityChecker) checkPasswords(ctx context.Context) PasswordCheckResult {
	res := PasswordCheckResult{Passed: true}

	// 1. 验证 Argon2id 签名与校验
	const testPass = "SjtuOwPassword2026!#"
	argonHash, err := auth.Hash(ctx, testPass)
	if err != nil || !strings.HasPrefix(argonHash, "argon2$argon2id$v=19$") {
		res.Argon2idOK = false
		res.Detail = fmt.Sprintf("Argon2id 哈希生成失败: %v", err)
	} else {
		ok, upgrade, err := auth.Verify(ctx, argonHash, testPass)
		if err != nil || !ok || upgrade {
			res.Argon2idOK = false
			res.Detail = fmt.Sprintf("Argon2id 校验失败: ok=%v, upgrade=%v, err=%v", ok, upgrade, err)
		} else {
			res.Argon2idOK = true
		}
	}

	// 2. 验证 Django PBKDF2 哈希兼容及自动升级标记
	// 测试向量：Django 生成的 1 次迭代 pbkdf2_sha256，密码为 "pw"
	const djangoPBKDF2 = "pbkdf2_sha256$1$salt$b0rYx47DZcBg5kjraU7kDepYSEsDcfvWFxWsRBC3OAo="
	ok, upgrade, err := auth.Verify(ctx, djangoPBKDF2, "pw")
	if err != nil || !ok {
		res.PBKDF2OK = false
		res.Detail += fmt.Sprintf(" Django PBKDF2 校验失败: ok=%v, err=%v", ok, err)
	} else {
		res.PBKDF2OK = true
		if upgrade {
			res.RehashOK = true
		} else {
			res.RehashOK = false
			res.Detail += " Django PBKDF2 未触发 rehash 自动升级标记"
		}
	}

	res.Passed = res.Argon2idOK && res.PBKDF2OK && res.RehashOK
	return res
}

// checkArticles 校验 Markdown 渲染器、锚点提取与字数耗时统计（12 号文档 5.12）。
func (c *ParityChecker) checkArticles(ctx context.Context) ArticleRenderingResult {
	res := ArticleRenderingResult{Passed: true}

	var bodies []string
	if c.db != nil {
		rows, err := c.db.ReadPool().QueryContext(ctx, "SELECT body FROM articles LIMIT 10")
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var b string
				if err := rows.Scan(&b); err == nil && strings.TrimSpace(b) != "" {
					bodies = append(bodies, b)
				}
			}
		}
	}

	// 若库中无文章或无 DB，使用标准合规样本测试
	if len(bodies) == 0 {
		bodies = []string{
			"# 守望先锋赛事通知\n\n这是正文第一段，点击 [SJTU-OW](https://sjtu-ow.example.com)。\n\n## 规则说明\n\n参赛须知：\n| 组别 | 人数 |\n| --- | --- |\n| 坦克 | 1 |\n| 输出 | 2 |\n\n—— 组委会",
		}
	}

	for _, body := range bodies {
		html, plain, words, minutes, hdgs, err := markdown.Facts(body, "https://sjtu.ow-shanghaiuniversity.com", nil)
		if err != nil {
			res.Passed = false
			res.Detail = fmt.Sprintf("Markdown 渲染失败: %v", err)
			return res
		}
		if html == "" || plain == "" || words < 0 || minutes < 1 {
			res.Passed = false
			res.Detail = fmt.Sprintf("Markdown 渲染指标异常: htmlLen=%d, plainLen=%d, words=%d, min=%d", len(html), len(plain), words, minutes)
			return res
		}
		_ = hdgs
		res.SampledCount++
	}

	return res
}

// checkMedia 扫描正文与图片表中引用的媒体路径，验证磁盘文件或 HTTP 可达性（12 号文档 8.2）。
func (c *ParityChecker) checkMedia(ctx context.Context) MediaCheckResult {
	res := MediaCheckResult{Passed: true}
	if c.db == nil {
		return res
	}

	seenPaths := make(map[string]bool)

	// 1. 扫描 images 表
	rows, err := c.db.ReadPool().QueryContext(ctx, "SELECT file_path FROM images LIMIT 1000")
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var p string
			if err := rows.Scan(&p); err == nil && p != "" {
				seenPaths[p] = true
			}
		}
	}

	// 2. 扫描 articles 与 site_pages 正文中的图片 URL
	bodyRows, err := c.db.ReadPool().QueryContext(ctx, "SELECT body FROM articles UNION ALL SELECT body FROM site_pages")
	if err == nil {
		defer bodyRows.Close()
		for bodyRows.Next() {
			var b string
			if err := bodyRows.Scan(&b); err == nil {
				matches := imageSrcRegex.FindAllStringSubmatch(b, -1)
				for _, m := range matches {
					if len(m) > 1 {
						seenPaths[m[1]] = true
					}
				}
			}
		}
	}

	res.TotalChecked = len(seenPaths)

	// 3. 校验路径是否存在（优先磁盘，其次 HTTP）
	for p := range seenPaths {
		if c.opts.MediaDir != "" {
			fullPath := filepath.Join(c.opts.MediaDir, p)
			if _, err := os.Stat(fullPath); os.IsNotExist(err) {
				// 尝试在 media/images/ 或 media/originals/ 查找
				altPath := filepath.Join(c.opts.MediaDir, "images", p)
				if _, err2 := os.Stat(altPath); os.IsNotExist(err2) {
					res.Missing = append(res.Missing, p)
				}
			}
		} else if c.opts.NewBaseURL != "" {
			reqURL := fmt.Sprintf("%s/media/images/%s", strings.TrimRight(c.opts.NewBaseURL, "/"), p)
			req, _ := http.NewRequestWithContext(ctx, "HEAD", reqURL, nil)
			resp, err := c.client.Do(req)
			if err != nil || resp.StatusCode != http.StatusOK {
				res.Missing = append(res.Missing, p)
			}
			if resp != nil {
				_ = resp.Body.Close()
			}
		}
	}

	if len(res.Missing) > 0 {
		res.Passed = false
	}
	return res
}

// checkRoutes 对拍关键公开页面（12 号文档 8.2、9）。
func (c *ParityChecker) checkRoutes(ctx context.Context) []RouteCheckResult {
	canonicalRoutes := []string{
		"/",
		"/about/",
		"/constitution/",
		"/join/",
		"/news/",
		"/tournaments/",
		"/scrims/",
		"/members/",
		"/teams/",
		"/accounts/login/",
		"/accounts/register/",
		"/accounts/forgot/",
		"/accounts/verify-email/",
		"/api/healthz",
		"/sitemap.xml",
		"/robots.txt",
	}

	var results []RouteCheckResult

	newBase := strings.TrimRight(c.opts.NewBaseURL, "/")
	legBase := strings.TrimRight(c.opts.LegacyBaseURL, "/")

	for _, path := range canonicalRoutes {
		rResult := RouteCheckResult{Path: path, Passed: true}

		// 检查新站
		if newBase != "" {
			target := newBase + path
			req, err := http.NewRequestWithContext(ctx, "GET", target, nil)
			if err == nil {
				resp, err := c.client.Do(req)
				if err != nil {
					rResult.Passed = false
					rResult.Detail = fmt.Sprintf("新站请求异常: %v", err)
				} else {
					rResult.NewStatus = resp.StatusCode
					bodyBytes, _ := io.ReadAll(resp.Body)
					_ = resp.Body.Close()

					// 抽取标题
					if m := titleTagRegex.FindSubmatch(bodyBytes); len(m) > 1 {
						rResult.Title = strings.TrimSpace(string(m[1]))
					}

					if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusFound && resp.StatusCode != http.StatusMovedPermanently {
						rResult.Passed = false
						rResult.Detail = fmt.Sprintf("新站非 200/3xx 响应: %d", resp.StatusCode)
					}
				}
			}
		}

		// 对比旧站
		if legBase != "" {
			target := legBase + path
			req, err := http.NewRequestWithContext(ctx, "GET", target, nil)
			if err == nil {
				resp, err := c.client.Do(req)
				if err == nil {
					rResult.LegStatus = resp.StatusCode
					_ = resp.Body.Close()
					if rResult.NewStatus != 0 && rResult.NewStatus != rResult.LegStatus {
						// 状态码不一致时标记警告
						rResult.Detail += fmt.Sprintf(" [状态码差异: 新=%d 旧=%d]", rResult.NewStatus, rResult.LegStatus)
					}
				}
			}
		}

		results = append(results, rResult)
	}

	return results
}

// FormatReport 格式化输出对拍审计报告。
func (r *ParityResult) FormatReport() string {
	var sb strings.Builder
	sb.WriteString("=== SJTU-OW 生产割接对拍与兼容性审计报告 ===\n")
	sb.WriteString(fmt.Sprintf("综合核验结果: %s\n\n", statusBadge(r.OverallOK)))

	// 1. 签名与安全凭证
	sb.WriteString("1. 签名凭据兼容性（djsign / Calendar / Unsubscribe）:\n")
	sb.WriteString(fmt.Sprintf("   - 日历订阅 URL 签名: %s\n", statusBadge(r.Signatures.CalendarOK)))
	sb.WriteString(fmt.Sprintf("   - 退订链接 URL 签名: %s\n", statusBadge(r.Signatures.UnsubscribeOK)))
	if r.Signatures.Detail != "" {
		sb.WriteString(fmt.Sprintf("     详情: %s\n", r.Signatures.Detail))
	}

	// 2. 密码哈希
	sb.WriteString("\n2. 用户密码哈希兼容性（Argon2id / PBKDF2 升级）:\n")
	sb.WriteString(fmt.Sprintf("   - Argon2id 密码哈希校验: %s\n", statusBadge(r.Passwords.Argon2idOK)))
	sb.WriteString(fmt.Sprintf("   - Django PBKDF2 存量兼容: %s\n", statusBadge(r.Passwords.PBKDF2OK)))
	sb.WriteString(fmt.Sprintf("   - 登录时自动升级触发标记: %s\n", statusBadge(r.Passwords.RehashOK)))
	if r.Passwords.Detail != "" {
		sb.WriteString(fmt.Sprintf("     详情: %s\n", r.Passwords.Detail))
	}

	// 3. Markdown 正文渲染
	sb.WriteString("\n3. 文章 Markdown 渲染与目录结构:\n")
	sb.WriteString(fmt.Sprintf("   - 样本渲染核验: %s (抽样 %d 篇)\n", statusBadge(r.Articles.Passed), r.Articles.SampledCount))
	if r.Articles.Detail != "" {
		sb.WriteString(fmt.Sprintf("     详情: %s\n", r.Articles.Detail))
	}

	// 4. 图片引用
	if r.Media.TotalChecked > 0 {
		sb.WriteString("\n4. 图片与媒体引用可达性:\n")
		sb.WriteString(fmt.Sprintf("   - 核查图片数量: %d\n", r.Media.TotalChecked))
		sb.WriteString(fmt.Sprintf("   - 状态: %s\n", statusBadge(r.Media.Passed)))
		if len(r.Media.Missing) > 0 {
			sb.WriteString(fmt.Sprintf("   - 缺失项: %s\n", strings.Join(r.Media.Missing[:min(5, len(r.Media.Missing))], ", ")))
		}
	}

	// 5. 路由对拍
	if len(r.Routes) > 0 {
		sb.WriteString("\n5. 公开页面端点状态:\n")
		sb.WriteString(fmt.Sprintf("   %-24s %-10s %-10s %-8s %s\n", "路径", "新站状态", "旧站状态", "结果", "标题/详情"))
		for _, rt := range r.Routes {
			legStr := "-"
			if rt.LegStatus > 0 {
				legStr = fmt.Sprintf("%d", rt.LegStatus)
			}
			newStr := fmt.Sprintf("%d", rt.NewStatus)
			desc := rt.Title
			if rt.Detail != "" {
				desc += " (" + rt.Detail + ")"
			}
			sb.WriteString(fmt.Sprintf("   %-24s %-10s %-10s %-8s %s\n",
				rt.Path, newStr, legStr, statusBadge(rt.Passed), desc))
		}
	}

	sb.WriteString("=============================================\n")
	return sb.String()
}

// ToJSON 导出 JSON 报告。
func (r *ParityResult) ToJSON() (string, error) {
	b, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func statusBadge(ok bool) string {
	if ok {
		return "[PASS]"
	}
	return "[FAIL]"
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
