package accounts

import (
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

// Overwatch rank score encoding (对齐 accounts/ranks.py 及设计附录 A).
// 0..4: Bronze 5..1
// 5..9: Silver 5..1
// 10..14: Gold 5..1
// 15..19: Platinum 5..1
// 20..24: Diamond 5..1
// 25..29: Master 5..1
// 30..34: Grandmaster 5..1
// 35..39: Champion 5..1
// 40: Top 500

type TierDef struct {
	Key   string
	Label string
	Index int
}

var TierDefs = []TierDef{
	{Key: "bronze", Label: "青铜", Index: 0},
	{Key: "silver", Label: "白银", Index: 1},
	{Key: "gold", Label: "黄金", Index: 2},
	{Key: "platinum", Label: "白金", Index: 3},
	{Key: "diamond", Label: "钻石", Index: 4},
	{Key: "master", Label: "大师", Index: 5},
	{Key: "grandmaster", Label: "宗师", Index: 6},
	{Key: "champion", Label: "英杰", Index: 7},
}

const (
	Top500Score   = 40
	Top500Tier    = "top500"
	UnrankedLabel = "未定级"
	Top500Label   = "前 500"
)

var tierIndexMap = func() map[string]int {
	m := make(map[string]int)
	for _, td := range TierDefs {
		m[td.Key] = td.Index
	}
	return m
}()

var tierLabelMap = func() map[string]string {
	m := make(map[string]string)
	for _, td := range TierDefs {
		m[td.Key] = td.Label
	}
	return m
}()

var indexTierMap = func() map[int]string {
	m := make(map[int]string)
	for _, td := range TierDefs {
		m[td.Index] = td.Key
	}
	return m
}()

// EncodeRank 编码 (tier, division) 到分数值。未定级为 nil。
func EncodeRank(tier string, division int) (*int, error) {
	if tier == "" || tier == "unranked" {
		return nil, nil
	}
	if tier == Top500Tier {
		s := Top500Score
		return &s, nil
	}
	idx, ok := tierIndexMap[tier]
	if !ok {
		return nil, fmt.Errorf("未知段位梯级: %s", tier)
	}
	if division < 1 || division > 5 {
		return nil, errors.New("段位小阶必须是 1 到 5")
	}
	score := idx*5 + (5 - division)
	return &score, nil
}

// DecodeRank 解码分数值到 (tier, division)。未定级返回 ("", 0, nil)。
func DecodeRank(score *int) (tier string, division int, err error) {
	if score == nil {
		return "", 0, nil
	}
	s := *score
	if s == Top500Score {
		return Top500Tier, 0, nil
	}
	if s < 0 || s > 39 {
		return "", 0, fmt.Errorf("未知段位分数: %d", s)
	}
	tierIdx := s / 5
	rem := s % 5
	t, ok := indexTierMap[tierIdx]
	if !ok {
		return "", 0, fmt.Errorf("未知段位分数: %d", s)
	}
	return t, 5 - rem, nil
}

// FormatRank 格式化段位分数为人读中文。
func FormatRank(score *int) string {
	tier, div, err := DecodeRank(score)
	if err != nil || tier == "" {
		return UnrankedLabel
	}
	if tier == Top500Tier {
		return Top500Label
	}
	return fmt.Sprintf("%s %d", tierLabelMap[tier], div)
}

// ValidateBattletag 验证 BattleTag 格式（规则 17，对齐 accounts/models.py:validate_battletag）。
// 格式为「名称#4-6位数字」，名称 2-12 字符，不能有空格或 #。
func ValidateBattletag(tag string) error {
	tag = strings.TrimSpace(tag)
	if strings.Count(tag, "#") != 1 {
		return errors.New("游戏 ID 格式为「名称#数字」。")
	}
	parts := strings.Split(tag, "#")
	name, digits := parts[0], parts[1]
	if strings.Contains(name, " ") || name == "" {
		return errors.New("名称不能包含空格或 #。")
	}
	nameLen := utf8.RuneCountInString(name)
	if nameLen < 2 || nameLen > 12 {
		return errors.New("名称长度必须是 2 到 12 个字符。")
	}
	if len(digits) < 4 || len(digits) > 6 {
		return errors.New("数字部分必须是 4 到 6 位数字。")
	}
	for _, c := range digits {
		if c < '0' || c > '9' {
			return errors.New("数字部分必须是 4 到 6 位数字。")
		}
	}
	return nil
}

// ValidateContact 验证联系方式（规则 19，对齐 accounts/models.py:validate_contact_value）。
func ValidateContact(cType, value string) error {
	text := strings.TrimSpace(value)
	switch cType {
	case ContactQQ:
		if len(text) < 5 || len(text) > 11 {
			return errors.New("QQ 号必须是 5 到 11 位数字。")
		}
		for _, c := range text {
			if c < '0' || c > '9' {
				return errors.New("QQ 号必须是 5 到 11 位数字。")
			}
		}
	case ContactWeChat:
		l := utf8.RuneCountInString(text)
		if l < 6 || l > 20 {
			return errors.New("微信号必须是 6 到 20 个字符。")
		}
	case ContactPhone:
		if len(text) != 11 || !strings.HasPrefix(text, "1") {
			return errors.New("手机号必须是 11 位中国大陆手机号。")
		}
		for _, c := range text {
			if c < '0' || c > '9' {
				return errors.New("手机号必须是 11 位中国大陆手机号。")
			}
		}
	case ContactOther:
		l := utf8.RuneCountInString(text)
		if l < 1 || l > 64 {
			return errors.New("其他联系方式最多 64 个字符。")
		}
	default:
		return errors.New("未知的联系方式类型。")
	}
	return nil
}

var linkInText = regexp.MustCompile(`(?i)https?:|www\.|\.(?:com|cn|net|org|top|xyz)\b`)

// ValidateMotto 验证个人宣言（规则 20，一行 ≤30 字且不能含链接）。
func ValidateMotto(motto string) error {
	motto = strings.TrimSpace(motto)
	if motto == "" {
		return nil
	}
	if strings.ContainsAny(motto, "\r\n") {
		return errors.New("个人宣言必须为单行。")
	}
	if utf8.RuneCountInString(motto) > 30 {
		return errors.New("个人宣言最多 30 字。")
	}
	if linkInText.MatchString(motto) {
		return errors.New("个人宣言里不能放链接。")
	}
	return nil
}

// ValidateNickname 验证昵称长度（2-16 字符，规则 1）。
func ValidateNickname(nick string) error {
	nick = strings.TrimSpace(nick)
	l := utf8.RuneCountInString(nick)
	if l < 2 || l > 16 {
		return errors.New("昵称必须是 2 到 16 个字符。")
	}
	return nil
}

// IsProfileComplete 检查资料是否完整（规则 18：至少 1 个游戏 ID + 至少 1 种联系方式）。
func IsProfileComplete(gameAccountCount, contactCount int) bool {
	return gameAccountCount >= 1 && contactCount >= 1
}

// PublicRankInfo 是单个位置的公开段位信息。
type PublicRankInfo struct {
	Score     *int   `json:"score"`
	Label     string `json:"label"`
	IsExpired bool   `json:"is_expired"`
}

// PublicRanksResult 汇总公开段位（规则 21：每个位置所有游戏 ID 中的最高分，>180 天标记过期）。
type PublicRanksResult struct {
	Tank    PublicRankInfo `json:"tank"`
	Damage  PublicRankInfo `json:"damage"`
	Support PublicRankInfo `json:"support"`
}

const rankExpirationDuration = 180 * 24 * time.Hour

// CalculatePublicRanks 计算用户所有游戏 ID 在各位置的最高段位。
// 不勾「公开段位」则返回未定级（规则 21）。
func CalculatePublicRanks(gas []GameAccount, showRank bool, now time.Time) PublicRanksResult {
	if !showRank || len(gas) == 0 {
		return PublicRanksResult{
			Tank:    PublicRankInfo{Label: UnrankedLabel},
			Damage:  PublicRankInfo{Label: UnrankedLabel},
			Support: PublicRankInfo{Label: UnrankedLabel},
		}
	}

	var maxTank, maxDamage, maxSupport *int
	var tankUpdated, damageUpdated, supportUpdated time.Time

	for _, ga := range gas {
		if ga.RankTank != nil {
			if maxTank == nil || *ga.RankTank > *maxTank {
				maxTank = ga.RankTank
				tankUpdated = ga.RanksUpdatedAt
			}
		}
		if ga.RankDamage != nil {
			if maxDamage == nil || *ga.RankDamage > *maxDamage {
				maxDamage = ga.RankDamage
				damageUpdated = ga.RanksUpdatedAt
			}
		}
		if ga.RankSupport != nil {
			if maxSupport == nil || *ga.RankSupport > *maxSupport {
				maxSupport = ga.RankSupport
				supportUpdated = ga.RanksUpdatedAt
			}
		}
	}

	res := PublicRanksResult{
		Tank:    PublicRankInfo{Score: maxTank, Label: FormatRank(maxTank)},
		Damage:  PublicRankInfo{Score: maxDamage, Label: FormatRank(maxDamage)},
		Support: PublicRankInfo{Score: maxSupport, Label: FormatRank(maxSupport)},
	}

	if maxTank != nil && !tankUpdated.IsZero() && now.Sub(tankUpdated) > rankExpirationDuration {
		res.Tank.IsExpired = true
	}
	if maxDamage != nil && !damageUpdated.IsZero() && now.Sub(damageUpdated) > rankExpirationDuration {
		res.Damage.IsExpired = true
	}
	if maxSupport != nil && !supportUpdated.IsZero() && now.Sub(supportUpdated) > rankExpirationDuration {
		res.Support.IsExpired = true
	}

	return res
}

// ParseRankScore 将前端传入的字符串或者数字解析为段位分（nil 表示未定级）。
func ParseRankScore(val any) (*int, error) {
	if val == nil {
		return nil, nil
	}
	switch v := val.(type) {
	case int:
		if v < 0 || v > Top500Score {
			return nil, fmt.Errorf("非法段位分数: %d", v)
		}
		return &v, nil
	case int64:
		i := int(v)
		if i < 0 || i > Top500Score {
			return nil, fmt.Errorf("非法段位分数: %d", i)
		}
		return &i, nil
	case float64:
		i := int(v)
		if i < 0 || i > Top500Score {
			return nil, fmt.Errorf("非法段位分数: %d", i)
		}
		return &i, nil
	case string:
		v = strings.TrimSpace(v)
		if v == "" {
			return nil, nil
		}
		i, err := strconv.Atoi(v)
		if err != nil || i < 0 || i > Top500Score {
			return nil, fmt.Errorf("非法段位分数: %s", v)
		}
		return &i, nil
	default:
		return nil, errors.New("无法解析段位分数")
	}
}
