// Package storage implements the small path-style S3 surface used by backup
// and the administrator's write/read/delete probe. Signature V4 follows AWS:
// https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sig-v4-header-based-auth.html
package storage

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"time"
)

const responseLimit = 1024 * 1024

var bucketPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$`)
var regionPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,32}$`)

type Config struct {
	Endpoint        string
	Region          string
	Bucket          string
	AccessKeyID     string
	SecretAccessKey string
	Prefix          string
}
type Client struct {
	config   Config
	endpoint *url.URL
	http     *http.Client
	now      func() time.Time
}

// A caller may inject a transport for a dedicated test host. Production
// construction always requires HTTPS and refuses credential-bearing URLs.
func New(config Config, transport http.RoundTripper) (*Client, error) {
	endpoint, err := url.Parse(strings.TrimSpace(config.Endpoint))
	if err != nil || endpoint.Scheme != "https" || endpoint.Hostname() == "" || endpoint.User != nil || endpoint.RawQuery != "" || endpoint.Fragment != "" {
		return nil, errors.New("对象存储地址必须是有效的 HTTPS 地址。")
	}
	if endpoint.Path != "" && endpoint.Path != "/" {
		return nil, errors.New("对象存储地址不能带路径，请把目录填在路径前缀中。")
	}
	if !bucketPattern.MatchString(config.Bucket) {
		return nil, errors.New("存储桶名称无效。")
	}
	if config.Region == "" {
		config.Region = "auto"
	}
	if !regionPattern.MatchString(config.Region) {
		return nil, errors.New("对象存储区域无效。")
	}
	if config.AccessKeyID == "" || config.SecretAccessKey == "" {
		return nil, errors.New("请先保存对象存储的访问密钥。")
	}
	if strings.ContainsAny(config.AccessKeyID+config.SecretAccessKey, "\r\n") {
		return nil, errors.New("访问密钥包含无效字符。")
	}
	prefix, err := NormalizePrefix(config.Prefix)
	if err != nil {
		return nil, err
	}
	config.Prefix = prefix
	if transport == nil {
		transport = &http.Transport{Proxy: http.ProxyFromEnvironment, MaxIdleConns: 2, IdleConnTimeout: 30 * time.Second, TLSHandshakeTimeout: 10 * time.Second, ResponseHeaderTimeout: 30 * time.Second}
	}
	return &Client{config: config, endpoint: endpoint, http: &http.Client{Transport: transport, Timeout: 2 * time.Minute, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse }}, now: time.Now}, nil
}
func NormalizePrefix(prefix string) (string, error) {
	prefix = strings.TrimSpace(strings.TrimPrefix(prefix, "/"))
	if len(prefix) > 128 || strings.ContainsAny(prefix, "\\\r\n\x00") {
		return "", errors.New("路径前缀无效。")
	}
	for _, part := range strings.Split(prefix, "/") {
		if part == "." || part == ".." {
			return "", errors.New("路径前缀不能包含上级目录。")
		}
	}
	if prefix != "" && !strings.HasSuffix(prefix, "/") {
		prefix += "/"
	}
	return prefix, nil
}

func hash(data []byte) string { value := sha256.Sum256(data); return hex.EncodeToString(value[:]) }
func mac(key []byte, value string) []byte {
	h := hmac.New(sha256.New, key)
	_, _ = h.Write([]byte(value))
	return h.Sum(nil)
}
func uriEncode(value string, slash bool) string {
	const digits = "0123456789ABCDEF"
	var result strings.Builder
	for i := 0; i < len(value); i++ {
		c := value[i]
		if c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c >= '0' && c <= '9' || strings.ContainsRune("-_.~", rune(c)) || slash && c == '/' {
			result.WriteByte(c)
		} else {
			result.WriteByte('%')
			result.WriteByte(digits[c>>4])
			result.WriteByte(digits[c&15])
		}
	}
	return result.String()
}
func canonicalQuery(values url.Values) string {
	pairs := []string{}
	for key, list := range values {
		for _, value := range list {
			pairs = append(pairs, uriEncode(key, false)+"="+uriEncode(value, false))
		}
	}
	sort.Strings(pairs)
	return strings.Join(pairs, "&")
}
func (c *Client) sign(request *http.Request, payload string) {
	now := c.now().UTC()
	day := now.Format("20060102")
	stamp := now.Format("20060102T150405Z")
	request.Header.Set("x-amz-date", stamp)
	request.Header.Set("x-amz-content-sha256", payload)
	headers := "host:" + request.URL.Host + "\nx-amz-content-sha256:" + payload + "\nx-amz-date:" + stamp + "\n"
	signed := "host;x-amz-content-sha256;x-amz-date"
	canonical := strings.Join([]string{request.Method, request.URL.EscapedPath(), request.URL.RawQuery, headers, signed, payload}, "\n")
	scope := day + "/" + c.config.Region + "/s3/aws4_request"
	toSign := "AWS4-HMAC-SHA256\n" + stamp + "\n" + scope + "\n" + hash([]byte(canonical))
	key := mac([]byte("AWS4"+c.config.SecretAccessKey), day)
	key = mac(key, c.config.Region)
	key = mac(key, "s3")
	key = mac(key, "aws4_request")
	signature := hex.EncodeToString(mac(key, toSign))
	request.Header.Set("Authorization", "AWS4-HMAC-SHA256 Credential="+c.config.AccessKeyID+"/"+scope+", SignedHeaders="+signed+", Signature="+signature)
}

// RemoteError contains a provider code and status, not the raw response or a
// signed request URL. Credentials and provider echo bodies stay out of logs.
type RemoteError struct {
	Status int
	Code   string
}

func (e *RemoteError) Error() string {
	if e.Code != "" {
		return fmt.Sprintf("对象存储返回 %d（%s）。", e.Status, e.Code)
	}
	return fmt.Sprintf("对象存储返回 %d。", e.Status)
}
func remoteError(response *http.Response) error {
	raw, _ := io.ReadAll(io.LimitReader(response.Body, 64*1024))
	var body struct {
		Code string `xml:"Code"`
	}
	_ = xml.Unmarshal(raw, &body)
	safe := regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)
	if !safe.MatchString(body.Code) {
		body.Code = ""
	}
	return &RemoteError{Status: response.StatusCode, Code: body.Code}
}
func (c *Client) request(ctx context.Context, method, key string, query url.Values, body io.Reader, size int64, payloadHash string) (*http.Response, error) {
	if strings.ContainsRune(key, 0) {
		return nil, errors.New("对象名称无效。")
	}
	address := *c.endpoint
	address.Path = "/" + c.config.Bucket
	if key != "" {
		address.Path += "/" + key
	}
	address.RawPath = uriEncode(address.Path, true)
	address.RawQuery = canonicalQuery(query)
	request, err := http.NewRequestWithContext(ctx, method, address.String(), body)
	if err != nil {
		return nil, errors.New("无法创建对象存储请求。")
	}
	request.ContentLength = size
	c.sign(request, payloadHash)
	response, err := c.http.Do(request)
	if err != nil {
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		return nil, errors.New("无法连接对象存储，请检查地址和网络。")
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		defer response.Body.Close()
		return nil, remoteError(response)
	}
	return response, nil
}
func (c *Client) Put(ctx context.Context, key string, data []byte) error {
	response, err := c.request(ctx, http.MethodPut, key, nil, bytes.NewReader(data), int64(len(data)), hash(data))
	if err != nil {
		return err
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, responseLimit))
	return nil
}

// PutFile hashes a seekable encrypted backup once and sends the exact bytes.
// The archive is never buffered in memory and plaintext never reaches S3.
func (c *Client) PutFile(ctx context.Context, key string, file io.ReadSeeker, size int64) error {
	if size < 0 {
		return errors.New("备份文件大小无效。")
	}
	digest := sha256.New()
	count, err := io.Copy(digest, file)
	if err != nil || count != size {
		return errors.New("无法完整读取备份文件。")
	}
	if _, err := file.Seek(0, io.SeekStart); err != nil {
		return err
	}
	response, err := c.request(ctx, http.MethodPut, key, nil, file, size, hex.EncodeToString(digest.Sum(nil)))
	if err != nil {
		return err
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, responseLimit))
	return nil
}
func (c *Client) Get(ctx context.Context, key string, limit int64) ([]byte, error) {
	response, err := c.request(ctx, http.MethodGet, key, nil, nil, 0, hash(nil))
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if limit < 1 {
		limit = responseLimit
	}
	data, err := io.ReadAll(io.LimitReader(response.Body, limit+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > limit {
		return nil, errors.New("对象存储响应过大。")
	}
	return data, nil
}
func (c *Client) Delete(ctx context.Context, key string) error {
	response, err := c.request(ctx, http.MethodDelete, key, nil, nil, 0, hash(nil))
	if err != nil {
		return err
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, responseLimit))
	return nil
}

type Object struct {
	Key          string    `xml:"Key"`
	LastModified time.Time `xml:"LastModified"`
	Size         int64     `xml:"Size"`
}
type ObjectPage struct {
	Items []Object
	Next  string
}

func (c *Client) List(ctx context.Context, prefix, token string) (ObjectPage, error) {
	query := url.Values{"list-type": {"2"}, "prefix": {prefix}, "max-keys": {"1000"}}
	if token != "" {
		query.Set("continuation-token", token)
	}
	response, err := c.request(ctx, http.MethodGet, "", query, nil, 0, hash(nil))
	if err != nil {
		return ObjectPage{}, err
	}
	defer response.Body.Close()
	var result struct {
		Items     []Object `xml:"Contents"`
		Next      string   `xml:"NextContinuationToken"`
		Truncated bool     `xml:"IsTruncated"`
	}
	raw, err := io.ReadAll(io.LimitReader(response.Body, 4*responseLimit+1))
	if err != nil {
		return ObjectPage{}, err
	}
	if len(raw) > 4*responseLimit {
		return ObjectPage{}, errors.New("对象列表响应过大。")
	}
	if err := xml.Unmarshal(raw, &result); err != nil {
		return ObjectPage{}, errors.New("对象存储列表格式无效。")
	}
	if result.Truncated && result.Next == "" {
		return ObjectPage{}, errors.New("对象存储分页标识缺失。")
	}
	return ObjectPage{Items: result.Items, Next: result.Next}, nil
}

// Probe uses a random non-backup object and always attempts deletion after a
// successful PUT, even if GET fails or the caller cancels the request.
func (c *Client) Probe(ctx context.Context) error {
	nonce := make([]byte, 16)
	if _, err := rand.Read(nonce); err != nil {
		return err
	}
	key := c.config.Prefix + ".sjtuow-storage-test-" + hex.EncodeToString(nonce)
	data := []byte("SJTU-OW object storage test " + hex.EncodeToString(nonce) + "\n")
	if err := c.Put(ctx, key, data); err != nil {
		return err
	}
	read, readErr := c.Get(ctx, key, 1024)
	cleanup, cancel := context.WithTimeout(context.WithoutCancel(ctx), 30*time.Second)
	defer cancel()
	deleteErr := c.Delete(cleanup, key)
	if deleteErr != nil {
		return fmt.Errorf("测试文件已写入，但删除失败：%w", deleteErr)
	}
	if readErr != nil {
		return readErr
	}
	if !bytes.Equal(read, data) {
		return errors.New("测试文件读取内容与写入内容不一致。")
	}
	return nil
}
