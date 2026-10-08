package crypto

import (
	_ "embed"
	"encoding/json"
	"testing"
)

//go:embed testdata/golden.json
var goldenJSON []byte

// testdata/golden.json 是 cryptography.fernet 用 SHA-256(field_key) 打出来的。
func TestDecryptsCryptographyToken(t *testing.T) {
	var g struct {
		FieldKey  string `json:"field_key"`
		Plaintext string `json:"plaintext"`
		Token     string `json:"token"`
	}
	if err := json.Unmarshal(goldenJSON, &g); err != nil {
		t.Fatal(err)
	}
	got, err := Decrypt(g.FieldKey, g.Token)
	if err != nil || got != g.Plaintext {
		t.Fatalf("得到 %q err=%v", got, err)
	}
	if _, err := Decrypt("other-key", g.Token); err == nil {
		t.Fatal("另一把钥匙不应解开")
	}
}

func TestEncryptRoundTripAndEmpty(t *testing.T) {
	tok, err := Encrypt("field-key", "hello")
	if err != nil {
		t.Fatal(err)
	}
	got, err := Decrypt("field-key", tok)
	if err != nil || got != "hello" {
		t.Fatalf("得到 %q err=%v", got, err)
	}
	empty, err := Encrypt("field-key", "")
	if err != nil || empty != "" {
		t.Fatalf("空串应还是空串：%q %v", empty, err)
	}
	if got, err := Decrypt("field-key", ""); err != nil || got != "" {
		t.Fatalf("解密空串：%q %v", got, err)
	}
	if _, err := Encrypt("", "x"); err == nil {
		t.Fatal("没有钥匙不应加密")
	}
}
