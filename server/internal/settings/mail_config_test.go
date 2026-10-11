package settings

import (
	"context"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/crypto"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

func TestMailConfigReadsSavedChangesForEachDelivery(t *testing.T) {
	e := newEditorEnv(t)
	fallback := mail.SMTP{Host: "bootstrap.example.test", FromAddr: "bootstrap@example.test", Password: "bootstrap-only", Allowlist: []string{"receiver@example.test"}, Timeout: 3 * time.Second}
	initial, err := e.service.MailConfig(context.Background(), fallback)
	if err != nil || initial.Host != fallback.Host {
		t.Fatalf("bootstrap configuration: %+v %v", initial, err)
	}
	encrypted, err := crypto.Encrypt(editorFieldKey, "virtual-saved-password")
	if err != nil {
		t.Fatal(err)
	}
	e.exec(`UPDATE site_settings SET smtp_host='first.example.test',smtp_port=2525,smtp_security='tls',from_address='first@example.test',smtp_password=? WHERE id=1`, encrypted)
	saved, err := e.service.MailConfig(context.Background(), fallback)
	if err != nil || saved.Host != "first.example.test" || saved.Password != "virtual-saved-password" || saved.Security != "starttls" || saved.Timeout != fallback.Timeout || len(saved.Allowlist) != 1 {
		t.Fatalf("saved configuration: host=%s security=%s %v", saved.Host, saved.Security, err)
	}
	e.exec(`UPDATE site_settings SET smtp_host='second.example.test',smtp_security='none',smtp_password='' WHERE id=1`)
	changed, err := e.service.MailConfig(context.Background(), fallback)
	if err != nil || changed.Host != "second.example.test" || changed.Security != "plain" || changed.Password != "" {
		t.Fatalf("delivery did not reread or used bootstrap credential: host=%s %v", changed.Host, err)
	}
}

func TestMailConfigDoesNotFallbackAfterSavedConfigurationOrDecryptFailure(t *testing.T) {
	e := newEditorEnv(t)
	fallback := mail.SMTP{Host: "bootstrap.example.test", FromAddr: "bootstrap@example.test"}
	e.exec(`UPDATE site_settings SET from_address='saved@example.test',smtp_host='' WHERE id=1`)
	partial, err := e.service.MailConfig(context.Background(), fallback)
	if err != nil || partial.Host != "" || partial.FromAddr != "saved@example.test" {
		t.Fatal("incomplete saved configuration silently selected bootstrap")
	}
	e.exec(`UPDATE site_settings SET smtp_password='invalid-ciphertext' WHERE id=1`)
	_, err = e.service.MailConfig(context.Background(), fallback)
	if err == nil {
		t.Fatal("corrupt credential accepted")
	}
	if err.Error() != "无法解密已保存的 SMTP 密码，请重新保存密钥。" {
		t.Fatalf("unsafe decrypt error: %v", err)
	}
}
