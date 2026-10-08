// Package auth 是认证底座（12 号文档 5.7）：Django 兼容的密码哈希、会话。
// 注册、登录、验证码那些流程在 M3；这里只提供验密码和发会话的原语。
package auth

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"errors"
	"fmt"
	"strconv"
	"strings"

	"golang.org/x/crypto/argon2"
	"golang.org/x/crypto/pbkdf2"
)

// Django 6 的 Argon2PasswordHasher 默认参数。新写的哈希用这一套，
// 割接后两周内回滚时旧站照样认。
const (
	argonTime    = 2
	argonMemory  = 102400
	argonThreads = 8
	argonKeyLen  = 32
	argonSaltLen = 16

	// 验一条别人塞进来的哈希时不按它要的内存去分配：超过我们自己的参数就拒。
	// 站上的存量哈希就是这套参数，没有更贵的。
	argonTimeMax = 4
)

// argonSlots 同时最多两个 Argon2（一次约 100 MB），多的排队。
var argonSlots = make(chan struct{}, 2)

func acquireArgon2(ctx context.Context) error {
	select {
	case argonSlots <- struct{}{}:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func releaseArgon2() { <-argonSlots }

// IsUsable 报告这串哈希能不能拿来登录。`!` 开头是注销时写的不可用密码。
func IsUsable(encoded string) bool {
	return encoded != "" && !strings.HasPrefix(encoded, "!")
}

// Unusable 造一个 `!` 开头的不可用密码（注销账号）。
func Unusable() (string, error) {
	var b [30]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return "!" + base64.RawURLEncoding.EncodeToString(b[:]), nil
}

// Hash 用 Django 的 Argon2 格式写一条新哈希。
func Hash(ctx context.Context, password string) (string, error) {
	salt := make([]byte, argonSaltLen)
	if _, err := rand.Read(salt); err != nil {
		return "", err
	}
	return hashArgon2(ctx, password, salt, argonTime, argonMemory, argonThreads)
}

func hashArgon2(ctx context.Context, password string, salt []byte, time, memory uint32, threads uint8) (string, error) {
	if err := acquireArgon2(ctx); err != nil {
		return "", err
	}
	defer releaseArgon2()
	sum := argon2.IDKey([]byte(password), salt, time, memory, threads, argonKeyLen)
	return fmt.Sprintf("argon2$argon2id$v=19$m=%d,t=%d,p=%d$%s$%s",
		memory, time, threads,
		base64.RawStdEncoding.EncodeToString(salt),
		base64.RawStdEncoding.EncodeToString(sum)), nil
}

// Verify 验密码。ok 是对不对；upgrade 表示对了、但该换成现在的 Argon2
// （PBKDF2，或者 Argon2 参数比现在的旧）。不可用密码、认不出的格式一律不对，
// 并且仍然跑一遍 Argon2，免得「这个账号没设密码」从耗时上被看出来。
func Verify(ctx context.Context, encoded, password string) (ok, upgrade bool, err error) {
	if password == "" || !IsUsable(encoded) {
		return false, false, burnArgon2(ctx)
	}
	switch {
	case strings.HasPrefix(encoded, "argon2$"):
		return verifyArgon2(ctx, encoded, password)
	case strings.HasPrefix(encoded, "pbkdf2_sha256$"):
		return verifyPBKDF2(encoded, password)
	default:
		return false, false, burnArgon2(ctx)
	}
}

func burnArgon2(ctx context.Context) error {
	if err := acquireArgon2(ctx); err != nil {
		return err
	}
	defer releaseArgon2()
	// 丢掉结果。盐固定，省一次随机数；算的是假密码。
	_ = argon2.IDKey([]byte("unusable"), []byte("timing-pad-salt!"), argonTime, argonMemory, argonThreads, argonKeyLen)
	return nil
}

func verifyArgon2(ctx context.Context, encoded, password string) (bool, bool, error) {
	salt, want, timeCost, memory, threads, err := parseArgon2(encoded)
	if err != nil {
		return false, false, nil
	}
	if err := acquireArgon2(ctx); err != nil {
		return false, false, err
	}
	defer releaseArgon2()
	got := argon2.IDKey([]byte(password), salt, timeCost, memory, threads, uint32(len(want)))
	ok := subtle.ConstantTimeCompare(got, want) == 1
	upgrade := ok && (timeCost != argonTime || memory != argonMemory || threads != argonThreads || len(want) != argonKeyLen)
	return ok, upgrade, nil
}

func parseArgon2(encoded string) (salt, sum []byte, timeCost, memory uint32, threads uint8, err error) {
	parts := strings.Split(encoded, "$")
	if len(parts) != 6 || parts[0] != "argon2" || parts[1] != "argon2id" || parts[2] != "v=19" {
		return nil, nil, 0, 0, 0, errBadHash
	}
	memory, timeCost, threads, err = parseArgon2Params(parts[3])
	if err != nil {
		return nil, nil, 0, 0, 0, err
	}
	if memory == 0 || memory > argonMemory || timeCost == 0 || timeCost > argonTimeMax || threads == 0 || threads > argonThreads {
		return nil, nil, 0, 0, 0, errBadHash
	}
	salt, err = base64.RawStdEncoding.DecodeString(parts[4])
	if err != nil || len(salt) == 0 {
		return nil, nil, 0, 0, 0, errBadHash
	}
	sum, err = base64.RawStdEncoding.DecodeString(parts[5])
	if err != nil || len(sum) == 0 {
		return nil, nil, 0, 0, 0, errBadHash
	}
	return salt, sum, timeCost, memory, threads, nil
}

func parseArgon2Params(s string) (memory, timeCost uint32, threads uint8, err error) {
	var gotM, gotT, gotP bool
	for _, part := range strings.Split(s, ",") {
		k, v, ok := strings.Cut(part, "=")
		if !ok {
			return 0, 0, 0, errBadHash
		}
		n, nerr := strconv.ParseUint(v, 10, 32)
		if nerr != nil {
			return 0, 0, 0, errBadHash
		}
		switch k {
		case "m":
			memory, gotM = uint32(n), true
		case "t":
			timeCost, gotT = uint32(n), true
		case "p":
			if n > 255 {
				return 0, 0, 0, errBadHash
			}
			threads, gotP = uint8(n), true
		default:
			return 0, 0, 0, errBadHash
		}
	}
	if !gotM || !gotT || !gotP {
		return 0, 0, 0, errBadHash
	}
	return memory, timeCost, threads, nil
}

var errBadHash = errors.New("认不出的密码哈希")

func verifyPBKDF2(encoded, password string) (bool, bool, error) {
	parts := strings.Split(encoded, "$")
	if len(parts) != 4 || parts[0] != "pbkdf2_sha256" {
		return false, false, nil
	}
	iter, err := strconv.Atoi(parts[1])
	if err != nil || iter < 1 || iter > 5_000_000 {
		return false, false, nil
	}
	want, err := base64.StdEncoding.DecodeString(parts[3])
	if err != nil || len(want) == 0 {
		return false, false, nil
	}
	got := pbkdf2.Key([]byte(password), []byte(parts[2]), iter, len(want), sha256.New)
	ok := subtle.ConstantTimeCompare(got, want) == 1
	// 存量的 PBKDF2 下次登录换成 Argon2。
	return ok, ok, nil
}
