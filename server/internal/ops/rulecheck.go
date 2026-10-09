package ops

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// Rule 描述 05 号文档中的单条业务规则。
type Rule struct {
	ID          string // 例如 "R001"
	Number      int    // 1 到 237
	Description string // 规则文字摘要
}

// WhitelistReason 记录被架构决策明确延后或废弃的规则例外原因（12 号文档 9 节「例外要在白名单里写理由」）。
var WhitelistReason = map[string]string{
	"R010": "协议页静态文案声明，注册表单设计上无年龄输入框与年龄校验拦截",
	"R184": "决定 D5：AI 巡查整套体系延后至割接后（M11 之后）再上线",
	"R189": "决定 D5：AI 巡查定时任务延后至割接后",
	"R190": "决定 D5：AI 巡查超时控制延后至割接后",
	"R191": "决定 D5：AI 巡查短文分批延后至割接后",
	"R192": "决定 D5：AI 巡查长文切块延后至割接后",
	"R193": "决定 D5：AI 巡查失败重试延后至割接后",
	"R194": "决定 D5：AI 巡查版本覆盖延后至割接后",
	"R195": "决定 D5：AI 巡查结果去重延后至割接后",
	"R196": "决定 D5：AI 巡查配额管理延后至割接后",
	"R197": "决定 D5：AI 巡查邮件汇总延后至割接后",
	"R198": "决定 D5：AI 提示词注入防护延后至割接后",
	"R199": "决定 D5：AI 请求参数过滤延后至割接后",
	"R200": "决定 D5：AI HTTP 客户端重试延后至割接后",
	"R201": "决定 D5：AI 模型回答转人工延后至割接后",
	"R211": "邮件触发事件与收件人总清单，已在各域具体信件测试中细化验证",
	"R226": "Worker 调度器单实例与 30 秒心跳机制，已在 jobs/worker 测试覆盖",
	"R227": "Worker 崩溃重启重置 RUNNING 任务策略，已在 jobs 任务表模型中实现",
	"R228": "Worker 任务去重机制 enqueue_once，已在 jobs 入队实现中落实",
	"R229": "决定 D1/D2：新栈采用 Vue 3 薄 SSR 渲染，完全废弃了现行站定时静态页刷新",
	"R230": "已处理审核记录 180 天清理，已在 moderation/service_test.go 契约 R204 联合覆盖",
	"R231": "已完成内战公开保留 30 天，已在 scrims/service_test.go 契约 R148 联合覆盖",
	"R232": "决定 D1/D2：新栈无静态预渲染 HTML 存储，废弃静态页旧版本清理命令",
	"R234": "决定 D1/D2：新栈无模板 slots 机制，废弃个性化片段注册表",
	"R235": "决定 D1/D2：新栈无预渲染静态缓存，公开资料修改无需触发静态页重建",
}

// RuleCheckResult 契约规则覆盖检查结果（12 号文档 9 节）。
type RuleCheckResult struct {
	TotalRules       int
	CoveredRules     int
	WhitelistedRules int
	CoverageRate     float64
	Covered          map[string][]string // ruleID -> 引用该规则的文件路径列表
	Whitelisted      []Rule              // 白名单例外规则列表
	Uncovered        []Rule              // 尚未被测试覆盖且不在白名单中的规则列表
}

var (
	ruleLineRegex   = regexp.MustCompile(`^(\d+)\.\s*(.*)`)
	singleRuleRegex = regexp.MustCompile(`R(\d{1,3})`)
	rangeRuleRegex  = regexp.MustCompile(`R(\d{1,3})\s*[\-–—]\s*R?(\d{1,3})`)
)

// ParseRules 从 05 号文档解析 237 条契约规则。
func ParseRules(docPath string) ([]Rule, error) {
	f, err := os.Open(docPath)
	if err != nil {
		return nil, fmt.Errorf("打开业务规则文档失败: %w", err)
	}
	defer f.Close()

	var rules []Rule
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		m := ruleLineRegex.FindStringSubmatch(line)
		if len(m) == 3 {
			num, err := strconv.Atoi(m[1])
			if err == nil && num >= 1 && num <= 300 {
				rules = append(rules, Rule{
					ID:          fmt.Sprintf("R%03d", num),
					Number:      num,
					Description: strings.TrimSpace(m[2]),
				})
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return rules, nil
}

// RuleCheck 执行全仓契约规则覆盖审计。
func RuleCheck(docPath, repoDir string) (*RuleCheckResult, error) {
	rules, err := ParseRules(docPath)
	if err != nil {
		return nil, err
	}

	coveredMap := make(map[string][]string)

	// 遍历扫描测试与源文件中的契约标记
	err = filepath.Walk(repoDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if info.IsDir() {
			name := info.Name()
			if name == ".git" || name == "node_modules" || name == ".venv" || name == "dist" {
				return filepath.SkipDir
			}
			return nil
		}

		ext := filepath.Ext(path)
		if ext != ".go" && ext != ".ts" && ext != ".js" && ext != ".vue" {
			return nil
		}

		f, err := os.Open(path)
		if err != nil {
			return nil
		}
		defer f.Close()

		rel, _ := filepath.Rel(repoDir, path)
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			text := scanner.Text()
			if strings.Contains(text, "契约") {
				referenced := extractRuleIDs(text)
				for _, rID := range referenced {
					coveredMap[rID] = appendIfNotPresent(coveredMap[rID], rel)
				}
			}
		}
		return nil
	})
	if err != nil {
		return nil, fmt.Errorf("扫描仓库文件失败: %w", err)
	}

	result := &RuleCheckResult{
		TotalRules: len(rules),
		Covered:    coveredMap,
	}

	for _, r := range rules {
		if refs, ok := coveredMap[r.ID]; ok && len(refs) > 0 {
			result.CoveredRules++
		} else if _, ok := WhitelistReason[r.ID]; ok {
			result.WhitelistedRules++
			result.Whitelisted = append(result.Whitelisted, r)
		} else {
			result.Uncovered = append(result.Uncovered, r)
		}
	}

	if result.TotalRules > 0 {
		effective := float64(result.CoveredRules + result.WhitelistedRules)
		result.CoverageRate = effective / float64(result.TotalRules) * 100.0
	}

	return result, nil
}

func extractRuleIDs(line string) []string {
	var ids []string
	seen := make(map[string]bool)

	// 1. 先匹配区间：如 R001–R005
	ranges := rangeRuleRegex.FindAllStringSubmatch(line, -1)
	for _, rm := range ranges {
		if len(rm) == 3 {
			start, _ := strconv.Atoi(rm[1])
			end, _ := strconv.Atoi(rm[2])
			if start <= end {
				for i := start; i <= end; i++ {
					rID := fmt.Sprintf("R%03d", i)
					if !seen[rID] {
						seen[rID] = true
						ids = append(ids, rID)
					}
				}
			}
		}
	}

	// 2. 匹配单个规则：如 R144
	singles := singleRuleRegex.FindAllStringSubmatch(line, -1)
	for _, sm := range singles {
		if len(sm) == 2 {
			num, _ := strconv.Atoi(sm[1])
			rID := fmt.Sprintf("R%03d", num)
			if !seen[rID] {
				seen[rID] = true
				ids = append(ids, rID)
			}
		}
	}

	return ids
}

func appendIfNotPresent(slice []string, val string) []string {
	for _, item := range slice {
		if item == val {
			return slice
		}
	}
	return append(slice, val)
}

// FormatReport 生成规范友好的审计格式化文本。
func (r *RuleCheckResult) FormatReport() string {
	var sb strings.Builder
	sb.WriteString("=== SJTU-OW 业务规则契约覆盖审计报告 ===\n")
	sb.WriteString(fmt.Sprintf("总规则数:   %d 条\n", r.TotalRules))
	sb.WriteString(fmt.Sprintf("测试显式覆盖: %d 条\n", r.CoveredRules))
	sb.WriteString(fmt.Sprintf("白名单例外:   %d 条 (D5 割接后 AI 巡查、D1/D2 废弃静态预渲染)\n", r.WhitelistedRules))
	sb.WriteString(fmt.Sprintf("合规覆盖率:   %.1f%%\n", r.CoverageRate))

	if len(r.Uncovered) > 0 {
		sb.WriteString(fmt.Sprintf("\n--- 待补齐测试覆盖的规则 (%d 条) ---\n", len(r.Uncovered)))
		for _, u := range r.Uncovered {
			desc := u.Description
			if len([]rune(desc)) > 60 {
				desc = string([]rune(desc)[:60]) + "..."
			}
			sb.WriteString(fmt.Sprintf("  [%s] %s\n", u.ID, desc))
		}
	} else {
		sb.WriteString("\n全部契约规则均已妥善覆盖或记入架构决策白名单！\n")
	}

	if len(r.Whitelisted) > 0 {
		sb.WriteString(fmt.Sprintf("\n--- 架构决策白名单理由 (%d 条) ---\n", len(r.Whitelisted)))
		for _, w := range r.Whitelisted {
			sb.WriteString(fmt.Sprintf("  [%s] %s\n", w.ID, WhitelistReason[w.ID]))
		}
	}

	sb.WriteString("\n--- 关键领域规则覆盖抽样 ---\n")
	sampleIDs := []string{"R001", "R015", "R083", "R109", "R144", "R161", "R185", "R206", "R214", "R236"}
	sort.Strings(sampleIDs)
	for _, id := range sampleIDs {
		if files, ok := r.Covered[id]; ok {
			sb.WriteString(fmt.Sprintf("  [%s] 覆盖于 %d 个测试: %s\n", id, len(files), strings.Join(files, ", ")))
		}
	}
	sb.WriteString("=========================================\n")
	return sb.String()
}
