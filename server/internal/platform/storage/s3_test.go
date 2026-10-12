package storage

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net/http"
	"net/url"
	"reflect"
	"strings"
	"testing"
	"time"
)

type storageTestTransport func(*http.Request) (*http.Response, error)

func (f storageTestTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	return f(request)
}

func storageTestResponse(request *http.Request, status int, body string) *http.Response {
	return &http.Response{StatusCode: status, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(body)), Request: request}
}

func storageTestConfig() Config {
	return Config{Endpoint: "https://storage.example.invalid", Region: "auto", Bucket: "sjtu-backups", AccessKeyID: "test-access-id", SecretAccessKey: "test-secret-not-production", Prefix: "this-site/backups"}
}

func storageTestClient(t *testing.T, transport http.RoundTripper) *Client {
	t.Helper()
	client, err := New(storageTestConfig(), transport)
	if err != nil {
		t.Fatal(err)
	}
	return client
}

// These are AWS's published public example credentials and signatures, not
// project credentials. Independent vectors: "GET Bucket Lifecycle" and
// "Get Bucket (List Objects)" at the official AWS S3 SigV4 reference:
// https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sig-v4-header-based-auth.html
func TestSignMatchesPublishedAWSExamples(t *testing.T) {
	config := Config{Endpoint: "https://examplebucket.s3.amazonaws.com", Region: "us-east-1", Bucket: "examplebucket", AccessKeyID: "AKIAIOSFODNN7EXAMPLE", SecretAccessKey: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"}
	client, err := New(config, nil)
	if err != nil {
		t.Fatal(err)
	}
	client.now = func() time.Time { return time.Date(2013, 5, 24, 0, 0, 0, 0, time.UTC) }
	const emptyDigest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
	for _, example := range []struct{ name, query, signature string }{
		{"lifecycle", "lifecycle=", "fea454ca298b7da1c68078a5d1bdbfbbe0d65c699e0f91ac7a200a0136783543"},
		{"list objects", "max-keys=2&prefix=J", "34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7"},
	} {
		t.Run(example.name, func(t *testing.T) {
			request, err := http.NewRequest(http.MethodGet, config.Endpoint+"/?"+example.query, nil)
			if err != nil {
				t.Fatal(err)
			}
			client.sign(request, emptyDigest)
			if request.Header.Get("x-amz-date") != "20130524T000000Z" {
				t.Fatal("incorrect fixed signing timestamp")
			}
			if request.Header.Get("x-amz-content-sha256") != emptyDigest {
				t.Fatal("empty payload digest changed")
			}
			want := "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature=" + example.signature
			if got := request.Header.Get("Authorization"); got != want {
				t.Fatalf("signature does not match official %s vector: %s", example.name, got)
			}
		})
	}
}

func TestURIAndQueryEncodingUseLiteralUTF8Bytes(t *testing.T) {
	if got := uriEncode("社团/备份 +%.enc", true); got != "%E7%A4%BE%E5%9B%A2/%E5%A4%87%E4%BB%BD%20%2B%25.enc" {
		t.Fatalf("object path bytes changed: %s", got)
	}
	if got := uriEncode("a/b", false); got != "a%2Fb" {
		t.Fatalf("query slash remained unescaped: %s", got)
	}
	query := url.Values{"prefix": {"目录/ a+b"}, "x": {"z", "a"}, "empty": {""}, "token": {"a/b=+%"}}
	const want = "empty=&prefix=%E7%9B%AE%E5%BD%95%2F%20a%2Bb&token=a%2Fb%3D%2B%25&x=a&x=z"
	if got := canonicalQuery(query); got != want {
		t.Fatalf("canonical query differs from byte literal: %s", got)
	}
}

func TestRequestsPreserveS3ObjectPathWithoutFilesystemNormalization(t *testing.T) {
	var seen *http.Request
	client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
		seen = request
		return storageTestResponse(request, 200, ""), nil
	}))
	if err := client.Put(context.Background(), "a/./b//../%2F +雪", []byte("exact bytes")); err != nil {
		t.Fatal(err)
	}
	if seen == nil {
		t.Fatal("PUT was not performed")
	}
	const want = "/sjtu-backups/a/./b//../%252F%20%2B%E9%9B%AA"
	if got := seen.URL.EscapedPath(); got != want {
		t.Fatalf("object identity was normalized: %s", got)
	}
	if seen.ContentLength != int64(len("exact bytes")) {
		t.Fatal("payload size does not match bytes")
	}
	if !strings.Contains(seen.Header.Get("Authorization"), "/auto/s3/aws4_request") {
		t.Fatal("configured S3 region not signed")
	}
}

func TestProbeActuallyWritesReadsAndDeletesSameRandomObject(t *testing.T) {
	methods, keys := []string{}, []string{}
	var stored []byte
	client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
		methods = append(methods, request.Method)
		keys = append(keys, request.URL.Path)
		switch request.Method {
		case http.MethodPut:
			var err error
			stored, err = io.ReadAll(request.Body)
			if err != nil {
				return nil, err
			}
			return storageTestResponse(request, 200, ""), nil
		case http.MethodGet:
			return storageTestResponse(request, 200, string(stored)), nil
		case http.MethodDelete:
			return storageTestResponse(request, 204, ""), nil
		default:
			return nil, errors.New("unexpected request")
		}
	}))
	if err := client.Probe(context.Background()); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(methods, []string{"PUT", "GET", "DELETE"}) {
		t.Fatalf("probe did not verify write/read/delete: %v", methods)
	}
	if len(keys) != 3 || keys[0] != keys[1] || keys[1] != keys[2] {
		t.Fatalf("probe used different object identities: %v", keys)
	}
	if !strings.HasPrefix(keys[0], "/sjtu-backups/this-site/backups/.sjtuow-storage-test-") {
		t.Fatalf("probe escaped site's prefix: %s", keys[0])
	}
	if strings.HasSuffix(keys[0], ".tar.gz.enc") || len(stored) == 0 {
		t.Fatal("probe used a backup object or empty unverified data")
	}
}

func TestProbeDeletesAfterReadFailureMismatchAndCancellation(t *testing.T) {
	for _, mode := range []string{"get fails", "bytes mismatch", "caller cancels"} {
		t.Run(mode, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			methods := []string{}
			deleted := false
			client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
				methods = append(methods, request.Method)
				switch request.Method {
				case http.MethodPut:
					return storageTestResponse(request, 200, ""), nil
				case http.MethodGet:
					if mode == "caller cancels" {
						cancel()
						return nil, ctx.Err()
					}
					if mode == "get fails" {
						return storageTestResponse(request, 503, "<Error><Code>Unavailable</Code><Message>private remote details</Message></Error>"), nil
					}
					return storageTestResponse(request, 200, "wrong payload"), nil
				case http.MethodDelete:
					if request.Context().Err() != nil {
						t.Fatal("cleanup inherited caller cancellation")
					}
					if _, ok := request.Context().Deadline(); !ok {
						t.Fatal("cleanup has no bounded timeout")
					}
					deleted = true
					return storageTestResponse(request, 204, ""), nil
				}
				return nil, errors.New("unexpected request")
			}))
			if err := client.Probe(ctx); err == nil {
				t.Fatal("probe reported success after failed verification")
			}
			if !deleted || !reflect.DeepEqual(methods, []string{"PUT", "GET", "DELETE"}) {
				t.Fatalf("verification failure left remote object behind: %v", methods)
			}
		})
	}
}

func TestProbeDeleteFailureIsReportedEvenWhenReadSucceeded(t *testing.T) {
	var stored []byte
	client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
		switch request.Method {
		case http.MethodPut:
			stored, _ = io.ReadAll(request.Body)
			return storageTestResponse(request, 200, ""), nil
		case http.MethodGet:
			return storageTestResponse(request, 200, string(stored)), nil
		case http.MethodDelete:
			return storageTestResponse(request, 403, "<Error><Code>AccessDenied</Code></Error>"), nil
		}
		return nil, errors.New("unexpected request")
	}))
	if err := client.Probe(context.Background()); err == nil || !strings.Contains(err.Error(), "删除失败") {
		t.Fatalf("cleanup failure disappeared: %v", err)
	}
}

func TestRemoteFailureAndRedirectNeverLeakProviderBody(t *testing.T) {
	for _, status := range []int{400, 403, 500, 307} {
		t.Run(http.StatusText(status), func(t *testing.T) {
			calls := 0
			const secret = "provider-private-secret-and-user-address@example.invalid"
			client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
				calls++
				response := storageTestResponse(request, status, "<Error><Code>AccessDenied</Code><Message>"+secret+"</Message><RequestId>private-request-id</RequestId></Error>")
				response.Header.Set("Location", "https://credential-leak.invalid/collect")
				return response, nil
			}))
			_, err := client.Get(context.Background(), "private-object", 100)
			var remote *RemoteError
			if !errors.As(err, &remote) || remote.Status != status {
				t.Fatalf("non-2xx accepted or lost status: %v", err)
			}
			if calls != 1 {
				t.Fatalf("signed request followed redirect: %d requests", calls)
			}
			for _, private := range []string{secret, "private-request-id", "credential-leak.invalid", storageTestConfig().SecretAccessKey} {
				if strings.Contains(err.Error(), private) {
					t.Fatalf("private provider content entered error: %s", err)
				}
			}
		})
	}
}

func TestProviderCannotEchoSecretsThroughSafeLookingErrorCode(t *testing.T) {
	for _, secret := range []string{"AsciiSecret123456", "test-access-id", "test-secret-not-production"} {
		t.Run(secret, func(t *testing.T) {
			client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
				return storageTestResponse(request, 403, "<Error><Code>"+secret+"</Code></Error>"), nil
			}))
			_, err := client.Get(context.Background(), "private-object", 100)
			if err == nil || strings.Contains(err.Error(), secret) {
				t.Fatalf("provider Code leaked its echo: %v", err)
			}
			var remote *RemoteError
			if !errors.As(err, &remote) || remote.Status != 403 || remote.Code != "" {
				t.Fatalf("unknown code was exposed: %v", err)
			}
		})
	}
}

func TestPutFileSendsExactlyHashedBytesAndRejectsWrongSize(t *testing.T) {
	calls := 0
	data := []byte("encrypted binary backup\x00\x80\xff")
	client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
		calls++
		read, err := io.ReadAll(request.Body)
		if err != nil {
			return nil, err
		}
		digest := sha256.Sum256(data)
		if request.Header.Get("x-amz-content-sha256") != hex.EncodeToString(digest[:]) {
			t.Fatal("signature hash is not the actual encrypted file")
		}
		if !bytes.Equal(read, data) || request.ContentLength != int64(len(data)) {
			t.Fatal("uploaded bytes differed from encrypted file")
		}
		return storageTestResponse(request, 200, ""), nil
	}))
	if err := client.PutFile(context.Background(), "backup.enc", bytes.NewReader(data), int64(len(data))); err != nil {
		t.Fatal(err)
	}
	if err := client.PutFile(context.Background(), "backup.enc", bytes.NewReader(data), int64(len(data)+1)); err == nil {
		t.Fatal("truncated file uploaded")
	}
	if calls != 1 {
		t.Fatal("wrong size still issued a write")
	}
}

func TestStorageConfigurationRejectsCredentialRedirectAndUnsafePrefixes(t *testing.T) {
	for _, endpoint := range []string{"http://storage.invalid", "https://user:password@storage.invalid", "https://storage.invalid/path", "https://storage.invalid?token=private", "https://storage.invalid#fragment"} {
		config := storageTestConfig()
		config.Endpoint = endpoint
		if _, err := New(config, nil); err == nil {
			t.Fatalf("unsafe endpoint accepted: %s", endpoint)
		}
	}
	for _, prefix := range []string{"site/../other", "site/./backup", "site\\other", "site\x00private"} {
		if _, err := NormalizePrefix(prefix); err == nil {
			t.Fatalf("unsafe prefix accepted: %q", prefix)
		}
	}
}

func TestFailedProbePutDoesNotReadOrDeleteUncreatedObject(t *testing.T) {
	methods := []string{}
	client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
		methods = append(methods, request.Method)
		return storageTestResponse(request, 403, "<Error><Code>AccessDenied</Code></Error>"), nil
	}))
	if err := client.Probe(context.Background()); err == nil {
		t.Fatal("failed PUT reported successful storage probe")
	}
	if !reflect.DeepEqual(methods, []string{"PUT"}) {
		t.Fatalf("probe read/deleted after rejected PUT: %v", methods)
	}
}

func TestGetRejectsOversizedSuccessfulBodyWithoutReturningPartialData(t *testing.T) {
	client := storageTestClient(t, storageTestTransport(func(request *http.Request) (*http.Response, error) {
		return storageTestResponse(request, 200, "0123456789"), nil
	}))
	data, err := client.Get(context.Background(), "private-object", 4)
	if err == nil || len(data) != 0 {
		t.Fatalf("oversized object returned truncated success: %q %v", data, err)
	}
}
