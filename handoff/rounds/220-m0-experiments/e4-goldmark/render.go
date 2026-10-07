// A first cut of the site's Markdown renderer on goldmark, to see how much of
// content/markdown.py (markdown-it-py) can be had without a Python sidecar
// (12-architecture 5.12). The rules ported are the ones in that file: no raw
// HTML (shown as text), one newline is a line break, # and ## are h2 and
// ### and below h3, an image alone on a line is a figure with its caption (own
// images only), a Bilibili link alone is the player, bare addresses become
// links, a quote's last line starting with ―― is its source, tables get a
// scrolling wrapper, unsafe links stay text.
package main

import (
	"bytes"
	"fmt"
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
	bareURL   = regexp.MustCompile(`https?://[^\s<>"'（）【】「」『』《》，。！？；：、]+`)
	bvPattern = regexp.MustCompile(`BV[0-9A-Za-z]+`)
	bvExact   = regexp.MustCompile(`^BV[0-9A-Za-z]+$`)
	badScheme = regexp.MustCompile(`(?i)^(vbscript|javascript|file|data):`)
	okData    = regexp.MustCompile(`(?i)^data:image/(gif|png|jpeg|webp);`)
	biliHosts = map[string]bool{"bilibili.com": true, "www.bilibili.com": true, "m.bilibili.com": true, "player.bilibili.com": true}
	b23Hosts  = map[string]bool{"b23.tv": true, "www.b23.tv": true}
	headings  = map[int]int{1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 6: 3}
)

// Stats is what the Python renderer counts in env: images and videos shown.
type Stats struct{ Images, Videos int }

type site struct {
	siteURL string
	stats   Stats
	// The short-link cache (the `embeds` table): the page-render path never
	// goes to the network, it only looks here.
	short map[string]string
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

// plain is what a reader sees of an inline subtree (alt text, a source line).
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
			return // markdown-it's renderInlineAsText leaves code out of an alt text
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
		return s.short[raw] // only what the worker already resolved
	}
	return ""
}

// ---------------------------------------------------------------- transformer

func (s *site) Transform(doc *ast.Document, reader text.Reader, pc parser.Context) {
	src := reader.Source()
	// 1. everything that rewrites the tree, collected first so we do not edit
	// while walking.
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
		h.Level = headings[h.Level]
	}
	for _, l := range links { // unsafe destinations are plain text
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

// standalone: images one to a line, or a video link, that are the whole paragraph.
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

// linkBareURLs turns pasted addresses into links. goldmark cuts running text
// into many Text nodes (at _, *, & ...), so runs of plain text are joined first.
func (s *site) linkBareURLs(parent ast.Node, src []byte) {
	var run []*ast.Text
	var flush func()
	flush = func() {
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
		if soft || hard { // the line ended after the run: keep the break
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
	n.SetRaw(true) // already the literal text; the renderer escapes it below
	return n
}

// attribution: a quote's last line starting with ―― is its source.
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
	// markdown-it with html:false treats tags as text.
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

// Render is the whole renderer: Markdown in, HTML and the counts out.
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

// ---------------------------------------------------------------- ~~strike~~

// goldmark's GFM extension takes one tilde as strikethrough; markdown-it, and
// so every page written so far, needs two. This is that extension's parser
// with the minimum raised to two.
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
