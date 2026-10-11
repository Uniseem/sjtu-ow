package fonts

import (
	"net/netip"
	"testing"
)

func TestGoogleFontDownloadURLBoundary(t *testing.T) {
	cases := []struct {
		url, host string
		ok        bool
	}{
		{"https://fonts.googleapis.com/css2?family=Noto+Sans+SC", "fonts.googleapis.com", true},
		{"https://fonts.gstatic.com/s/notosanssc/v1/font.woff2", "fonts.gstatic.com", true},
		{"http://fonts.gstatic.com/s/font.woff2", "fonts.gstatic.com", false},
		{"https://fonts.gstatic.com.attacker.test/s/font.woff2", "fonts.gstatic.com", false},
		{"https://fonts.gstatic.com:8443/s/font.woff2", "fonts.gstatic.com", false},
		{"https://user:password@fonts.gstatic.com/s/font.woff2", "fonts.gstatic.com", false},
		{"https://fonts.gstatic.com/s/font.woff2#fragment", "fonts.gstatic.com", false},
		{"https://fonts.googleapis.com/css2?family=Noto", "fonts.gstatic.com", false},
		{"https://127.0.0.1/private", "fonts.gstatic.com", false},
	}
	for _, item := range cases {
		t.Run(item.url, func(t *testing.T) {
			_, err := allowedGoogleURL(item.url, item.host)
			if (err == nil) != item.ok {
				t.Fatalf("allowed=%v want=%v error=%v", err == nil, item.ok, err)
			}
		})
	}
}
func TestPinnedDownloaderRejectsAllNonPublicAddressClasses(t *testing.T) {
	cases := []struct {
		address string
		allowed bool
	}{
		{"8.8.8.8", true}, {"2606:4700:4700::1111", true},
		{"127.0.0.1", false}, {"10.4.5.6", false}, {"172.16.8.2", false}, {"192.168.0.9", false},
		{"169.254.169.254", false}, {"100.64.1.2", false}, {"0.0.0.0", false},
		{"198.18.1.2", false}, {"224.0.0.1", false}, {"240.0.0.1", false},
		{"192.0.2.1", false}, {"198.51.100.1", false}, {"203.0.113.1", false},
		{"::", false}, {"::1", false}, {"::ffff:127.0.0.1", false}, {"::ffff:10.0.0.1", false},
		{"fc00::1", false}, {"fe80::1", false}, {"ff02::1", false}, {"2001:db8::1", false},
	}
	for _, item := range cases {
		t.Run(item.address, func(t *testing.T) {
			actual := publicAddress(netip.MustParseAddr(item.address))
			if actual != item.allowed {
				t.Fatalf("public=%v want=%v", actual, item.allowed)
			}
		})
	}
}
