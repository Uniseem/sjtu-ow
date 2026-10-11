package mail

import (
	"bytes"
	"encoding/base64"
	"io"
	"mime"
	"mime/multipart"
	stdmail "net/mail"
	"strings"
	"testing"
	"time"
)

// Parse the SMTP bytes as a recipient would. Finding Content-Type somewhere
// in Raw is insufficient: it must be in the actual message headers.
func TestBuildHasParseableAlternativeRelatedMIME(t *testing.T) {
	letter := Letter{Subject: "邮箱验证码", Lead: "请验证邮箱。", Code: "001234", Reason: "注册账号。"}
	msg, err := Build(letter, Person{Address: "journey@example.test", Name: "测试成员"}, "SJTU-OW <site@example.test>", "http://127.0.0.1:45905", DefaultPrefix, time.Date(2026, 10, 11, 0, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	parsed, err := stdmail.ReadMessage(bytes.NewReader(msg.Raw))
	if err != nil {
		t.Fatal(err)
	}
	top, params, err := mime.ParseMediaType(parsed.Header.Get("Content-Type"))
	if err != nil || top != "multipart/alternative" || params["boundary"] == "" {
		t.Fatalf("top-level MIME header missing or invalid: %q (%v)", parsed.Header.Get("Content-Type"), err)
	}
	if msg.Header.Get("Content-Type") != parsed.Header.Get("Content-Type") {
		t.Fatal("Message.Header disagrees with SMTP headers")
	}
	alternatives := multipart.NewReader(parsed.Body, params["boundary"])
	plain, err := alternatives.NextPart()
	if err != nil || plain.Header.Get("Content-Type") != "text/plain; charset=utf-8" {
		t.Fatalf("first alternative must be plain text: %v", err)
	}
	text, err := io.ReadAll(plain) // NextPart decodes quoted-printable.
	if err != nil || !strings.Contains(string(text), "验证码：001234") || !strings.Contains(string(text), "测试成员，你好：") {
		t.Fatalf("plain text did not decode the exact code/greeting: %v", err)
	}
	related, err := alternatives.NextPart()
	if err != nil {
		t.Fatal(err)
	}
	media, relatedParams, err := mime.ParseMediaType(related.Header.Get("Content-Type"))
	if err != nil || media != "multipart/related" || relatedParams["boundary"] == "" {
		t.Fatalf("second alternative must contain HTML and pictures: %v", err)
	}
	parts := multipart.NewReader(related, relatedParams["boundary"])
	html, err := parts.NextPart()
	if err != nil || html.Header.Get("Content-Type") != "text/html; charset=utf-8" {
		t.Fatalf("related first part must be HTML: %v", err)
	}
	body, err := io.ReadAll(html)
	if err != nil || !strings.Contains(string(body), "001234") || !strings.Contains(string(body), "cid:ow-mark") || !strings.Contains(string(body), "cid:ow-horizon") {
		t.Fatalf("HTML did not decode code/inline picture references: %v", err)
	}
	for _, cid := range []string{"ow-mark", "ow-horizon"} {
		picture, err := parts.NextPart()
		if err != nil || picture.Header.Get("Content-ID") != "<"+cid+">" || picture.Header.Get("Content-Type") != "image/png" {
			t.Fatalf("missing inline picture %s: %v", cid, err)
		}
		pixels, err := io.ReadAll(base64.NewDecoder(base64.StdEncoding, picture))
		if err != nil || !bytes.Equal(pixels, Art()[cid]) {
			t.Fatalf("invalid inline PNG %s: %v", cid, err)
		}
	}
	if _, err := parts.NextPart(); err != io.EOF {
		t.Fatalf("unexpected related part: %v", err)
	}
	if _, err := alternatives.NextPart(); err != io.EOF {
		t.Fatalf("unexpected alternative: %v", err)
	}
}
