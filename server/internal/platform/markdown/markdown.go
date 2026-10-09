// Package markdown 提供站点唯一的 Markdown 渲染器（12 号文档 5.12、规则 61–72）。
// 基于 goldmark 构建，保证：
// 1. CommonMark + GFM 表格 + 两个波浪线删除线 + 单换行即 <br>（breaks=True）
// 2. 原始 HTML 当文本原样显示（不解析，转义输出）
// 3. #/## -> h2，### 及以下 -> h3（h1 留给页面标题）
// 4. 单独成行的本站图片 -> <figure> + <figcaption>，行内本站图片 -> 小 <img>，外站图片 -> 链接
// 5. 单独成行的 B 站链接 -> 播放器 iframe，b23.tv 短链查本地缓存表
// 6. 裸 URL 自动转链接
// 7. 引用块最后一行以「——」开头渲染为出处脚注 <footer>
// 8. 字数统计（中文字符数 + 拉丁单词数）与阅读时长（字数/400 + 每图 10 秒 + 每视频 60 秒，向上取整最少 1 分钟）
// 9. 目录（h2+h3 总数 >= 3 时，锚点 h-1, h-2...）
package markdown

import (
	"bytes"
	"fmt"
	htmlpkg "html"
	"math"
	"net/url"
	"regexp"
	"strconv"
	"strings"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/extension"
	extast "github.com/yuin/goldmark/extension/ast"
	"github.com/yuin/goldmark/parser"
	"github.com/yuin/goldmark/renderer"
	"github.com/yuin/goldmark/renderer/html"
	"github.com/yuin/goldmark/text"
	"github.com/yuin/goldmark/util"
)

const trailing = ".,;:!?)]}'\""

var (
	bareURL      = regexp.MustCompile(`https?://[^\s<>"'（）【】「」『』《》，。！？；：、]+`)
	bvPattern    = regexp.MustCompile(`BV[0-9A-Za-z]+`)
	bvExact      = regexp.MustCompile(`^BV[0-9A-Za-z]+$`)
	badScheme    = regexp.MustCompile(`(?i)^(vbscript|javascript|file|data):`)
	okData       = regexp.MustCompile(`(?i)^data:image/(gif|png|jpeg|webp);`)
	biliHosts    = map[string]bool{"bilibili.com": true, "www.bilibili.com": true, "m.bilibili.com": true, "player.bilibili.com": true}
	b23Hosts     = map[string]bool{"b23.tv": true, "www.b23.tv": true}
	headingsMap  = map[int]int{1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 6: 3}
	cjkRegex     = regexp.MustCompile(`[\p{Han}\x{3400}-\x{4DBF}\x{F900}-\x{FAFF}]`)
	latinRegex   = regexp.MustCompile(`[A-Za-z0-9]+(?:['’.-][A-Za-z0-9]+)*`)
	headingRegex = regexp.MustCompile(`(?i)<(h[23])(\s[^>]*)?>(.*?)</(h[23])\s*>`)
	idAttrRegex  = regexp.MustCompile(`(?i)\sid=(".*?"|'.*?'|\S+)`)
	tagRegex     = regexp.MustCompile(`<[^>]*>`)
)

// Stats 统计渲染出的多媒体数量。
type Stats struct {
	Images int
	Videos int
}

// Heading 目录标题项（规则 72）。
type Heading struct {
	Level  int    `json:"level"`
	Anchor string `json:"anchor"`
	Text   string `json:"text"`
}

type site struct {
	siteURL string
	stats   Stats
	short   map[string]string
}

// ---------------------------------------------------------------- nodes

var (
	kindRaw  = ast.NewNodeKind("SiteRawBlock")
	kindWrap = ast.NewNodeKind("SiteTableWrap")
)

type rawBlock struct {
	ast.BaseBlock
	HTML string
}

func (n *rawBlock) Kind() ast.NodeKind         { return kindRaw }
func (n *rawBlock) Dump(src []byte, level int) { ast.DumpHelper(n, src, level, nil, nil) }
func (n *rawBlock) IsRaw() bool                { return true }

type tableWrap struct{ ast.BaseBlock }

func (n *tableWrap) Kind() ast.NodeKind         { return kindWrap }
func (n *tableWrap) Dump(src []byte, level int) { ast.DumpHelper(n, src, level, nil, nil) }

// ---------------------------------------------------------------- helpers

func esc(s string) string {
	var b bytes.Buffer
	for _, r := range s {
		switch r {
		case '&':
			b.WriteString("&amp;")
		case '<':
			b.WriteString("&lt;")
		case '>':
			b.WriteString("&gt;")
		case '"':
			b.WriteString("&quot;")
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}

func plain(n ast.Node, src []byte) string {
	var b strings.Builder
	var walk func(ast.Node)
	walk = func(n ast.Node) {
		switch t := n.(type) {
		case *ast.Text:
			b.Write(util.ResolveEntityNames(util.UnescapePunctuations(t.Segment.Value(src))))
			if t.SoftLineBreak() || t.HardLineBreak() {
				b.WriteByte('\n')
			}
			return
		case *ast.String:
			b.Write(t.Value)
			return
		case *ast.CodeSpan:
			return
		}
		for c := n.FirstChild(); c != nil; c = c.NextSibling() {
			walk(c)
		}
	}
	walk(n)
	return b.String()
}

func (s *site) ownImage(src string) bool {
	u, err := url.Parse(src)
	if err != nil {
		return false
	}
	if u.Scheme == "" && u.Host == "" {
		return strings.HasPrefix(src, "/")
	}
	site, _ := url.Parse(s.siteURL)
	return (u.Scheme == "http" || u.Scheme == "https") && site.Host != "" && u.Host == site.Host
}

func validLink(dest string) bool {
	d := strings.TrimSpace(dest)
	if badScheme.MatchString(d) {
		return okData.MatchString(d)
	}
	return true
}

func extractBV(raw string) (string, int) {
	u, err := url.Parse(raw)
	if err != nil {
		return "", 0
	}
	q := u.Query()
	bvid := q.Get("bvid")
	if bvid != "" && !bvExact.MatchString(bvid) {
		bvid = ""
	}
	if bvid == "" {
		if m := bvPattern.FindString(u.Path); m != "" {
			bvid = m
		} else if m := bvPattern.FindString(raw); m != "" {
			bvid = m
		}
	}
	page := 0
	for _, key := range []string{"p", "page"} {
		if v := q.Get(key); v != "" {
			if n, err := strconv.Atoi(v); err == nil && regexp.MustCompile(`^\d+$`).MatchString(v) {
				page = n
			}
			break
		}
	}
	return bvid, page
}

func (s *site) videoSrc(raw string) string {
	raw = strings.TrimSpace(raw)
	u, err := url.Parse(raw)
	if err != nil {
		return ""
	}
	host := strings.ToLower(u.Hostname())
	switch {
	case biliHosts[host]:
		bvid, page := extractBV(raw)
		if bvid == "" {
			return ""
		}
		src := "https://player.bilibili.com/player.html?bvid=" + bvid
		if page > 1 {
			src += "&page=" + strconv.Itoa(page)
		}
		return src
	case b23Hosts[host]:
		if s.short != nil {
			return s.short[raw]
		}
		return ""
	}
	return ""
}

// ---------------------------------------------------------------- transformer

func (s *site) Transform(doc *ast.Document, reader text.Reader, pc parser.Context) {
	src := reader.Source()
	var headingsSeen []*ast.Heading
	var paragraphs []ast.Node
	var tables []ast.Node
	var quotes []*ast.Blockquote
	var links []*ast.Link
	var inlineParents []ast.Node
	_ = ast.Walk(doc, func(n ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		switch t := n.(type) {
		case *ast.Heading:
			headingsSeen = append(headingsSeen, t)
		case *ast.Paragraph:
			paragraphs = append(paragraphs, t)
		case *extast.Table:
			tables = append(tables, t)
		case *ast.Blockquote:
			quotes = append(quotes, t)
		case *ast.Link:
			links = append(links, t)
		}
		if n.Type() == ast.TypeBlock && hasInlineChildren(n) {
			inlineParents = append(inlineParents, n)
		}
		return ast.WalkContinue, nil
	})
	for _, h := range headingsSeen {
		h.Level = headingsMap[h.Level]
	}
	for _, l := range links {
		if !validLink(string(l.Destination)) {
			literal := ast.NewString([]byte("[" + plain(l, src) + "](" + string(l.Destination) + ")"))
			literal.SetRaw(false)
			l.Parent().ReplaceChild(l.Parent(), l, literal)
		}
	}
	for _, p := range paragraphs {
		if p.Parent() == nil {
			continue
		}
		if block := s.standalone(p, src); block != nil {
			p.Parent().ReplaceChild(p.Parent(), p, block)
		}
	}
	for _, parent := range inlineParents {
		if parent.Parent() != nil || parent.Kind() == ast.KindDocument {
			s.linkBareURLs(parent, src)
		}
	}
	for _, q := range quotes {
		attribution(q, src)
	}
	for _, t := range tables {
		wrap := &tableWrap{}
		parent := t.Parent()
		parent.ReplaceChild(parent, t, wrap)
		wrap.AppendChild(wrap, t)
	}
}

func hasInlineChildren(n ast.Node) bool {
	switch n.(type) {
	case *ast.Paragraph, *ast.TextBlock, *ast.Heading:
		return true
	case *extast.TableCell:
		return true
	}
	return false
}

func isBlank(n ast.Node, src []byte) bool {
	t, ok := n.(*ast.Text)
	return ok && strings.TrimSpace(string(t.Segment.Value(src))) == ""
}

func (s *site) standalone(p ast.Node, src []byte) ast.Node {
	var kids []ast.Node
	for c := p.FirstChild(); c != nil; c = c.NextSibling() {
		if !isBlank(c, src) {
			kids = append(kids, c)
		}
	}
	if len(kids) == 0 {
		return nil
	}
	allImages := true
	for _, k := range kids {
		if _, ok := k.(*ast.Image); !ok {
			allImages = false
		}
	}
	if allImages {
		var out strings.Builder
		for _, k := range kids {
			if !s.ownImage(string(k.(*ast.Image).Destination)) {
				return nil
			}
		}
		for _, k := range kids {
			img := k.(*ast.Image)
			caption := plain(img, src)
			note := ""
			if caption != "" {
				note = "<figcaption>" + esc(caption) + "</figcaption>"
			}
			fmt.Fprintf(&out, `<figure><img src="%s" alt="%s" loading="lazy">%s</figure>`+"\n", esc(string(img.Destination)), esc(caption), note)
		}
		s.stats.Images += len(kids)
		return &rawBlock{HTML: out.String()}
	}
	link := ""
	allText := true
	for _, k := range kids {
		if _, ok := k.(*ast.Text); !ok {
			allText = false
		}
	}
	switch {
	case allText:
		var b strings.Builder
		for _, k := range kids {
			b.Write(k.(*ast.Text).Segment.Value(src))
		}
		candidate := strings.TrimSpace(b.String())
		if m := bareURL.FindString(candidate); m == candidate && m != "" {
			link = candidate
		}
	case len(kids) == 1:
		if l, ok := kids[0].(*ast.Link); ok {
			link = string(l.Destination)
		}
	}
	if link == "" {
		return nil
	}
	player := s.videoSrc(link)
	if player == "" {
		return nil
	}
	s.stats.Videos++
	return &rawBlock{HTML: `<figure class="c-prose__video"><iframe src="` + esc(player) + `" title="B 站视频" allowfullscreen loading="lazy" referrerpolicy="strict-origin-when-cross-origin"></iframe></figure>` + "\n"}
}

func (s *site) linkBareURLs(parent ast.Node, src []byte) {
	var run []*ast.Text
	flush := func() {
		if len(run) == 0 {
			return
		}
		defer func() { run = nil }()
		var b strings.Builder
		for _, t := range run {
			b.Write(t.Segment.Value(src))
		}
		joined := b.String()
		if !strings.Contains(joined, "://") {
			return
		}
		last := run[len(run)-1]
		soft, hard := last.SoftLineBreak(), last.HardLineBreak()
		matches := bareURL.FindAllStringIndex(joined, -1)
		var pieces []ast.Node
		pos := 0
		any := false
		for _, m := range matches {
			addr := strings.TrimRight(joined[m[0]:m[1]], trailing)
			if addr == "" || !validLink(addr) {
				continue
			}
			any = true
			if m[0] > pos {
				pieces = append(pieces, str(joined[pos:m[0]]))
			}
			link := ast.NewLink()
			link.Destination = []byte(addr)
			link.AppendChild(link, str(addr))
			pieces = append(pieces, link)
			pos = m[0] + len(addr)
		}
		if !any {
			return
		}
		if pos < len(joined) {
			pieces = append(pieces, str(joined[pos:]))
		}
		for _, p := range pieces {
			parent.InsertBefore(parent, run[0], p)
		}
		for _, t := range run {
			parent.RemoveChild(parent, t)
		}
		if soft || hard {
			br := ast.NewTextSegment(text.NewSegment(0, 0))
			br.SetSoftLineBreak(soft)
			br.SetHardLineBreak(hard)
			last := pieces[len(pieces)-1]
			parent.InsertAfter(parent, last, br)
		}
	}
	for c := parent.FirstChild(); c != nil; {
		next := c.NextSibling()
		if t, ok := c.(*ast.Text); ok {
			run = append(run, t)
			if t.SoftLineBreak() || t.HardLineBreak() {
				flush()
			}
		} else {
			flush()
		}
		c = next
	}
	flush()
}

func str(s string) *ast.String {
	n := ast.NewString([]byte(s))
	n.SetRaw(true)
	return n
}

func attribution(q *ast.Blockquote, src []byte) {
	last, ok := q.LastChild().(*ast.Paragraph)
	if !ok {
		return
	}
	var kids []ast.Node
	for c := last.FirstChild(); c != nil; c = c.NextSibling() {
		kids = append(kids, c)
	}
	breakAt := -1
	for i, c := range kids {
		if t, ok := c.(*ast.Text); ok && (t.SoftLineBreak() || t.HardLineBreak()) {
			breakAt = i
		}
	}
	tail := kids[breakAt+1:]
	if len(tail) == 0 {
		return
	}
	var b strings.Builder
	for _, c := range tail {
		t, ok := c.(*ast.Text)
		if !ok {
			return
		}
		b.Write(util.ResolveEntityNames(util.UnescapePunctuations(t.Segment.Value(src))))
	}
	source := strings.TrimSpace(b.String())
	if !strings.HasPrefix(source, "——") {
		return
	}
	footer := &rawBlock{HTML: "<footer>" + esc(source) + "</footer>\n"}
	if breakAt >= 0 {
		for _, c := range tail {
			last.RemoveChild(last, c)
		}
		if t, ok := kids[breakAt].(*ast.Text); ok {
			t.SetSoftLineBreak(false)
			t.SetHardLineBreak(false)
		}
		q.InsertAfter(q, last, footer)
	} else {
		q.ReplaceChild(q, last, footer)
	}
}

// ---------------------------------------------------------------- rendering

type siteRenderer struct{ s *site }

func (r *siteRenderer) RegisterFuncs(reg renderer.NodeRendererFuncRegisterer) {
	reg.Register(kindRaw, func(w util.BufWriter, src []byte, n ast.Node, entering bool) (ast.WalkStatus, error) {
		if entering {
			_, _ = w.WriteString(n.(*rawBlock).HTML)
		}
		return ast.WalkSkipChildren, nil
	})
	reg.Register(kindWrap, func(w util.BufWriter, src []byte, n ast.Node, entering bool) (ast.WalkStatus, error) {
		if entering {
			_, _ = w.WriteString(`<div class="c-prose__table">`)
		} else {
			_, _ = w.WriteString("</div>\n")
		}
		return ast.WalkContinue, nil
	})
	reg.Register(ast.KindHTMLBlock, func(w util.BufWriter, src []byte, n ast.Node, entering bool) (ast.WalkStatus, error) {
		if entering {
			var b strings.Builder
			lines := n.(*ast.HTMLBlock).Lines()
			for i := 0; i < lines.Len(); i++ {
				seg := lines.At(i)
				b.WriteString(strings.TrimRight(string(seg.Value(src)), "\n"))
				if i < lines.Len()-1 {
					b.WriteString("\n")
				}
			}
			if cl := n.(*ast.HTMLBlock).ClosureLine; cl.Len() > 0 {
				b.WriteString("\n" + strings.TrimRight(string(cl.Value(src)), "\n"))
			}
			_, _ = w.WriteString("<p>" + strings.ReplaceAll(esc(b.String()), "\n", "<br>\n") + "</p>\n")
		}
		return ast.WalkSkipChildren, nil
	})
	reg.Register(ast.KindRawHTML, func(w util.BufWriter, src []byte, n ast.Node, entering bool) (ast.WalkStatus, error) {
		if entering {
			segs := n.(*ast.RawHTML).Segments
			for i := 0; i < segs.Len(); i++ {
				seg := segs.At(i)
				_, _ = w.WriteString(esc(string(seg.Value(src))))
			}
		}
		return ast.WalkSkipChildren, nil
	})
	reg.Register(ast.KindString, func(w util.BufWriter, src []byte, n ast.Node, entering bool) (ast.WalkStatus, error) {
		if entering {
			_, _ = w.WriteString(esc(string(n.(*ast.String).Value)))
		}
		return ast.WalkContinue, nil
	})
	reg.Register(extast.KindStrikethrough, func(w util.BufWriter, src []byte, n ast.Node, entering bool) (ast.WalkStatus, error) {
		if entering {
			_, _ = w.WriteString("<s>")
		} else {
			_, _ = w.WriteString("</s>")
		}
		return ast.WalkContinue, nil
	})
	reg.Register(ast.KindImage, func(w util.BufWriter, src []byte, n ast.Node, entering bool) (ast.WalkStatus, error) {
		if !entering {
			return ast.WalkContinue, nil
		}
		img := n.(*ast.Image)
		dest := string(img.Destination)
		alt := plain(img, src)
		switch {
		case r.s.ownImage(dest):
			r.s.stats.Images++
			_, _ = w.WriteString(`<img src="` + esc(dest) + `" alt="` + esc(alt) + `" loading="lazy">`)
		case strings.HasPrefix(strings.ToLower(dest), "http://") || strings.HasPrefix(strings.ToLower(dest), "https://"):
			label := alt
			if label == "" {
				label = "图片"
			}
			_, _ = w.WriteString(`<a href="` + esc(dest) + `">` + esc(label) + `</a>`)
		default:
			_, _ = w.WriteString(esc(alt))
		}
		return ast.WalkSkipChildren, nil
	})
}

// ---------------------------------------------------------------- strike parser

type strikeParser struct{}
type strikeProcessor struct{}

func (strikeProcessor) IsDelimiter(b byte) bool { return b == '~' }
func (strikeProcessor) CanOpenCloser(opener, closer *parser.Delimiter) bool {
	return opener.Char == closer.Char
}
func (strikeProcessor) OnMatch(consumes int) ast.Node { return extast.NewStrikethrough() }

func (*strikeParser) Trigger() []byte { return []byte{'~'} }

func (*strikeParser) Parse(parent ast.Node, block text.Reader, pc parser.Context) ast.Node {
	before := block.PrecendingCharacter()
	line, segment := block.PeekLine()
	node := parser.ScanDelimiter(line, before, 2, strikeProcessor{})
	if node == nil || node.OriginalLength > 2 || before == '~' {
		return nil
	}
	node.Segment = segment.WithStop(segment.Start + node.OriginalLength)
	block.Advance(node.OriginalLength)
	pc.PushDelimiter(node)
	return node
}

// ---------------------------------------------------------------- public API

// Render 将 Markdown 源码渲染为站内标准的 HTML，并输出统计信息。
func Render(source string, siteURL string, short map[string]string) (string, Stats, error) {
	s := &site{siteURL: siteURL, short: short}
	md := goldmark.New(
		goldmark.WithExtensions(extension.Table),
		goldmark.WithParserOptions(
			parser.WithASTTransformers(util.Prioritized(s, 100)),
			parser.WithInlineParsers(util.Prioritized(&strikeParser{}, 500)),
		),
		goldmark.WithRendererOptions(
			html.WithHardWraps(),
			renderer.WithNodeRenderers(util.Prioritized(&siteRenderer{s}, 50)),
		),
	)
	var out bytes.Buffer
	if err := md.Convert([]byte(source), &out); err != nil {
		return "", Stats{}, err
	}
	return out.String(), s.stats, nil
}

// PlainHTML 从已渲染的 HTML 提取纯文本（规则 71、233）。
func PlainHTML(renderedHTML string) string {
	stripped := tagRegex.ReplaceAllString(renderedHTML, " ")
	unescaped := htmlpkg.UnescapeString(stripped)
	var lines []string
	for _, l := range strings.Split(unescaped, "\n") {
		t := strings.TrimSpace(l)
		if t != "" {
			lines = append(lines, t)
		}
	}
	return strings.Join(lines, "\n")
}

// WordCount 计算中文字符与拉丁单词数（规则 70）。
func WordCount(plainText string) int {
	return len(cjkRegex.FindAllString(plainText, -1)) + len(latinRegex.FindAllString(plainText, -1))
}

// ReadingMinutes 计算阅读时间（分钟）：字数/400 + 每图 10 秒 + 每视频 60 秒，向上取整最少 1 分钟（规则 70）。
func ReadingMinutes(words int, images int, videos int) int {
	seconds := float64(words)/400.0*60.0 + float64(images)*10.0 + float64(videos)*60.0
	return int(math.Max(1, math.Ceil(seconds/60.0)))
}

// AnchorHeadings 为所有 h2/h3 标签注入数字锚点 id="h-1", id="h-2" 并抽取目录（规则 72）。
func AnchorHeadings(htmlContent string) (string, []Heading) {
	var headings []Heading
	res := headingRegex.ReplaceAllStringFunc(htmlContent, func(m string) string {
		sub := headingRegex.FindStringSubmatch(m)
		if len(sub) < 5 || !strings.EqualFold(sub[1], sub[4]) {
			return m
		}
		tag := strings.ToLower(sub[1])
		attrs := sub[2]
		inner := sub[3]
		anchor := fmt.Sprintf("h-%d", len(headings)+1)
		cleanText := strings.TrimSpace(tagRegex.ReplaceAllString(inner, ""))
		level := 2
		if tag == "h3" {
			level = 3
		}
		headings = append(headings, Heading{
			Level:  level,
			Anchor: anchor,
			Text:   cleanText,
		})
		attrsWithoutID := idAttrRegex.ReplaceAllString(attrs, "")
		return fmt.Sprintf(`<%s id="%s"%s>%s</%s>`, tag, anchor, attrsWithoutID, inner, tag)
	})
	return res, headings
}

// Facts 一次性完成渲染、锚点、纯文本、字数与阅读时间计算。
func Facts(bodyMD string, siteURL string, short map[string]string) (renderedHTML string, plain string, words int, minutes int, headings []Heading, err error) {
	rawHTML, stats, err := Render(bodyMD, siteURL, short)
	if err != nil {
		return "", "", 0, 0, nil, err
	}
	anchoredHTML, hdgs := AnchorHeadings(rawHTML)
	plain = PlainHTML(anchoredHTML)
	words = WordCount(plain)
	minutes = ReadingMinutes(words, stats.Images, stats.Videos)
	return anchoredHTML, plain, words, minutes, hdgs, nil
}
