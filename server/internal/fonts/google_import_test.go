package fonts

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"slices"
	"strings"
	"testing"
)

type googleFixtureTransport func(*http.Request) (*http.Response, error)

func (f googleFixtureTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	return f(request)
}

func TestGoogleImportKeepsSelectedWeightsAndDisplayName(t *testing.T) {
	for _, scenario := range []struct {
		name, displayName, wantName string
		weights, wantWeights        []int
	}{
		{"custom", "  站内显示字体  ", "站内显示字体", []int{800, 300, 800}, []int{300, 800}},
		{"defaults", "", "Fixture Sans", nil, []int{400, 700}},
	} {
		t.Run(scenario.name, func(t *testing.T) {
			env := newFontEnv(t)
			calls := 0
			env.service.googleClient = &http.Client{Transport: googleFixtureTransport(func(request *http.Request) (*http.Response, error) {
				calls++
				var content []byte
				switch request.URL.Hostname() {
				case "fonts.googleapis.com":
					axis := []string{}
					var css strings.Builder
					for _, weight := range scenario.wantWeights {
						axis = append(axis, fmt.Sprint(weight))
						fmt.Fprintf(&css, "@font-face {font-family:'Fixture Sans';font-style:normal;font-weight:%d;src:url(https://fonts.gstatic.com/fixture/%d.woff2) format('woff2');unicode-range:U+20-7E;}\n", weight, weight)
					}
					if got := request.URL.Query().Get("family"); got != "Fixture Sans:wght@"+strings.Join(axis, ";") {
						t.Fatalf("download requested %q, expected selected weights %v", got, scenario.wantWeights)
					}
					content = []byte(css.String())
				case "fonts.gstatic.com":
					content = woff2Envelope()
				default:
					t.Fatalf("unexpected download host %s", request.URL.Hostname())
				}
				return &http.Response{StatusCode: 200, Body: io.NopCloser(bytes.NewReader(content)), Header: http.Header{}, ContentLength: int64(len(content))}, nil
			})}
			result, err := env.service.importFont(env.ctx, ImportIn{Source: "google", Family: "Fixture Sans", DisplayName: scenario.displayName, Weights: scenario.weights, LicenseConfirmed: true})
			if err != nil {
				t.Fatal(err)
			}
			if result.Font.DisplayName != scenario.wantName || result.Font.Family != "Fixture Sans" || result.Font.SourceRef != "Fixture Sans" {
				t.Fatalf("font identity and display name: %+v", result.Font)
			}
			if !slices.Equal(result.Font.Weights, scenario.wantWeights) || len(result.Slices) != len(scenario.wantWeights) || calls != 1+len(scenario.wantWeights) {
				t.Fatalf("stored weights=%v faces=%d downloads=%d", result.Font.Weights, len(result.Slices), calls)
			}
			if result.Font.LicenseType != "open_source" || result.Font.LicenseNote != "Google Fonts 开源字体" {
				t.Fatalf("Google license projection: %+v", result.Font)
			}
			stored, err := readFont(env.ctx.Context, env.d.ReadPool(), result.Font.ID)
			if err != nil || stored.Font.DisplayName != scenario.wantName {
				t.Fatalf("persisted display name=%q error=%v", stored.Font.DisplayName, err)
			}
			_, err = env.service.importFont(env.ctx, ImportIn{Source: "google", Family: "Fixture Sans", DisplayName: strings.Repeat("字", 65), LicenseConfirmed: true})
			apiStatus(t, err, 422)
			if calls != 1+len(scenario.wantWeights) {
				t.Fatal("invalid display name reached the downloader")
			}
		})
	}
}
