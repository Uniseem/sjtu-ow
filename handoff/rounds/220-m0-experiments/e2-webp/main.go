// E2: how fast is the pure-Go WebP encoder (gen2brain/webp built with
// -tags nodynamic, CGO_ENABLED=0) on a real photograph, through the pipeline in
// 12-architecture 5.13: JPEG upload -> decode -> master WebP (long side <= 4000,
// q90) -> thumbnails by specification (fill-WxH, q80) -> decode the master.
//
//	go run -tags nodynamic . photo.jpg
package main

import (
	"bytes"
	"fmt"
	"image"
	"image/jpeg"
	"math/rand"
	"os"
	"runtime"
	"sort"
	"time"

	"github.com/gen2brain/webp"
	"golang.org/x/image/draw"
)

// phoneSized stretches a small photograph to a 4000 x 3000 "phone photo": the
// scene is real, the noise (sensor grain) makes it as hard to compress as one.
func phoneSized(src image.Image) *image.RGBA {
	dst := image.NewRGBA(image.Rect(0, 0, 4000, 3000))
	draw.CatmullRom.Scale(dst, dst.Bounds(), src, src.Bounds(), draw.Src, nil)
	r := rand.New(rand.NewSource(1))
	for i := 0; i < len(dst.Pix); i += 4 {
		n := int(r.Int31n(13)) - 6
		for c := 0; c < 3; c++ {
			v := int(dst.Pix[i+c]) + n
			if v < 0 {
				v = 0
			} else if v > 255 {
				v = 255
			}
			dst.Pix[i+c] = uint8(v)
		}
	}
	return dst
}

func fill(src image.Image, w, h int) *image.RGBA {
	sb := src.Bounds()
	// Largest centred crop with the target aspect, then scale: Wagtail's "fill".
	cw, ch := sb.Dx(), sb.Dy()
	if cw*h > ch*w {
		cw = ch * w / h
	} else {
		ch = cw * h / w
	}
	crop := image.Rect(sb.Min.X+(sb.Dx()-cw)/2, sb.Min.Y+(sb.Dy()-ch)/2, 0, 0)
	crop.Max = image.Pt(crop.Min.X+cw, crop.Min.Y+ch)
	dst := image.NewRGBA(image.Rect(0, 0, w, h))
	draw.CatmullRom.Scale(dst, dst.Bounds(), src, crop, draw.Src, nil)
	return dst
}

type result struct {
	name string
	d    []time.Duration
	size int
}

func (r *result) median() time.Duration {
	s := append([]time.Duration(nil), r.d...)
	sort.Slice(s, func(i, j int) bool { return s[i] < s[j] })
	return s[len(s)/2]
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("usage: e2 photo.jpg [runs]")
		os.Exit(2)
	}
	runs, masterSide, method := 5, 4000, 4
	if len(os.Args) > 2 {
		fmt.Sscan(os.Args[2], &runs)
	}
	if len(os.Args) > 3 {
		fmt.Sscan(os.Args[3], &masterSide)
	}
	if len(os.Args) > 4 {
		fmt.Sscan(os.Args[4], &method)
	}
	f, err := os.Open(os.Args[1])
	check(err)
	small, err := jpeg.Decode(f)
	check(err)
	f.Close()
	big := phoneSized(small)
	var upload bytes.Buffer
	check(jpeg.Encode(&upload, big, &jpeg.Options{Quality: 92}))
	fmt.Printf("input: %s %dx%d -> phone-sized upload %dx%d, %d KB JPEG; GOARCH=%s cores=%d\n",
		os.Args[1], small.Bounds().Dx(), small.Bounds().Dy(), 4000, 3000, upload.Len()/1024, runtime.GOARCH, runtime.NumCPU())

	if path := os.Getenv("E2_DUMP"); path != "" { // the same upload, for the libwebp reference
		check(os.WriteFile(path, upload.Bytes(), 0o600))
	}
	steps := []*result{{name: "decode JPEG 4000x3000"}, {name: fmt.Sprintf("master WebP q90 (%d wide, method %d)", masterSide, method)}, {name: "decode master WebP"}}
	type spec struct {
		name string
		w, h int
	}
	specs := []spec{{"fill-2400x1350 q80", 2400, 1350}, {"fill-1280x720 q80", 1280, 720}, {"fill-400x400 q80", 400, 400}, {"fill-88x88 q80", 88, 88}}
	for _, s := range specs {
		steps = append(steps, &result{name: "thumb " + s.name})
	}
	for i := 0; i < runs; i++ {
		t := time.Now()
		img, err := jpeg.Decode(bytes.NewReader(upload.Bytes()))
		check(err)
		steps[0].d = append(steps[0].d, time.Since(t))

		if masterSide < 4000 { // a smaller master: the long side is cut down first
			img = fill(img, masterSide, masterSide*3/4)
		}
		t = time.Now()
		var master bytes.Buffer
		check(webp.Encode(&master, img, webp.Options{Quality: 90, Method: method}))
		steps[1].d = append(steps[1].d, time.Since(t))
		steps[1].size = master.Len()

		t = time.Now()
		dec, err := webp.Decode(bytes.NewReader(master.Bytes()))
		check(err)
		steps[2].d = append(steps[2].d, time.Since(t))

		for k, s := range specs {
			t = time.Now()
			th := fill(dec, s.w, s.h)
			var out bytes.Buffer
			check(webp.Encode(&out, th, webp.Options{Quality: 80, Method: method}))
			steps[3+k].d = append(steps[3+k].d, time.Since(t))
			steps[3+k].size = out.Len()
		}
	}
	var total time.Duration
	for _, s := range steps {
		m := s.median()
		total += m
		size := ""
		if s.size > 0 {
			size = fmt.Sprintf("%6d KB", s.size/1024)
		}
		fmt.Printf("%-34s median %8s  %s\n", s.name, m.Round(time.Millisecond), size)
	}
	fmt.Printf("%-34s        %8s\n", "whole pipeline (sum of medians)", total.Round(time.Millisecond))
	var ms runtime.MemStats
	runtime.ReadMemStats(&ms)
	fmt.Printf("Go runtime memory taken from the OS: %d MB\n", ms.Sys/1024/1024)
}

func check(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "fatal:", err)
		os.Exit(1)
	}
}
