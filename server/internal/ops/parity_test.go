package ops

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

// 契约 R015, R073–R079, R061–R072 对拍与割接兼容性验证。
func TestParitySignaturesAndPasswords(t *testing.T) {
	ctx := context.Background()
	opts := ParityOptions{
		SigningKey:      "test-secret-key-12345",
		CheckSignatures: true,
		CheckPasswords:  true,
		CheckArticles:   true,
	}
	checker := NewParityChecker(opts, nil)
	res, err := checker.Run(ctx)
	if err != nil {
		t.Fatalf("checker.Run 错误: %v", err)
	}

	// 1. 签名兼容性
	if !res.Signatures.Passed {
		t.Fatalf("Signatures 未通过: %+v", res.Signatures)
	}
	if !res.Signatures.CalendarOK || !res.Signatures.UnsubscribeOK {
		t.Errorf("签名细节未通过: %+v", res.Signatures)
	}

	// 2. 密码兼容性
	if !res.Passwords.Passed {
		t.Fatalf("Passwords 未通过: %+v", res.Passwords)
	}
	if !res.Passwords.Argon2idOK || !res.Passwords.PBKDF2OK || !res.Passwords.RehashOK {
		t.Errorf("密码哈希兼容细节未通过: %+v", res.Passwords)
	}

	// 3. 文章渲染兼容性
	if !res.Articles.Passed {
		t.Fatalf("Articles 未通过: %+v", res.Articles)
	}
	if res.Articles.SampledCount == 0 {
		t.Errorf("抽样文章数量为 0")
	}

	// 4. 报告与 JSON 序列化
	report := res.FormatReport()
	if report == "" {
		t.Errorf("FormatReport 输出为空")
	}
	jsonStr, err := res.ToJSON()
	if err != nil || jsonStr == "" {
		t.Errorf("ToJSON 失败: %v", err)
	}
}

func TestParityRoutesWithServer(t *testing.T) {
	ctx := context.Background()

	// 模拟站点服务器
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("<!DOCTYPE html><html><head><title>SJTU-OW 上海交通大学守望先锋</title></head><body><h1>首页</h1></body></html>"))
	}))
	defer ts.Close()

	opts := ParityOptions{
		NewBaseURL:  ts.URL,
		CheckRoutes: true,
	}
	checker := NewParityChecker(opts, nil)
	res, err := checker.Run(ctx)
	if err != nil {
		t.Fatalf("checker.Run 错误: %v", err)
	}

	if len(res.Routes) == 0 {
		t.Fatalf("未检查任何路由")
	}
	for _, r := range res.Routes {
		if !r.Passed {
			t.Errorf("路由 %s 未通过: %+v", r.Path, r)
		}
		if r.NewStatus != http.StatusOK {
			t.Errorf("路由 %s 状态码不是 200: %d", r.Path, r.NewStatus)
		}
	}
}
