// Compare the goldmark renderer with what the production renderer made of the
// same source (corpus.json from corpus.py), after both are parsed and written
// back in one canonical shape so only real differences are left.
//
//	go run . [-v] [-show N] [-kind awkward]
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"
	"time"

	"golang.org/x/net/html"
	"golang.org/x/net/html/atom"
)

type entry struct {
	ID     string  `json:"id"`
	Source string  `json:"source"`
	HTML   *string `json:"html"`
}

type corpus struct {
	SiteURL string  `json:"site_url"`
	Entries []entry `json:"entries"`
}

var block = map[atom.Atom]bool{
	atom.P: true, atom.H1: true, atom.H2: true, atom.H3: true, atom.H4: true, atom.H5: true, atom.H6: true,
	atom.Ul: true, atom.Ol: true, atom.Li: true, atom.Pre: true, atom.Blockquote: true, atom.Table: true,
	atom.Thead: true, atom.Tbody: true, atom.Tr: true, atom.Figure: true, atom.Div: true, atom.Hr: true,
	atom.Footer: true, atom.Body: true,
}

func canon(fragment string) string {
	root := &html.Node{Type: html.ElementNode, DataAtom: atom.Body, Data: "body"}
	nodes, err := html.ParseFragment(strings.NewReader(fragment), root)
	if err != nil {
		return "PARSE ERROR: " + err.Error()
	}
	var b bytes.Buffer
	var walk func(n *html.Node, inPre bool)
	walk = func(n *html.Node, inPre bool) {
		switch n.Type {
		case html.TextNode:
			t := n.Data
			if !inPre {
				t = strings.Join(strings.Fields(t), " ")
				if strings.TrimSpace(n.Data) != "" {
					if strings.HasPrefix(n.Data, " ") || strings.HasPrefix(n.Data, "\n") {
						t = " " + t
					}
					if strings.HasSuffix(n.Data, " ") || strings.HasSuffix(n.Data, "\n") {
						t += " "
					}
				} else if (n.PrevSibling == nil || block[n.PrevSibling.DataAtom]) || (n.NextSibling == nil || block[n.NextSibling.DataAtom]) || block[n.Parent.DataAtom] {
					t = ""
				} else {
					t = " "
				}
			}
			b.WriteString(strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;").Replace(t))
		case html.ElementNode:
			b.WriteString("<" + n.Data)
			attrs := append([]html.Attribute(nil), n.Attr...)
			sort.Slice(attrs, func(i, j int) bool { return attrs[i].Key < attrs[j].Key })
			for _, a := range attrs {
				fmt.Fprintf(&b, ` %s="%s"`, a.Key, strings.NewReplacer("&", "&amp;", `"`, "&quot;").Replace(a.Val))
			}
			b.WriteString(">")
			pre := inPre || n.DataAtom == atom.Pre
			for c := n.FirstChild; c != nil; c = c.NextSibling {
				walk(c, pre)
			}
			if n.DataAtom != atom.Br && n.DataAtom != atom.Img && n.DataAtom != atom.Hr {
				b.WriteString("</" + n.Data + ">")
			}
			if block[n.DataAtom] {
				b.WriteString("\n")
			}
		}
	}
	for _, n := range nodes {
		walk(n, false)
	}
	return strings.TrimSpace(b.String())
}

func main() {
	show := flag.Int("show", 12, "how many differing documents to print")
	kind := flag.String("kind", "", "only ids starting with this (test, doc, awkward)")
	flag.Parse()
	raw, err := os.ReadFile("corpus.json")
	if err != nil {
		fmt.Println("run corpus.py first:", err)
		os.Exit(2)
	}
	var c corpus
	if err := json.Unmarshal(raw, &c); err != nil {
		panic(err)
	}
	type tally struct{ same, diff, skipped int }
	tallies := map[string]*tally{}
	var report strings.Builder
	var diffs []entry
	var total time.Duration
	var bytesIn int
	for _, e := range c.Entries {
		k := strings.SplitN(e.ID, ":", 2)[0]
		if *kind != "" && k != *kind {
			continue
		}
		if tallies[k] == nil {
			tallies[k] = &tally{}
		}
		if e.HTML == nil {
			tallies[k].skipped++
			continue
		}
		start := time.Now()
		got, _, err := Render(e.Source, c.SiteURL, nil)
		total += time.Since(start)
		bytesIn += len(e.Source)
		if err != nil {
			got = "RENDER ERROR: " + err.Error()
		}
		want, have := canon(*e.HTML), canon(got)
		if want == have {
			tallies[k].same++
			continue
		}
		tallies[k].diff++
		diffs = append(diffs, e)
		fmt.Fprintf(&report, "=== %s\n--- source\n%s\n--- production (markdown-it-py)\n%s\n--- goldmark\n%s\n\n", e.ID, e.Source, want, have)
	}
	_ = os.WriteFile("diff-report.txt", []byte(report.String()), 0o644)
	var same, diff, skip int
	for k, t := range tallies {
		fmt.Printf("%-8s identical %3d  different %3d  (production failed: %d)\n", k, t.same, t.diff, t.skipped)
		same, diff, skip = same+t.same, diff+t.diff, skip+t.skipped
	}
	fmt.Printf("total    identical %3d  different %3d  of %d documents; goldmark rendered %d KB of Markdown in %s\n",
		same, diff, same+diff+skip, bytesIn/1024, total.Round(time.Millisecond))
	for i, e := range diffs {
		if i >= *show {
			break
		}
		fmt.Printf("  differs: %s\n", e.ID)
	}
}
