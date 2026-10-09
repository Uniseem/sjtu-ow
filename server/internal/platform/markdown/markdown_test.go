package markdown

import (
	"strings"
	"testing"
)

func TestMarkdownRules(t *testing.T) {
	siteURL := "https://sjtu.ow-shanghaiuniversity.com"

	// 规则 61: CommonMark + 表格 + 删除线 + 单换行即 <br> + HTML 不解析原样输出
	src1 := "第1行\n第2行\n\n<s>HTML标签</s>\n\n~~删除线~~\n\n| A | B |\n|---|---|\n| 1 | 2 |"
	html1, _, err := Render(src1, siteURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(html1, "第1行<br>\n第2行") {
		t.Errorf("单换行应为 <br>: %s", html1)
	}
	if !strings.Contains(html1, "&lt;s&gt;HTML标签&lt;/s&gt;") {
		t.Errorf("原始 HTML 应被转义: %s", html1)
	}
	if !strings.Contains(html1, "<s>删除线</s>") {
		t.Errorf("~~删除线~~ 应渲染为 <s>: %s", html1)
	}
	if !strings.Contains(html1, `<div class="c-prose__table"><table>`) {
		t.Errorf("表格应带滚动包裹: %s", html1)
	}

	// 规则 62: #/## 均为 h2，### 及以下为 h3
	src2 := "# 标题1\n## 标题2\n### 标题3\n#### 标题4"
	html2, _, err := Render(src2, siteURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(html2, "<h2>标题1</h2>") || !strings.Contains(html2, "<h2>标题2</h2>") {
		t.Errorf("#/## 应均为 h2: %s", html2)
	}
	if !strings.Contains(html2, "<h3>标题3</h3>") || !strings.Contains(html2, "<h3>标题4</h3>") {
		t.Errorf("###/#### 应均为 h3: %s", html2)
	}

	// 规则 63-65: 本站大图 figure + 外站图链接
	src3 := "![说明](/media/images/photo.webp)\n\n![外站](https://example.com/other.png)"
	html3, stats3, err := Render(src3, siteURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(html3, `<figure><img src="/media/images/photo.webp" alt="说明" loading="lazy"><figcaption>说明</figcaption></figure>`) {
		t.Errorf("单独成行的本站图片应为 figure + figcaption: %s", html3)
	}
	if stats3.Images != 1 {
		t.Errorf("本站图片应计入统计: %+v", stats3)
	}
	if !strings.Contains(html3, `<a href="https://example.com/other.png">外站</a>`) {
		t.Errorf("外站图片应降级为纯链接: %s", html3)
	}

	// 规则 66: B 站视频
	src4 := "https://www.bilibili.com/video/BV1xx411c7mD?p=2"
	html4, stats4, err := Render(src4, siteURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(html4, `<iframe src="https://player.bilibili.com/player.html?bvid=BV1xx411c7mD&amp;page=2" title="B 站视频"`) {
		t.Errorf("单独成行的 B 站视频应为播放器 iframe: %s", html4)
	}
	if stats4.Videos != 1 {
		t.Errorf("B 站视频应计入统计: %+v", stats4)
	}

	// 规则 68: 裸 URL 自动转链接
	src5 := "访问 https://sjtu.edu.cn 了解更多"
	html5, _, err := Render(src5, siteURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(html5, `<a href="https://sjtu.edu.cn">https://sjtu.edu.cn</a>`) {
		t.Errorf("裸 URL 应自动转链接: %s", html5)
	}

	// 规则 69: 引用块最后一行以「——」开头渲染为出处脚注
	src6 := "> 这是一个伟大的引言\n> \n> —— 某名言作者"
	html6, _, err := Render(src6, siteURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(html6, "<footer>—— 某名言作者</footer>") {
		t.Errorf("引用块以 —— 开头应渲染为 footer: %s", html6)
	}
}

func TestFactsAndMeta(t *testing.T) {
	siteURL := "https://sjtu.ow-shanghaiuniversity.com"
	body := "## 第一章 引言\n\n欢迎来到上海交通大学守望先锋社区！\n\n### 第二节 规则\n\n守望先锋是一款团队射击游戏。\n\n### 第三节 结尾\n\n再见！"
	html, plain, words, minutes, headings, err := Facts(body, siteURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(headings) != 3 {
		t.Fatalf("应提取 3 个标题项: %+v", headings)
	}
	if headings[0].Anchor != "h-1" || headings[1].Anchor != "h-2" || headings[2].Anchor != "h-3" {
		t.Errorf("锚点编号错误: %+v", headings)
	}
	if !strings.Contains(html, `id="h-1"`) {
		t.Errorf("HTML 应被注入锚点: %s", html)
	}
	if words <= 0 || minutes < 1 {
		t.Errorf("字数和时长应有效: words=%d, min=%d", words, minutes)
	}
	if !strings.Contains(plain, "上海交通大学守望先锋社区") {
		t.Errorf("纯文本应提取成功: %s", plain)
	}
}
