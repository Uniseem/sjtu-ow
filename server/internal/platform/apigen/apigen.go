// Package apigen 从接口注册表生成前端调用代码（12 号文档 5.3）。
// 守门矩阵、乱填、限流数字和查询预算已经在 Go 测试里直接读注册表，不另写一份。
package apigen

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

const header = "// 由 sjtuow apigen 生成。不要手改。\n\n"

// Write 把注册表写成 dir 下的 index.ts 和 nav.ts。
func Write(dir string, reg *api.Registry) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	index, nav := Render(reg)
	if err := os.WriteFile(filepath.Join(dir, "index.ts"), []byte(index), 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, "nav.ts"), []byte(nav), 0o644)
}

// Render 返回 index.ts 和 nav.ts 的正文。
func Render(reg *api.Registry) (index, nav string) {
	routes := append([]*api.Route(nil), reg.Routes()...)
	sort.Slice(routes, func(i, j int) bool {
		if routes[i].Method != routes[j].Method {
			return routes[i].Method < routes[j].Method
		}
		return routes[i].Pattern < routes[j].Pattern
	})
	var b strings.Builder
	b.WriteString(header)
	var navItems []string
	for _, rt := range routes {
		name := funcName(rt.Method, rt.Pattern)
		inName := export(name) + "In"
		outName := export(name) + "Out"
		writeStruct(&b, inName, rt.InType, true)
		writeStruct(&b, outName, rt.OutType, false)
		writeFunc(&b, name, inName, outName, rt)
		if section, tab, ok := splitNav(rt.Nav); ok {
			navItems = append(navItems, fmt.Sprintf(
				"  { section: %q, tab: %q, method: %q, path: %q },",
				section, tab, rt.Method, rt.Pattern))
		}
	}
	b.WriteString(callFn)
	navFile := header + "export const nav: { section: string; tab: string; method: string; path: string }[] = [\n" +
		strings.Join(navItems, "\n")
	if len(navItems) > 0 {
		navFile += "\n"
	}
	navFile += "]\n"
	return b.String(), navFile
}

func writeStruct(b *strings.Builder, name string, t reflect.Type, jsonOnly bool) {
	b.WriteString("export interface " + name + " {\n")
	b.WriteString(fields(t, jsonOnly))
	b.WriteString("}\n\n")
}

func fields(t reflect.Type, jsonOnly bool) string {
	t = deref(t)
	if t.Kind() != reflect.Struct {
		return ""
	}
	var b strings.Builder
	for i := range t.NumField() {
		f := t.Field(i)
		if f.PkgPath != "" {
			continue
		}
		tag := f.Tag.Get("json")
		if tag == "-" {
			continue
		}
		if _, isPath := f.Tag.Lookup("path"); isPath {
			continue
		}
		name, opts := splitTag(tag)
		if name == "" {
			if jsonOnly {
				continue
			}
			name = f.Name
		}
		opt := ""
		if strings.Contains(opts, "omitempty") {
			opt = "?"
		}
		fmt.Fprintf(&b, "  %s%s: %s;\n", name, opt, tsType(f.Type))
	}
	return b.String()
}

func writeFunc(b *strings.Builder, name, inName, outName string, rt *api.Route) {
	params, arg := pathArgs(rt)
	body := "undefined"
	if hasJSON(rt.InType) {
		params = append(params, "body: "+inName)
		body = "body"
	}
	fmt.Fprintf(b, "export function %s(%s): Promise<%s> {\n", name, strings.Join(params, ", "), outName)
	fmt.Fprintf(b, "  return call<%s>(%q, %q, { %s }, %s)\n}\n\n", outName, rt.Method, rt.Pattern, arg, body)
}

func pathArgs(rt *api.Route) (params []string, object string) {
	t := deref(rt.InType)
	var keys []string
	if t.Kind() == reflect.Struct {
		for i := range t.NumField() {
			f := t.Field(i)
			p, ok := f.Tag.Lookup("path")
			if !ok {
				continue
			}
			params = append(params, p+": string")
			keys = append(keys, p)
		}
	}
	return params, strings.Join(keys, ", ")
}

func hasJSON(t reflect.Type) bool {
	t = deref(t)
	if t.Kind() != reflect.Struct {
		return false
	}
	for i := range t.NumField() {
		f := t.Field(i)
		tag := f.Tag.Get("json")
		if tag == "" || tag == "-" {
			continue
		}
		if _, isPath := f.Tag.Lookup("path"); isPath {
			continue
		}
		return true
	}
	return false
}

func tsType(t reflect.Type) string {
	isPtr := t.Kind() == reflect.Pointer
	t = deref(t)
	var out string
	switch t.Kind() {
	case reflect.String:
		out = "string"
	case reflect.Bool:
		out = "boolean"
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
		reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64,
		reflect.Float32, reflect.Float64:
		out = "number"
	case reflect.Slice, reflect.Array:
		out = tsType(t.Elem()) + "[]"
	case reflect.Map:
		out = "Record<" + tsType(t.Key()) + ", " + tsType(t.Elem()) + ">"
	case reflect.Struct:
		if t.PkgPath() == "time" && t.Name() == "Time" || t == reflect.TypeOf(time.Time{}) {
			out = "string"
		} else {
			body := fields(t, false)
			if body == "" {
				out = "Record<string, never>"
			} else {
				out = "{ " + strings.ReplaceAll(strings.TrimRight(body, "\n"), "\n", " ") + " }"
			}
		}
	default:
		out = "unknown"
	}
	if isPtr {
		return out + " | null"
	}
	return out
}

func deref(t reflect.Type) reflect.Type {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}
	return t
}

func splitTag(tag string) (name, opts string) {
	name, opts, _ = strings.Cut(tag, ",")
	return name, opts
}

func splitNav(nav string) (section, tab string, ok bool) {
	section, tab, ok = strings.Cut(nav, "/")
	return section, tab, ok && section != "" && tab != ""
}

func funcName(method, pattern string) string {
	parts := []string{strings.ToLower(method)}
	for _, seg := range strings.Split(pattern, "/") {
		seg = strings.Trim(seg, "{}")
		if seg == "" {
			continue
		}
		parts = append(parts, export(seg))
	}
	return parts[0] + strings.Join(parts[1:], "")
}

func export(s string) string {
	if s == "" {
		return s
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

const callFn = `export async function call<T>(method: string, path: string, params: Record<string, string>, body?: unknown): Promise<T> {
  let url = path
  for (const key of Object.keys(params)) {
    url = url.split("{" + key + "}").join(encodeURIComponent(params[key]))
  }
  const init: RequestInit = { method }
  if (body !== undefined) {
    init.headers = { "content-type": "application/json" }
    init.body = JSON.stringify(body)
  }
  const response = await fetch(url, init)
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return (await response.json()) as T
}
`
