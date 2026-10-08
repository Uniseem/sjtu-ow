package mail

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"mime"
	"mime/multipart"
	"mime/quotedprintable"
	"net/textproto"
	"time"
)

// Message 是一封准备发出去的信：主题已经加过前缀，正文是带图的 MIME。
type Message struct {
	Subject string
	From    string
	To      string
	Header  textproto.MIMEHeader
	Raw     []byte
}

// Build 排好纯文本、HTML 和两张头图。prefix 空着就用 [SJTU-OW]。
func Build(letter Letter, to Person, from, siteURL, prefix string, now time.Time) (Message, error) {
	if prefix == "" {
		prefix = DefaultPrefix
	}
	text := letter.Text(to.Name, siteURL, now)
	html, err := letter.HTML(to.Name, siteURL, now)
	if err != nil {
		return Message{}, err
	}
	raw, err := assemble(text, html)
	if err != nil {
		return Message{}, err
	}
	h := textproto.MIMEHeader{}
	subject := PrefixSubject(letter.Subject, prefix)
	h.Set("Subject", mime.QEncoding.Encode("utf-8", subject))
	h.Set("From", from)
	h.Set("To", to.Address)
	h.Set("MIME-Version", "1.0")
	if letter.Unsubscribe != "" {
		h.Set("List-Unsubscribe", "<"+letter.Unsubscribe+">")
		h.Set("List-Unsubscribe-Post", "List-Unsubscribe=One-Click")
	}
	var buf bytes.Buffer
	for k, vs := range h {
		for _, v := range vs {
			fmt.Fprintf(&buf, "%s: %s\r\n", k, v)
		}
	}
	buf.WriteString("\r\n")
	buf.Write(raw)
	return Message{Subject: subject, From: from, To: to.Address, Header: h, Raw: buf.Bytes()}, nil
}

func assemble(text, html string) ([]byte, error) {
	var related bytes.Buffer
	rw := multipart.NewWriter(&related)
	htmlHeader := textproto.MIMEHeader{}
	htmlHeader.Set("Content-Type", "text/html; charset=utf-8")
	htmlHeader.Set("Content-Transfer-Encoding", "quoted-printable")
	hw, err := rw.CreatePart(htmlHeader)
	if err != nil {
		return nil, err
	}
	qhtml := quotedprintable.NewWriter(hw)
	if _, err := qhtml.Write([]byte(html)); err != nil {
		return nil, err
	}
	if err := qhtml.Close(); err != nil {
		return nil, err
	}
	for _, cid := range []string{"ow-mark", "ow-horizon"} {
		ih := textproto.MIMEHeader{}
		ih.Set("Content-Type", "image/png")
		ih.Set("Content-Transfer-Encoding", "base64")
		ih.Set("Content-ID", "<"+cid+">")
		ih.Set("Content-Disposition", "inline")
		pw, err := rw.CreatePart(ih)
		if err != nil {
			return nil, err
		}
		enc := base64.NewEncoder(base64.StdEncoding, &lineWrap{w: pw})
		if _, err := enc.Write(Art()[cid]); err != nil {
			return nil, err
		}
		if err := enc.Close(); err != nil {
			return nil, err
		}
	}
	if err := rw.Close(); err != nil {
		return nil, err
	}

	var alt bytes.Buffer
	aw := multipart.NewWriter(&alt)
	th := textproto.MIMEHeader{}
	th.Set("Content-Type", "text/plain; charset=utf-8")
	th.Set("Content-Transfer-Encoding", "quoted-printable")
	tw, err := aw.CreatePart(th)
	if err != nil {
		return nil, err
	}
	qtext := quotedprintable.NewWriter(tw)
	if _, err := qtext.Write([]byte(text)); err != nil {
		return nil, err
	}
	if err := qtext.Close(); err != nil {
		return nil, err
	}
	rh := textproto.MIMEHeader{}
	rh.Set("Content-Type", "multipart/related; boundary="+rw.Boundary())
	rp, err := aw.CreatePart(rh)
	if err != nil {
		return nil, err
	}
	if _, err := rp.Write(related.Bytes()); err != nil {
		return nil, err
	}
	if err := aw.Close(); err != nil {
		return nil, err
	}

	var out bytes.Buffer
	fmt.Fprintf(&out, "Content-Type: multipart/alternative; boundary=%s\r\n\r\n", aw.Boundary())
	out.Write(alt.Bytes())
	return out.Bytes(), nil
}

// lineWrap 给 base64 每 76 个字符换一行，邮件才认。
type lineWrap struct {
	w interface{ Write([]byte) (int, error) }
	n int
}

func (l *lineWrap) Write(p []byte) (int, error) {
	written := 0
	for len(p) > 0 {
		room := 76 - l.n
		if room == 0 {
			if _, err := l.w.Write([]byte("\r\n")); err != nil {
				return written, err
			}
			l.n = 0
			room = 76
		}
		n := room
		if n > len(p) {
			n = len(p)
		}
		if _, err := l.w.Write(p[:n]); err != nil {
			return written, err
		}
		l.n += n
		p = p[n:]
		written += n
	}
	return written, nil
}
