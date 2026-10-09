package scrims

import (
	"fmt"
	"math/rand"
	"testing"
	"time"
)

// 造一桌玩家：每人随机能打 1–3 个位置，只对勾选的位置有段位。
func randomPlayers(rng *rand.Rand, n int, rated bool) []Player {
	out := make([]Player, 0, n)
	for i := 0; i < n; i++ {
		p := Player{SignupID: int64(i + 1), Nickname: fmt.Sprintf("P%d", i+1), Ratings: map[string]int{}}
		for _, r := range RoleOrder {
			if rng.Intn(100) < 55 {
				p.Roles = append(p.Roles, r)
			}
		}
		if len(p.Roles) == 0 {
			p.Roles = []string{RoleOrder[rng.Intn(3)]}
		}
		for _, r := range p.Roles {
			p.Ratings[r] = 1000 + rng.Intn(40)*100
			if rated && p.Ratings[r] > p.Best {
				p.Best = p.Ratings[r]
			}
		}
		out = append(out, p)
	}
	return out
}

// refScore 测试里自己写一份得分（总分差，再各位置总分差之和），不借被测代码的 score()。
func refScore(a, b Assignment) [2]int {
	gap := 0
	for _, role := range RoleOrder {
		d := a.RoleTotals[role] - b.RoleTotals[role]
		if d < 0 {
			d = -d
		}
		gap += d
	}
	t := a.Total - b.Total
	if t < 0 {
		t = -t
	}
	return [2]int{t, gap}
}

// 暴力穷举：枚举全部拆分（不固定第一个人）和每队全部合法位置分配，取最小得分。
func bruteBest(players []Player, format string) ([2]int, bool) {
	size := len(players) / 2
	req := Requirements(format)
	best, found := [2]int{}, false
	var pick func(start int, chosen []int)
	pick = func(start int, chosen []int) {
		if len(chosen) == size {
			in := map[int]bool{}
			var a, b []Player
			for _, i := range chosen {
				in[i] = true
				a = append(a, players[i])
			}
			for i, p := range players {
				if !in[i] {
					b = append(b, p)
				}
			}
			var sa, sb []Assignment
			if RoleQueue(format) {
				sa, sb = assignments(a, req), assignments(b, req)
			} else {
				ta, tb := 0, 0
				for _, p := range a {
					ta += p.Best
				}
				for _, p := range b {
					tb += p.Best
				}
				s := [2]int{abs(ta - tb), 0}
				if !found || s[0] < best[0] {
					best, found = s, true
				}
				return
			}
			for _, x := range sa {
				for _, y := range sb {
					s := refScore(x, y)
					if !found || (s[0] < best[0] || (s[0] == best[0] && s[1] < best[1])) {
						best, found = s, true
					}
				}
			}
			return
		}
		for i := start; i < len(players); i++ {
			pick(i+1, append(chosen, i))
		}
	}
	pick(0, nil)
	return best, found
}

func validSplit(t *testing.T, sp *Split, players []Player, format string) {
	t.Helper()
	lookup := map[int64]Player{}
	for _, p := range players {
		lookup[p.SignupID] = p
	}
	seen := map[int64]bool{}
	for _, a := range []Assignment{sp.A, sp.B} {
		n := 0
		for role, ids := range a.ByRole {
			if RoleQueue(format) && len(ids) != Requirements(format)[role] {
				t.Fatalf("位置 %s 要 %d 人，给了 %d", role, Requirements(format)[role], len(ids))
			}
			for _, id := range ids {
				if seen[id] {
					t.Fatalf("%d 被放了两次", id)
				}
				seen[id] = true
				n++
				if RoleQueue(format) && !lookup[id].has(role) {
					t.Fatalf("%d 被放进了他不能打的位置 %s", id, role)
				}
			}
		}
		if n != TeamSize(format) {
			t.Fatalf("每队 %d 人，给了 %d", TeamSize(format), n)
		}
	}
	if len(seen) != len(players) {
		t.Fatalf("有人没放进去：%d/%d", len(seen), len(players))
	}
}

// 契约 R160、R161、R162：每队位置需求（5v5 1/2/2, 6v6 2/2/2）与分队得分和暴力穷举一致（总分差最小，再各位置分差之和最小）
func TestTeamingMatchesBruteForce(t *testing.T) {
	rng := rand.New(rand.NewSource(42))
	checked := 0
	for round := 0; round < 40 && checked < 12; round++ {
		players := randomPlayers(rng, 10, true)
		want, ok := bruteBest(players, FormatRQ5)
		got, err := Generate(players, FormatRQ5, rand.New(rand.NewSource(int64(round))))
		if !ok {
			if err == nil {
				t.Fatalf("暴力穷举无解，算法却给了解")
			}
			continue
		}
		if err != nil {
			if IsNoSolution(err) && err.Error() != "" {
				// 可行性检查先拦下（某位置人数不够）：暴力穷举里 assignments 也会为空，所以 ok 应为 false
				t.Fatalf("暴力穷举有解 %v，算法说无解：%v", want, err)
			}
			t.Fatal(err)
		}
		if got.Score != want {
			t.Fatalf("第 %d 桌：算法得分 %v，暴力穷举 %v", round, got.Score, want)
		}
		validSplit(t, got, players, FormatRQ5)
		checked++
	}
	if checked < 6 {
		t.Fatalf("可用的随机桌太少：%d", checked)
	}
	// 不限位置：总分差最小
	for round := 0; round < 5; round++ {
		players := randomPlayers(rng, 10, true)
		want, _ := bruteBest(players, Open5)
		got, err := Generate(players, Open5, rand.New(rand.NewSource(int64(round))))
		if err != nil || got.Score != want {
			t.Fatalf("不限位置：%v %v 要 %v", got, err, want)
		}
	}
	// 6v6 少量对拍
	n6 := 0
	for round := 0; round < 30 && n6 < 2; round++ {
		players := randomPlayers(rng, 12, true)
		want, ok := bruteBest(players, FormatRQ6)
		if !ok {
			continue
		}
		got, err := Generate(players, FormatRQ6, rand.New(rand.NewSource(int64(round))))
		if err != nil || got.Score != want {
			t.Fatalf("6v6：%v %v 要 %v", got, err, want)
		}
		validSplit(t, got, players, FormatRQ6)
		n6++
	}
	if n6 == 0 {
		t.Fatal("没找到可对拍的 6v6 桌")
	}
}

// 契约 R162：6v6 在预算内算完（设计 9.4 约 1 秒；机器忙时放宽到 3 秒）
func TestTeamingTimeBudget(t *testing.T) {
	rng := rand.New(rand.NewSource(7))
	players := randomPlayers(rng, 12, true)
	for j := range players { // 每人都能打全部位置：搜索空间最大
		players[j].Roles = []string{Tank, Damage, Support}
		players[j].Ratings = map[string]int{Tank: 2000 + rng.Intn(30)*100, Damage: 2000 + rng.Intn(30)*100, Support: 2000 + rng.Intn(30)*100}
	}
	start := time.Now()
	if _, err := Generate(players, FormatRQ6, rand.New(rand.NewSource(1))); err != nil {
		t.Fatal(err)
	}
	if d := time.Since(start); d > 3*time.Second {
		t.Fatalf("6v6 全能桌用了 %v", d)
	}
}

// 契约 R161：得分并列时随机取一个，「重新生成」才有不同结果
func TestTeamingTiesAreRandom(t *testing.T) {
	players := make([]Player, 10)
	for i := range players {
		players[i] = Player{SignupID: int64(i + 1), Nickname: fmt.Sprintf("P%d", i+1), Roles: []string{Tank, Damage, Support},
			Ratings: map[string]int{Tank: 3000, Damage: 3000, Support: 3000}, Best: 3000}
	}
	seen := map[string]bool{}
	for seed := int64(0); seed < 30; seed++ {
		sp, err := Generate(players, FormatRQ5, rand.New(rand.NewSource(seed)))
		if err != nil {
			t.Fatal(err)
		}
		if sp.Score != [2]int{0, 0} {
			t.Fatalf("全一样的人应该能分到 0 差：%v", sp.Score)
		}
		seen[fmt.Sprint(sp.A.ByRole[Tank], sp.A.ByRole[Damage], sp.A.ByRole[Support])] = true
	}
	if len(seen) < 3 {
		t.Fatalf("并列时应有不同的结果，30 次只出现 %d 种", len(seen))
	}
	// 同一个随机源种子给同样的结果（可复现）
	a, _ := Generate(players, FormatRQ5, rand.New(rand.NewSource(9)))
	b, _ := Generate(players, FormatRQ5, rand.New(rand.NewSource(9)))
	if fmt.Sprint(a.A.ByRole) != fmt.Sprint(b.A.ByRole) {
		t.Fatal("同种子应同结果")
	}
}

// 契约 R159：可行性前置检查，原因写清楚
func TestTeamingFeasibility(t *testing.T) {
	rng := rand.New(rand.NewSource(3))
	nine := randomPlayers(rng, 9, true)
	_, err := Generate(nine, FormatRQ5, nil)
	if err == nil || !IsNoSolution(err) || err.Error() != "需要正好 10 人才能分队，当前勾选了 9 人。" {
		t.Fatalf("人数不对：%v", err)
	}
	// 没人能打坦克
	players := randomPlayers(rng, 10, true)
	for i := range players {
		players[i].Roles = []string{Damage, Support}
		players[i].Ratings = map[string]int{Damage: 2000, Support: 2000}
	}
	_, err = Generate(players, FormatRQ5, nil)
	if err == nil || err.Error() != "能打坦克的玩家只有 0 人，角色限定 5v5 需要至少 2 人。" {
		t.Fatalf("位置不够：%v", err)
	}
	// 所选游戏 ID 上没有任何段位
	players = randomPlayers(rng, 10, true)
	for i := range players {
		players[i].Roles = []string{Tank, Damage, Support}
		players[i].Ratings = map[string]int{Tank: 2000, Damage: 2000, Support: 2000}
	}
	players[3].Ratings = map[string]int{}
	_, err = Generate(players, FormatRQ5, nil)
	if err == nil || err.Error() != "这些玩家在所选游戏 ID 上没有可用的段位：P4。" {
		t.Fatalf("没有段位：%v", err)
	}
	// 不限位置只看人数
	if _, err := Generate(nine, Open5, nil); err == nil {
		t.Fatal("不限位置也要正好 10 人")
	}
	// 6v6 的 12 人
	if _, err := Generate(randomPlayers(rng, 10, true), FormatRQ6, nil); err == nil || err.Error() != "需要正好 12 人才能分队，当前勾选了 10 人。" {
		t.Fatalf("6v6：%v", err)
	}
}

// 契约 R163：被放进没有段位的位置的人，按 0 分算并列出来。
// 构造成必然发生：全桌只有 P1、P2 能打坦克，P1 的坦克位没有段位，所以 P1 一定被放在坦克位。
func TestUnratedPlacements(t *testing.T) {
	players := make([]Player, 10)
	for i := range players {
		players[i] = Player{SignupID: int64(i + 1), Nickname: fmt.Sprintf("P%d", i+1), Roles: []string{Damage, Support},
			Ratings: map[string]int{Damage: 2500, Support: 2500}, Best: 2500}
	}
	players[0].Roles = []string{Tank, Damage}
	players[0].Ratings = map[string]int{Damage: 2500}
	players[1].Roles = []string{Tank, Damage, Support}
	players[1].Ratings = map[string]int{Tank: 2600, Damage: 2500, Support: 2500}
	players[1].Best = 2600
	sp, err := Generate(players, FormatRQ5, rand.New(rand.NewSource(1)))
	if err != nil {
		t.Fatal(err)
	}
	un := UnratedPlacements(sp, players, FormatRQ5)
	if len(un) != 1 || un[0] != "P1（坦克）" {
		t.Fatalf("P1 被放在没有段位的坦克位，应列出来：%v", un)
	}
	used := RatingsUsed(sp, players, FormatRQ5)
	if used[1] != 0 || used[2] != 2600 {
		t.Fatalf("没有段位的位置按 0 分，有的按该位置的段位：P1=%d P2=%d", used[1], used[2])
	}
	if len(UnratedPlacements(sp, players, Open5)) != 0 {
		t.Fatal("不限位置没有这个提醒")
	}
}
