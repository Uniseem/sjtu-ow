package djsign

import (
	_ "embed"
	"encoding/json"
	"testing"
)

//go:embed testdata/golden.json
var goldenJSON []byte

type golden struct {
	Key             string `json:"key"`
	SaltCalendar    string `json:"salt_calendar"`
	Sign42          string `json:"sign_42"`
	SignPair        string `json:"sign_pair"`
	SaltUnsubscribe string `json:"salt_unsubscribe"`
	Dumps42         string `json:"dumps_42"`
	DumpsCompressed string `json:"dumps_compressed"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	var g golden
	if err := json.Unmarshal(goldenJSON, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// testdata/golden.json 是 Django 6 用同一把钥匙打出来的。改了算法这里就对不上。
func TestSignObjectMatchesDjango(t *testing.T) {
	g := loadGolden(t)
	got, err := SignObject(g.Key, g.SaltCalendar, 42)
	if err != nil {
		t.Fatal(err)
	}
	if got != g.Sign42 {
		t.Fatalf("日历（只有编号）：\n得到 %s\n要   %s", got, g.Sign42)
	}
	var id int
	if err := UnsignObject(g.Key, g.SaltCalendar, g.Sign42, &id); err != nil || id != 42 {
		t.Fatalf("解开：%d %v", id, err)
	}

	got, err = SignObject(g.Key, g.SaltCalendar, []int{7, 1})
	if err != nil {
		t.Fatal(err)
	}
	if got != g.SignPair {
		t.Fatalf("日历（编号+版本）：\n得到 %s\n要   %s", got, g.SignPair)
	}
	var pair []int
	if err := UnsignObject(g.Key, g.SaltCalendar, g.SignPair, &pair); err != nil || len(pair) != 2 || pair[0] != 7 || pair[1] != 1 {
		t.Fatalf("解开一对：%v %v", pair, err)
	}
}

func TestLoadsMatchesDjangoDumps(t *testing.T) {
	g := loadGolden(t)
	// dumps 中间那段是签发时的时间戳，整串固定，重签不会得到同一串。
	var id int
	if err := Loads(g.Key, g.SaltUnsubscribe, g.Dumps42, &id); err != nil || id != 42 {
		t.Fatalf("退订：%d %v", id, err)
	}
	var nums []int
	if err := Loads(g.Key, g.SaltUnsubscribe, g.DumpsCompressed, &nums); err != nil || len(nums) != 20 || nums[0] != 0 || nums[19] != 19 {
		t.Fatalf("压缩的：%v %v", nums, err)
	}
}

func TestDumpsRoundTripAndRejectsTamper(t *testing.T) {
	g := loadGolden(t)
	signed, err := Dumps(g.Key, g.SaltUnsubscribe, 9)
	if err != nil {
		t.Fatal(err)
	}
	var id int
	if err := Loads(g.Key, g.SaltUnsubscribe, signed, &id); err != nil || id != 9 {
		t.Fatalf("自己签的：%d %v", id, err)
	}
	bad := signed[:len(signed)-1] + "A"
	if err := Loads(g.Key, g.SaltUnsubscribe, bad, &id); err == nil {
		t.Fatal("改一个字符还应验过")
	}
	if err := UnsignObject(g.Key, g.SaltCalendar, "NDI:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", &id); err == nil {
		t.Fatal("假签名还应验过")
	}
}

func TestCompressedRoundTrip(t *testing.T) {
	body, err := encodeObject(make([]int, 30), true)
	if err != nil {
		t.Fatal(err)
	}
	if body[0] != '.' {
		t.Fatalf("30 个整数压完应该更短、带点：%s", body)
	}
	var nums []int
	if err := decodeObject(body, &nums); err != nil || len(nums) != 30 {
		t.Fatalf("解开压缩：%v %v", nums, err)
	}
}
