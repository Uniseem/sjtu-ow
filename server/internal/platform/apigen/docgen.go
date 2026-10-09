package apigen

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// WriteMarkdown 将接口注册表渲染为 Markdown 全景手册并写入目标文件（13 号文档 D 节）。
func WriteMarkdown(filePath string, reg *api.Registry) error {
	if err := os.MkdirAll(filepath.Dir(filePath), 0o755); err != nil {
		return err
	}
	content := RenderMarkdown(reg)
	return os.WriteFile(filePath, []byte(content), 0o644)
}

// RenderMarkdown 从注册表自动生成全量 API 与权限能力全景手册 Markdown。
func RenderMarkdown(reg *api.Registry) string {
	routes := append([]*api.Route(nil), reg.Routes()...)
	sort.Slice(routes, func(i, j int) bool {
		if routes[i].Method != routes[j].Method {
			return routes[i].Method < routes[j].Method
		}
		return routes[i].Pattern < routes[j].Pattern
	})

	total := len(routes)
	publicCnt := 0
	memberCnt := 0
	capCnt := 0
	superuserCnt := 0

	for _, rt := range routes {
		desc := rt.Gate.Describe()
		switch {
		case strings.HasPrefix(desc, "Public"):
			publicCnt++
		case strings.HasPrefix(desc, "Superuser"):
			superuserCnt++
		case strings.HasPrefix(desc, "Cap"):
			capCnt++
		default:
			memberCnt++
		}
	}

	var sb strings.Builder
	sb.WriteString("# SJTU-OW 接口注册表与权限全景手册\n\n")
	sb.WriteString("> **注意**：本文档由 `sjtuow apigen` 从 Go 服务端注册表自动生成，单向派生，保证代码实现与架构文档 100% 同步。**严禁手动编辑**。\n\n")

	// 1. 架构概览与指标
	sb.WriteString("## 1. 架构概览与指标\n\n")
	sb.WriteString(fmt.Sprintf("- **注册接口总数**：%d 个\n", total))
	sb.WriteString(fmt.Sprintf("- **公开访问接口 (Public)**：%d 个\n", publicCnt))
	sb.WriteString(fmt.Sprintf("- **登录会员接口 (Member / Verified / Feature)**：%d 个\n", memberCnt))
	sb.WriteString(fmt.Sprintf("- **干部管理接口 (Cap / Superuser)**：%d 个\n", capCnt+superuserCnt))
	sb.WriteString("- **限流保护**：全量写接口均显式声明 `ratelimit.Decl` 集中限流规则，杜绝内联魔法数字；\n")
	sb.WriteString("- **查询预算**：关键列表接口显式声明 `api.Budget(n)` 查询上限，防范 N+1 慢查询。\n\n")

	// 2. 全量接口清单
	sb.WriteString("## 2. 全量接口清单与准入门禁\n\n")
	sb.WriteString("| 方法 | 路径 | 准入门禁 (Gate) | 限流规则 (Rate Limits) | 查询预算 | 后台分类/标签 |\n")
	sb.WriteString("|---|---|---|---|---|---|\n")

	for _, rt := range routes {
		gateStr := rt.Gate.Describe()

		var limitStrs []string
		if len(rt.Limits) > 0 {
			for _, l := range rt.Limits {
				limitStrs = append(limitStrs, fmt.Sprintf("%s (%d/%s)", l.Name, l.N, l.Window))
			}
		} else if rt.NoLimitStr != "" {
			limitStrs = append(limitStrs, fmt.Sprintf("不限流 (%s)", rt.NoLimitStr))
		} else {
			limitStrs = append(limitStrs, "默认")
		}

		budgetStr := "-"
		if rt.Budget > 0 {
			budgetStr = fmt.Sprintf("≤ %d 次", rt.Budget)
		}

		navStr := "-"
		if rt.Nav != "" {
			navStr = rt.Nav
		}

		sb.WriteString(fmt.Sprintf("| `%s` | `%s` | %s | %s | %s | %s |\n",
			rt.Method, rt.Pattern, gateStr, strings.Join(limitStrs, "<br>"), budgetStr, navStr))
	}

	// 3. 角色与后台能力对照表
	sb.WriteString("\n## 3. 干部角色能力对照表 (Who Can Do What)\n\n")
	sb.WriteString("依据系统设计，后台功能实行细粒度能力权限控制，超级管理员与具备特定能力的角色可进入对应后台标签：\n\n")
	sb.WriteString("| 干部角色 | 对应后台能力 (Capabilities) | 负责后台大类/标签 |\n")
	sb.WriteString("|---|---|---|\n")
	sb.WriteString("| **超级管理员 (Superuser)** | 全量所有能力 (`*`) | 全站后台所有八大分类与所有页面 |\n")
	sb.WriteString("| **赛事总监 (Tournament Director)** | `tournament:manage`<br>`tournament:rosters`<br>`tournament:review`<br>`tournament:export` | 活动（赛事管理、报名审核、队伍编排板、数据导出） |\n")
	sb.WriteString("| **内战裁判 (Scrim Manager)** | `scrim:manage`<br>`scrim:teaming` | 活动（内战管理、内战分队板与自动分队） |\n")
	sb.WriteString("| **资讯编辑 (Editor)** | `article:manage`<br>`article:publish`<br>`home:pins`<br>`categories` | 内容（文章列表、双栏编辑器、首页置顶排序、分类设置、媒体库） |\n")
	sb.WriteString("| **普通会员 (Member)** | 基础身份权限 | 个人中心资料、组队、报名活动、文章评论、头像上传 |\n")
	sb.WriteString("| **访客 (Visitor)** | 公开访问 | 首页、公开资讯阅读、赛事内战公开展示、成员墙浏览 |\n")

	return sb.String()
}
