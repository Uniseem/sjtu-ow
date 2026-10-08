package auth

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

// 盐是 0..15 共 16 字节。对照值由 argon2-cffi 的 hash_secret 打出
// （Django 的 Argon2PasswordHasher.encode 就是在这串前面加 "argon2"）。
func TestArgon2MatchesCffi(t *testing.T) {
	salt := make([]byte, 16)
	for i := range salt {
		salt[i] = byte(i)
	}
	got, err := hashArgon2(context.Background(), "Correct-Horse-Battery-1", salt, argonTime, argonMemory, argonThreads)
	if err != nil {
		t.Fatal(err)
	}
	const want = "argon2$argon2id$v=19$m=102400,t=2,p=8$AAECAwQFBgcICQoLDA0ODw$0wx1hXSRPdX5FuKUG9tzsWeLnCQ1U351d7S07ZE5tno"
	if got != want {
		t.Fatalf("和 argon2-cffi 不一致：\n得到 %s\n要   %s", got, want)
	}
	ok, upgrade, err := Verify(context.Background(), want, "Correct-Horse-Battery-1")
	if err != nil || !ok || upgrade {
		t.Fatalf("对照哈希应验过且参数已是现在的：ok=%v upgrade=%v err=%v", ok, upgrade, err)
	}
}

func TestArgon2RoundTripAndFormat(t *testing.T) {
	ctx := context.Background()
	encoded, err := Hash(ctx, "Correct-Horse-Battery-1")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(encoded, "argon2$argon2id$v=19$m=102400,t=2,p=8$") {
		t.Fatalf("不是 Django 的 Argon2 格式：%s", encoded)
	}
	ok, upgrade, err := Verify(ctx, encoded, "Correct-Horse-Battery-1")
	if err != nil || !ok || upgrade {
		t.Fatalf("自己写的哈希应验过且不用升级：ok=%v upgrade=%v err=%v", ok, upgrade, err)
	}
	ok, _, err = Verify(ctx, encoded, "wrong-password")
	if err != nil || ok {
		t.Fatalf("错密码应验不过：ok=%v err=%v", ok, err)
	}
}

// hashlib.pbkdf2_hmac("sha256", b"pw", b"salt", 1) 的结果。
// 轮数用 1 是为了测试快；Django 6 的默认 120 万在下一条。
func TestPBKDF2MatchesHashlib(t *testing.T) {
	ok, upgrade, err := Verify(context.Background(),
		"pbkdf2_sha256$1$salt$b0rYx47DZcBg5kjraU7kDepYSEsDcfvWFxWsRBC3OAo=", "pw")
	if err != nil || !ok || !upgrade {
		t.Fatalf("应验过并要求升级：ok=%v upgrade=%v err=%v", ok, upgrade, err)
	}
	ok, _, err = Verify(context.Background(),
		"pbkdf2_sha256$1$salt$b0rYx47DZcBg5kjraU7kDepYSEsDcfvWFxWsRBC3OAo=", "nope")
	if err != nil || ok {
		t.Fatalf("错密码：ok=%v err=%v", ok, err)
	}
}

// Django 6 PBKDF2PasswordHasher 的默认轮数。向量来自 Python hashlib。
func TestPBKDF2DjangoDefaultIterations(t *testing.T) {
	ok, upgrade, err := Verify(context.Background(),
		"pbkdf2_sha256$1200000$testsalt1234$6nJc7sfSC9nDbhlJ3YZtDucOzIdfuKLb9Agt3fOfAu0=",
		"Correct-Horse-Battery-1")
	if err != nil || !ok || !upgrade {
		t.Fatalf("Django 默认轮数应验过并升级：ok=%v upgrade=%v err=%v", ok, upgrade, err)
	}
}

func TestUnusablePasswordNeverMatches(t *testing.T) {
	u, err := Unusable()
	if err != nil {
		t.Fatal(err)
	}
	if IsUsable(u) || !strings.HasPrefix(u, "!") {
		t.Fatalf("不可用密码应以 ! 开头：%s", u)
	}
	ok, _, err := Verify(context.Background(), u, "Correct-Horse-Battery-1")
	if err != nil || ok {
		t.Fatalf("不可用密码应验不过：ok=%v err=%v", ok, err)
	}
	ok, _, err = Verify(context.Background(), "sha1$deadbeef", "x")
	if err != nil || ok {
		t.Fatalf("认不出的格式应验不过：ok=%v err=%v", ok, err)
	}
}

func TestArgon2SlotsAtMostTwo(t *testing.T) {
	ctx := context.Background()
	if err := acquireArgon2(ctx); err != nil {
		t.Fatal(err)
	}
	if err := acquireArgon2(ctx); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		releaseArgon2()
		releaseArgon2()
	})
	short, cancel := context.WithTimeout(ctx, 30*time.Millisecond)
	defer cancel()
	err := acquireArgon2(short)
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("第三个应排队到超时，得到 %v", err)
	}
}

func TestValidatePassword(t *testing.T) {
	if msgs := Validate("Correct-Horse-Battery-1", "a@b.co", "小明"); len(msgs) != 0 {
		t.Fatalf("好密码不应被拦：%v", msgs)
	}
	msgs := Validate("short", "a@b.co", "小明")
	if !contains(msgs, "至少 8") {
		t.Fatalf("太短：%v", msgs)
	}
	msgs = Validate("12345678", "a@b.co", "小明")
	if !contains(msgs, "数字") || !contains(msgs, "常见") {
		t.Fatalf("纯数字又常见：%v", msgs)
	}
	msgs = Validate("password", "a@b.co", "小明")
	if !contains(msgs, "常见") {
		t.Fatalf("常见密码：%v", msgs)
	}
	msgs = Validate("alice@example.com", "alice@example.com", "小明")
	if !contains(msgs, "邮箱") {
		t.Fatalf("和邮箱一样：%v", msgs)
	}
	msgs = Validate("playerone", "a@b.co", "playerone")
	if !contains(msgs, "昵称") {
		t.Fatalf("和昵称太像：%v", msgs)
	}
}

func TestCommonListHasTheUsualOnes(t *testing.T) {
	if !isCommon("password") || !isCommon("123456") {
		t.Fatal("常见密码表里应该有 password 和 123456")
	}
	if len(commonSet) < 19000 {
		t.Fatalf("常见密码表太短：%d", len(commonSet))
	}
}

func contains(msgs []string, part string) bool {
	for _, m := range msgs {
		if strings.Contains(m, part) {
			return true
		}
	}
	return false
}
