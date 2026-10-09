package scrims

import (
	"errors"
	"fmt"
	"math/rand"
	"sort"
	"strings"
)

// 分队算法（设计 9.4，规则 159–163）。
//
// 角色限定要把每个人放进他真的能打的位置，并让两队尽量接近；不限位置只平衡总分。
// 搜索是穷举但很小：5v5 把第一个人固定在 A 队，其余 C(9,4)=126 种；6v6 是 462 种。
// 每队的合法位置分配全部枚举（5v5 最多 30，6v6 最多 90）后按（总分，各位置总分）去重、按总分排序，
// 两侧配对用二分定位 + 向外扩展 + 已知最优剪枝，保证约 1 秒内算完。

// ErrNoSolution 表示没有合法的分队方案，文案说明原因。
type ErrNoSolution struct{ Msg string }

func (e *ErrNoSolution) Error() string { return e.Msg }

func noSolution(format string, a ...any) error { return &ErrNoSolution{Msg: fmt.Sprintf(format, a...)} }

// IsNoSolution 报 err 是不是「无解」。
func IsNoSolution(err error) bool {
	var e *ErrNoSolution
	return errors.As(err, &e)
}

// Player 是一个上场的报名，只留算法要的东西。
type Player struct {
	SignupID  int64
	Nickname  string
	Battletag string
	Roles     []string
	Ratings   map[string]int // 位置 → 分数，只有填了段位的位置
	Best      int            // 所选游戏 ID 上的最高分（不限位置用）
}

func (p Player) has(role string) bool {
	for _, r := range p.Roles {
		if r == role {
			return true
		}
	}
	return false
}

// Rating 某位置的分数，没有就是 0。
func (p Player) Rating(role string) int { return p.Ratings[role] }

// Assignment 是一队的位置分配和设计 9.4 要比较的各项总分。
type Assignment struct {
	ByRole     map[string][]int64 // 位置 → 报名编号
	Total      int
	RoleTotals map[string]int
}

// Split 是一个分队方案。
type Split struct {
	A, B  Assignment
	Score [2]int
}

func less(a, b [2]int) bool {
	if a[0] != b[0] {
		return a[0] < b[0]
	}
	return a[1] < b[1]
}

// CheckFeasible 搜索之前先说明为什么无解（规则 159）。
func CheckFeasible(players []Player, format string) error {
	needed := TeamSize(format) * 2
	if len(players) != needed {
		return noSolution("需要正好 %d 人才能分队，当前勾选了 %d 人。", needed, len(players))
	}
	if !RoleQueue(format) {
		return nil
	}
	for _, role := range RoleOrder {
		perTeam := Requirements(format)[role]
		able := 0
		for _, p := range players {
			if p.has(role) {
				able++
			}
		}
		if able < perTeam*2 {
			return noSolution("能打%s的玩家只有 %d 人，%s 需要至少 %d 人。", RoleLabels[role], able, FormatLabels[format], perTeam*2)
		}
	}
	var stuck []string
	for _, p := range players {
		if len(p.Ratings) == 0 {
			stuck = append(stuck, p.Nickname)
		}
	}
	if len(stuck) > 0 {
		return noSolution("这些玩家在所选游戏 ID 上没有可用的段位：%s。", strings.Join(stuck, "、"))
	}
	return nil
}

// combinations 按下标字典序给出 items 里取 k 个的所有组合（和 Python 的 itertools.combinations 同序）。
func combinations[T any](items []T, k int, fn func([]T)) {
	n := len(items)
	if k > n {
		return
	}
	idx := make([]int, k)
	for i := range idx {
		idx[i] = i
	}
	buf := make([]T, k)
	for {
		for i, j := range idx {
			buf[i] = items[j]
		}
		fn(buf)
		i := k - 1
		for i >= 0 && idx[i] == i+n-k {
			i--
		}
		if i < 0 {
			return
		}
		idx[i]++
		for j := i + 1; j < k; j++ {
			idx[j] = idx[j-1] + 1
		}
	}
}

// assignments 用刚好这几个人填满要求的位置，所有合法的填法。
func assignments(team []Player, req map[string]int) []Assignment {
	var results []Assignment
	var roles []string
	for _, r := range RoleOrder {
		if req[r] > 0 {
			roles = append(roles, r)
		}
	}
	rating := map[int64]Player{}
	for _, p := range team {
		rating[p.SignupID] = p
	}
	chosen := map[string][]int64{}
	var walk func(index int, remaining []Player)
	walk = func(index int, remaining []Player) {
		if index == len(roles) {
			if len(remaining) > 0 {
				return
			}
			by := map[string][]int64{}
			totals := map[string]int{}
			sum := 0
			for role, ids := range chosen {
				by[role] = append([]int64(nil), ids...)
				t := 0
				for _, id := range ids {
					t += rating[id].Rating(role)
				}
				totals[role] = t
				sum += t
			}
			results = append(results, Assignment{ByRole: by, Total: sum, RoleTotals: totals})
			return
		}
		role := roles[index]
		var eligible []Player
		for _, p := range remaining {
			if p.has(role) {
				eligible = append(eligible, p)
			}
		}
		combinations(eligible, req[role], func(picked []Player) {
			picks := map[int64]bool{}
			ids := make([]int64, len(picked))
			for i, p := range picked {
				picks[p.SignupID] = true
				ids[i] = p.SignupID
			}
			var still []Player
			for _, p := range remaining {
				if !picks[p.SignupID] {
					still = append(still, p)
				}
			}
			chosen[role] = ids
			walk(index+1, still)
			delete(chosen, role)
		})
	}
	walk(0, team)
	return results
}

// prune 配对之前先去重再按总分排序（设计 9.4）：总分和各位置总分都相同的两种分配，对任何
// 对手的得分一样，留一个就够。
func prune(list []Assignment) []Assignment {
	seen := map[string]bool{}
	var out []Assignment
	for _, a := range list {
		key := fmt.Sprintf("%d|%d|%d|%d", a.Total, a.RoleTotals[Tank], a.RoleTotals[Damage], a.RoleTotals[Support])
		if !seen[key] {
			seen[key] = true
			out = append(out, a)
		}
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].Total < out[j].Total })
	return out
}

func abs(n int) int {
	if n < 0 {
		return -n
	}
	return n
}

// score 先比两队总分差，再比各位置分差之和（规则 161）。
func score(a, b Assignment) [2]int {
	gap := 0
	for role, t := range a.RoleTotals {
		gap += abs(t - b.RoleTotals[role])
	}
	return [2]int{abs(a.Total - b.Total), gap}
}

// bestPairing 最便宜的（a, b）配对。两侧都按总分排好序，用二分找到离 a 最近的，再向外扩展，
// 只要总分差还可能有用就继续。limit 是之前各种拆分里最好的得分：总分差已经超过 limit[0] 的
// 严格更差，赢不了也平不了，可以停——这样平局仍能收集齐，「重新生成」才有随机性。
func bestPairing(sideA, sideB []Assignment, limit *[2]int) (pa, pb *Assignment, best [2]int, ok bool) {
	totals := make([]int, len(sideB))
	for i, b := range sideB {
		totals[i] = b.Total
	}
	for ai := range sideA {
		a := &sideA[ai]
		position := sort.SearchInts(totals, a.Total)
		low, high := position-1, position
		for low >= 0 || high < len(sideB) {
			var ci int
			switch {
			case low >= 0 && high < len(sideB):
				if a.Total-totals[low] <= totals[high]-a.Total {
					ci, low = low, low-1
				} else {
					ci, high = high, high+1
				}
			case low >= 0:
				ci, low = low, low-1
			default:
				ci, high = high, high+1
			}
			c := &sideB[ci]
			gap := abs(a.Total - c.Total)
			if limit != nil && gap > limit[0] {
				break
			}
			if ok && gap > best[0] {
				break
			}
			s := score(*a, *c)
			if !ok || less(s, best) {
				pa, pb, best, ok = a, c, s, true
			}
		}
		if ok && best == [2]int{0, 0} {
			break
		}
	}
	return
}

func without(all []Player, others []Player) []Player {
	in := map[int64]bool{}
	for _, p := range others {
		in[p.SignupID] = true
	}
	var out []Player
	for _, p := range all {
		if !in[p.SignupID] {
			out = append(out, p)
		}
	}
	return out
}

type candidate struct {
	score [2]int
	a, b  Assignment
}

// roleQueueSplits 对每种可行的拆分给出（得分，A 队分配，B 队分配）。
func roleQueueSplits(players []Player, req map[string]int, yield func(candidate)) {
	first, rest := players[0], players[1:]
	size := len(players) / 2
	var best *[2]int
	combinations(rest, size-1, func(others []Player) {
		teamA := append([]Player{first}, others...)
		teamB := without(rest, others)
		sideA := prune(assignments(teamA, req))
		if len(sideA) == 0 {
			return
		}
		sideB := prune(assignments(teamB, req))
		if len(sideB) == 0 {
			return
		}
		pa, pb, s, ok := bestPairing(sideA, sideB, best)
		if !ok {
			return
		}
		if best == nil || less(s, *best) {
			v := s
			best = &v
		}
		yield(candidate{score: s, a: *pa, b: *pb})
	})
}

func openSplits(players []Player, yield func(candidate)) {
	first, rest := players[0], players[1:]
	size := len(players) / 2
	combinations(rest, size-1, func(others []Player) {
		teamA := append([]Player{first}, others...)
		teamB := without(rest, others)
		sum := func(ps []Player) (int, []int64) {
			t := 0
			ids := make([]int64, len(ps))
			for i, p := range ps {
				t += p.Best
				ids[i] = p.SignupID
			}
			return t, ids
		}
		ta, ia := sum(teamA)
		tb, ib := sum(teamB)
		yield(candidate{
			score: [2]int{abs(ta - tb), 0},
			a:     Assignment{ByRole: map[string][]int64{"": ia}, Total: ta, RoleTotals: map[string]int{}},
			b:     Assignment{ByRole: map[string][]int64{"": ib}, Total: tb, RoleTotals: map[string]int{}},
		})
	})
}

// Generate 最好的分队方案；得分并列时随机取一个（规则 161）。
func Generate(players []Player, format string, rng *rand.Rand) (*Split, error) {
	if err := CheckFeasible(players, format); err != nil {
		return nil, err
	}
	var best [2]int
	var tied []Split
	collect := func(c candidate) {
		switch {
		case tied == nil || less(c.score, best):
			best = c.score
			tied = []Split{{A: c.a, B: c.b, Score: c.score}}
		case c.score == best:
			tied = append(tied, Split{A: c.a, B: c.b, Score: c.score})
		}
	}
	if RoleQueue(format) {
		roleQueueSplits(players, Requirements(format), collect)
	} else {
		openSplits(players, collect)
	}
	if len(tied) == 0 {
		return nil, noSolution("找不到合法的分队方案：每个位置都要有足够的、能打这个位置的玩家。")
	}
	if rng == nil {
		rng = rand.New(rand.NewSource(rand.Int63()))
	}
	pick := tied[rng.Intn(len(tied))]
	return &pick, nil
}

// UnratedPlacements 被放进了没有段位的位置的人，按 0 分算（规则 163）。
func UnratedPlacements(sp *Split, players []Player, format string) []string {
	if !RoleQueue(format) {
		return nil
	}
	lookup := map[int64]Player{}
	for _, p := range players {
		lookup[p.SignupID] = p
	}
	var found []string
	for _, a := range []Assignment{sp.A, sp.B} {
		for _, role := range RoleOrder {
			for _, id := range a.ByRole[role] {
				p := lookup[id]
				if _, ok := p.Ratings[role]; !ok {
					found = append(found, fmt.Sprintf("%s（%s）", p.Nickname, RoleLabels[role]))
				}
			}
		}
	}
	return found
}

// RatingsUsed 每个人分队时按多少分算的，写进 rating_used。
func RatingsUsed(sp *Split, players []Player, format string) map[int64]int {
	lookup := map[int64]Player{}
	for _, p := range players {
		lookup[p.SignupID] = p
	}
	used := map[int64]int{}
	for _, a := range []Assignment{sp.A, sp.B} {
		for role, ids := range a.ByRole {
			for _, id := range ids {
				p := lookup[id]
				if RoleQueue(format) {
					used[id] = p.Rating(role)
				} else {
					used[id] = p.Best
				}
			}
		}
	}
	return used
}
