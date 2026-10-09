// Package djsign 实现 Django 的签名（12 号文档 5.11）：日历订阅地址和退订
// 链接在割接后还要能验。新签发的也用这一套，这样只有一种格式。
//
// 钥匙 = SHA-256(盐 + "signer" + 密钥)，然后 HMAC-SHA256，URL 安全 base64、
// 不带填充。dumps / loads 在签名前再加一个 base62 时间戳；正文前有 "." 表示
// zlib 压缩过。
package djsign

import (
	"bytes"
	"compress/zlib"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"errors"
	"io"
	"strings"
	"time"
)

const sep = ":"

const base62Alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

// SignObject 是 Signer(salt).sign_object：不带时间戳。日历地址用这个。
func SignObject(key, salt string, obj any) (string, error) {
	body, err := encodeObject(obj, false)
	if err != nil {
		return "", err
	}
	return body + sep + signature(salt, body, key), nil
}

// UnsignObject 验 SignObject 的结果，把 JSON 解进 dest。
func UnsignObject(key, salt, signed string, dest any) error {
	body, err := unsign(key, salt, signed)
	if err != nil {
		return err
	}
	return decodeObject(body, dest)
}

// Dumps 是 signing.dumps：TimestampSigner，带 base62 时间戳。退订链接用这个。
func Dumps(key, salt string, obj any) (string, error) {
	body, err := encodeObject(obj, false)
	if err != nil {
		return "", err
	}
	stamped := body + sep + b62Encode(time.Now().Unix())
	return stamped + sep + signature(salt, stamped, key), nil
}

// Loads 验 Dumps 的结果。不查过期（退订链接没有有效期）。
func Loads(key, salt, signed string, dest any) error {
	stamped, err := unsign(key, salt, signed)
	if err != nil {
		return err
	}
	// 时间戳在最后一段。正文是 base64（压缩的前面多一个 "."），不含 ":"。
	idx := strings.LastIndex(stamped, sep)
	if idx < 0 {
		return errBad
	}
	if _, err := b62Decode(stamped[idx+1:]); err != nil {
		return err
	}
	return decodeObject(stamped[:idx], dest)
}

func encodeObject(obj any, compress bool) (string, error) {
	data, err := json.Marshal(obj)
	if err != nil {
		return "", err
	}
	if compress {
		var buf bytes.Buffer
		w, err := zlib.NewWriterLevel(&buf, zlib.BestCompression)
		if err != nil {
			return "", err
		}
		if _, err := w.Write(data); err != nil {
			return "", err
		}
		if err := w.Close(); err != nil {
			return "", err
		}
		if buf.Len() < len(data)-1 {
			return "." + base64.RawURLEncoding.EncodeToString(buf.Bytes()), nil
		}
	}
	return base64.RawURLEncoding.EncodeToString(data), nil
}

func decodeObject(body string, dest any) error {
	raw := body
	compressed := strings.HasPrefix(raw, ".")
	if compressed {
		raw = raw[1:]
	}
	data, err := base64.RawURLEncoding.DecodeString(raw)
	if err != nil {
		return errBad
	}
	if compressed {
		r, err := zlib.NewReader(bytes.NewReader(data))
		if err != nil {
			return errBad
		}
		data, err = io.ReadAll(r)
		_ = r.Close()
		if err != nil {
			return errBad
		}
	}
	if err := json.Unmarshal(data, dest); err != nil {
		return errBad
	}
	return nil
}

func unsign(key, salt, signed string) (string, error) {
	idx := strings.LastIndex(signed, sep)
	if idx < 0 {
		return "", errBad
	}
	body, sig := signed[:idx], signed[idx+1:]
	want := signature(salt, body, key)
	if subtle.ConstantTimeCompare([]byte(sig), []byte(want)) != 1 {
		return "", errBad
	}
	return body, nil
}

func signature(salt, value, key string) string {
	sum := sha256.Sum256([]byte(salt + "signer" + key))
	mac := hmac.New(sha256.New, sum[:])
	_, _ = mac.Write([]byte(value))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func b62Encode(n int64) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b []byte
	for n > 0 {
		b = append(b, base62Alphabet[n%62])
		n /= 62
	}
	// reverse
	for i, j := 0, len(b)-1; i < j; i, j = i+1, j-1 {
		b[i], b[j] = b[j], b[i]
	}
	if neg {
		return "-" + string(b)
	}
	return string(b)
}

func b62Decode(s string) (int64, error) {
	if s == "" || s == "-" {
		return 0, errBad
	}
	neg := s[0] == '-'
	if neg {
		s = s[1:]
	}
	var n int64
	for _, r := range s {
		i := strings.IndexRune(base62Alphabet, r)
		if i < 0 {
			return 0, errBad
		}
		n = n*62 + int64(i)
	}
	if neg {
		n = -n
	}
	return n, nil
}

var errBad = errors.New("签名对不上")
