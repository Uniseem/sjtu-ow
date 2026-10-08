// Package crypto 是字段加密（12 号文档 5.11、现行站 core/crypto.py）。
// 钥匙是 SHA-256(FIELD_ENCRYPTION_KEY)，再按 Fernet 的规矩拆成签名钥匙和
// 加密钥匙。空串加密、解密都还是空串。
package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"time"
)

// Encrypt 把明文收成 Fernet 令牌。空串还是空串。
func Encrypt(fieldKey, plaintext string) (string, error) {
	if plaintext == "" {
		return "", nil
	}
	signing, enc, err := splitKey(fieldKey)
	if err != nil {
		return "", err
	}
	iv := make([]byte, aes.BlockSize)
	if _, err := rand.Read(iv); err != nil {
		return "", err
	}
	block, err := aes.NewCipher(enc)
	if err != nil {
		return "", err
	}
	padded := pkcs7Pad([]byte(plaintext), aes.BlockSize)
	ct := make([]byte, len(padded))
	cipher.NewCBCEncrypter(block, iv).CryptBlocks(ct, padded)

	buf := make([]byte, 1+8+aes.BlockSize+len(ct))
	buf[0] = 0x80
	binary.BigEndian.PutUint64(buf[1:9], uint64(time.Now().Unix()))
	copy(buf[9:25], iv)
	copy(buf[25:], ct)
	mac := hmac.New(sha256.New, signing)
	_, _ = mac.Write(buf)
	buf = append(buf, mac.Sum(nil)...)
	return base64.URLEncoding.EncodeToString(buf), nil
}

// Decrypt 解开 Fernet 令牌。空串还是空串。对不上钥匙或被改过就报错。
func Decrypt(fieldKey, token string) (string, error) {
	if token == "" {
		return "", nil
	}
	signing, enc, err := splitKey(fieldKey)
	if err != nil {
		return "", err
	}
	raw, err := base64.URLEncoding.DecodeString(token)
	if err != nil {
		return "", errBad
	}
	// 1 版本 + 8 时间 + 16 IV + 至少 16 密文 + 32 HMAC
	if len(raw) < 1+8+aes.BlockSize+aes.BlockSize+sha256.Size || raw[0] != 0x80 {
		return "", errBad
	}
	macStart := len(raw) - sha256.Size
	mac := hmac.New(sha256.New, signing)
	_, _ = mac.Write(raw[:macStart])
	if subtle.ConstantTimeCompare(mac.Sum(nil), raw[macStart:]) != 1 {
		return "", errBad
	}
	iv := raw[9:25]
	ct := raw[25:macStart]
	if len(ct)%aes.BlockSize != 0 {
		return "", errBad
	}
	block, err := aes.NewCipher(enc)
	if err != nil {
		return "", err
	}
	plain := make([]byte, len(ct))
	cipher.NewCBCDecrypter(block, iv).CryptBlocks(plain, ct)
	plain, err = pkcs7Unpad(plain, aes.BlockSize)
	if err != nil {
		return "", err
	}
	return string(plain), nil
}

func splitKey(fieldKey string) (signing, enc []byte, err error) {
	if fieldKey == "" {
		return nil, nil, errors.New("FIELD_ENCRYPTION_KEY 是空的")
	}
	sum := sha256.Sum256([]byte(fieldKey))
	return sum[:16], sum[16:], nil
}

func pkcs7Pad(b []byte, block int) []byte {
	n := block - len(b)%block
	out := make([]byte, len(b)+n)
	copy(out, b)
	for i := len(b); i < len(out); i++ {
		out[i] = byte(n)
	}
	return out
}

func pkcs7Unpad(b []byte, block int) ([]byte, error) {
	if len(b) == 0 || len(b)%block != 0 {
		return nil, errBad
	}
	n := int(b[len(b)-1])
	if n == 0 || n > block || n > len(b) {
		return nil, errBad
	}
	for _, c := range b[len(b)-n:] {
		if int(c) != n {
			return nil, errBad
		}
	}
	return b[:len(b)-n], nil
}

var errBad = errors.New("密文和当前的 FIELD_ENCRYPTION_KEY 对不上")
