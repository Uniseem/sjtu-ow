package fonts

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

var blockedNetworks = []netip.Prefix{
	netip.MustParsePrefix("0.0.0.0/8"), netip.MustParsePrefix("10.0.0.0/8"), netip.MustParsePrefix("100.64.0.0/10"),
	netip.MustParsePrefix("127.0.0.0/8"), netip.MustParsePrefix("169.254.0.0/16"), netip.MustParsePrefix("172.16.0.0/12"),
	netip.MustParsePrefix("192.0.0.0/24"), netip.MustParsePrefix("192.0.2.0/24"), netip.MustParsePrefix("192.168.0.0/16"),
	netip.MustParsePrefix("198.18.0.0/15"), netip.MustParsePrefix("198.51.100.0/24"), netip.MustParsePrefix("203.0.113.0/24"),
	netip.MustParsePrefix("224.0.0.0/4"), netip.MustParsePrefix("240.0.0.0/4"), netip.MustParsePrefix("::/128"),
	netip.MustParsePrefix("::1/128"), netip.MustParsePrefix("fc00::/7"), netip.MustParsePrefix("fe80::/10"),
	netip.MustParsePrefix("ff00::/8"), netip.MustParsePrefix("2001:db8::/32"),
}

func publicAddress(ip netip.Addr) bool {
	ip = ip.Unmap()
	if !ip.IsGlobalUnicast() || ip.IsPrivate() || ip.IsLoopback() || ip.IsLinkLocalUnicast() {
		return false
	}
	for _, prefix := range blockedNetworks {
		if prefix.Contains(ip) {
			return false
		}
	}
	return true
}
func allowedGoogleURL(raw, host string) (*url.URL, error) {
	value, err := url.Parse(raw)
	if err != nil || value.Scheme != "https" || value.Hostname() != host || value.User != nil || (value.Port() != "" && value.Port() != "443") || value.Fragment != "" {
		return nil, api.Invalid("字体下载地址不可用。")
	}
	if host != "fonts.googleapis.com" && host != "fonts.gstatic.com" {
		return nil, api.Invalid("字体下载来源不允许。")
	}
	return value, nil
}
func fontHTTPClient() *http.Client {
	dialer := &net.Dialer{Timeout: 15 * time.Second, KeepAlive: 30 * time.Second}
	transport := &http.Transport{
		Proxy: nil, TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12}, ForceAttemptHTTP2: true,
		DialContext: func(ctx context.Context, network, address string) (net.Conn, error) {
			host, port, err := net.SplitHostPort(address)
			if err != nil {
				return nil, err
			}
			if (host != "fonts.googleapis.com" && host != "fonts.gstatic.com") || port != "443" {
				return nil, fmt.Errorf("字体下载来源不允许")
			}
			ips, err := net.DefaultResolver.LookupNetIP(ctx, "ip", host)
			if err != nil {
				return nil, err
			}
			if len(ips) == 0 {
				return nil, fmt.Errorf("字体下载地址没有解析结果")
			}
			// Reject an answer set containing any private address; then connect to exactly
			// the checked address, retaining the original host for TLS verification.
			for _, ip := range ips {
				if !publicAddress(ip) {
					return nil, fmt.Errorf("字体下载地址解析到非公网地址")
				}
			}
			var last error
			for _, ip := range ips {
				connection, err := dialer.DialContext(ctx, network, net.JoinHostPort(ip.String(), port))
				if err == nil {
					return connection, nil
				}
				last = err
			}
			return nil, last
		},
	}
	return &http.Client{Timeout: 30 * time.Second, Transport: transport, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return fmt.Errorf("字体下载不接受重定向") }}
}
func fetchGoogle(ctx context.Context, client *http.Client, raw, host string, max int64) ([]byte, error) {
	value, err := allowedGoogleURL(raw, host)
	if err != nil {
		return nil, err
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, value.String(), nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("User-Agent", "Mozilla/5.0 AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36")
	response, err := client.Do(request)
	if err != nil {
		return nil, api.Invalid("字体下载失败，请检查服务器网络后重试。")
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return nil, api.Invalid(fmt.Sprintf("字体下载失败：HTTP %d。", response.StatusCode))
	}
	if response.ContentLength > max {
		return nil, api.Invalid("字体下载文件超过大小上限。")
	}
	bytes, err := io.ReadAll(io.LimitReader(response.Body, max+1))
	if err != nil {
		return nil, api.Invalid("读取字体下载内容失败。")
	}
	if len(bytes) == 0 || int64(len(bytes)) > max {
		return nil, api.Invalid("字体下载文件大小不正确。")
	}
	return bytes, nil
}

var familyPattern = regexp.MustCompile(`^[\pL\pN _-]{1,120}$`)
var facePattern = regexp.MustCompile(`(?s)@font-face\s*\{([^}]+)\}`)
var srcPattern = regexp.MustCompile(`url\(\s*['"]?([^'"\s)]+)['"]?\s*\)`)

func declaration(body, name string) string {
	expression := regexp.MustCompile(`(?i)(?:^|;)\s*` + regexp.QuoteMeta(name) + `\s*:\s*([^;]+)`)
	match := expression.FindStringSubmatch(body)
	if len(match) < 2 {
		return ""
	}
	return strings.TrimSpace(match[1])
}
func prepareGoogle(ctx context.Context, family string, weights []int, client *http.Client) (preparedFont, error) {
	family = strings.TrimSpace(family)
	out := preparedFont{source: "google", sourceRef: family, data: map[string][]byte{}}
	if !familyPattern.MatchString(family) {
		return out, api.InvalidFields(map[string][]string{"family": {"请输入有效的 Google Fonts 家族名称。"}})
	}
	if len(weights) == 0 {
		weights = []int{400, 700}
	}
	unique := map[int]bool{}
	for _, weight := range weights {
		if !validWeight(weight) {
			return out, api.InvalidFields(map[string][]string{"weights": {"字重必须为100至900的整百数。"}})
		}
		unique[weight] = true
	}
	weights = []int{}
	for weight := range unique {
		weights = append(weights, weight)
	}
	sort.Ints(weights)
	axis := []string{}
	for _, weight := range weights {
		axis = append(axis, strconv.Itoa(weight))
	}
	query := url.Values{"family": {family + ":wght@" + strings.Join(axis, ";")}, "display": {"swap"}}
	if client == nil {
		client = fontHTTPClient()
		defer client.CloseIdleConnections()
	}
	css, err := fetchGoogle(ctx, client, "https://fonts.googleapis.com/css2?"+query.Encode(), "fonts.googleapis.com", 2<<20)
	if err != nil {
		return out, err
	}
	out.manifest = Manifest{Version: 1, Family: family, DisplayName: family, License: "Google Fonts 开源字体；添加人已确认允许本站网页嵌入。", LicenseConfirmed: true, Faces: []Face{}}
	faces := map[string]int{}
	var total int
	count := 0
	for _, match := range facePattern.FindAllStringSubmatch(string(css), -1) {
		body := match[1]
		source := declaration(body, "src")
		parsed := srcPattern.FindStringSubmatch(source)
		if len(parsed) < 2 || !strings.Contains(source, "woff2") {
			return out, api.Invalid("Google Fonts 返回了不支持的字体格式。")
		}
		style := declaration(body, "font-style")
		if style == "" {
			style = "normal"
		}
		weight, err := strconv.Atoi(declaration(body, "font-weight"))
		if err != nil || !unique[weight] || style != "normal" {
			continue
		}
		unicodeRange := declaration(body, "unicode-range")
		if !validUnicodeRange(unicodeRange) {
			return out, api.Invalid("Google Fonts 返回了不正确的 unicode-range。")
		}
		count++
		if count > MaxSlices {
			return out, api.Invalid("Google Fonts 分片数量超过上限。")
		}
		bytes, err := fetchGoogle(ctx, client, parsed[1], "fonts.gstatic.com", MaxSliceBytes)
		if err != nil {
			return out, err
		}
		if err := validateWOFF2(bytes); err != nil {
			return out, err
		}
		total += len(bytes)
		if total > MaxPackageBytes {
			return out, api.Invalid("Google Fonts 字体总大小超过64MB。")
		}
		hash := digest(bytes)
		key := fmt.Sprintf("%d/%s", weight, style)
		index, exists := faces[key]
		if !exists {
			index = len(out.manifest.Faces)
			faces[key] = index
			out.manifest.Faces = append(out.manifest.Faces, Face{Weight: weight, Style: style, Slices: []Slice{}})
		}
		face := &out.manifest.Faces[index]
		face.Slices = append(face.Slices, Slice{Path: "fonts/objects/" + hash + ".woff2", UnicodeRange: unicodeRange, SHA256: hash, Bytes: int64(len(bytes))})
		face.Bytes += int64(len(bytes))
		out.data[hash] = bytes
	}
	if len(out.manifest.Faces) != len(weights) {
		return out, api.Invalid("Google Fonts 没有这个字体，或者它没有所选字重。")
	}
	return out, nil
}
