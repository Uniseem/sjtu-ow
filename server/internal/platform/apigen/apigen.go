// Package apigen 从接口注册表生成前端调用代码（12 号文档 5.3）。
// 守门矩阵、乱填、限流数字和查询预算已经在 Go 测试里直接读注册表，不另写一份。
//
// 生成的每个函数第一个参数是 `Requester`（`@sjtu-ow/api` 的 createClient 造的），
// 幂等键、401、待发信、错误形状都在那里统一处理；生成物自己不碰 fetch
// （frontend-migration A3）。类型照 encoding/json 的实际输出写：匿名嵌入的结构
// 摊平、切片和映射不会是 null（注册表编码前换成空的）、指针是 `T | null`（A4）。
package apigen

import (
	"encoding/json"
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

const imports = "import type { CallExtras, Requester } from \"../client.ts\"\n\n"

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
	b.WriteString(imports)
	var navItems []string
	for _, rt := range routes {
		name := funcName(rt.Method, rt.Pattern)
		typeName := export(name)
		sig := signature{name: name, out: typeName + "Out", route: rt}
		if hasJSON(rt.InType) {
			sig.in = typeName + "In"
			writeInterface(&b, sig.in, bodyFields(rt.InType))
		}
		if q := queryFields(rt.InType); q != "" {
			sig.query = typeName + "Query"
			writeInterface(&b, sig.query, q)
		}
		writeOut(&b, sig.out, rt.OutType)
		writeFunc(&b, sig)
		if section, tab, ok := splitNav(rt.Nav); ok {
			navItems = append(navItems, fmt.Sprintf(
				"  { section: %q, tab: %q, method: %q, path: %q },",
				section, tab, rt.Method, rt.Pattern))
		}
	}
	navFile := header + "export const nav: { section: string; tab: string; method: string; path: string }[] = [\n" +
		strings.Join(navItems, "\n")
	if len(navItems) > 0 {
		navFile += "\n"
	}
	navFile += "]\n"
	return b.String(), navFile
}

type signature struct {
	name, in, query, out string
	route                *api.Route
}

func writeInterface(b *strings.Builder, name, body string) {
	b.WriteString("export interface " + name + " {\n")
	b.WriteString(body)
	b.WriteString("}\n\n")
}

func writeOut(b *strings.Builder, name string, t reflect.Type) {
	if t != nil && deref(t).Kind() == reflect.Struct && !isTime(deref(t)) {
		writeInterface(b, name, structFields(deref(t), map[reflect.Type]bool{}))
		return
	}
	fmt.Fprintf(b, "export type %s = %s\n\n", name, tsType(t, map[reflect.Type]bool{}))
}

// writeFunc 写一个调用函数：Requester、路径参数、请求体、查询参数、其余选项。
func writeFunc(b *strings.Builder, s signature) {
	params := []string{"r: Requester"}
	var parts []string
	keys := pathKeys(s.route.InType)
	for _, k := range keys {
		params = append(params, k+": string | number")
	}
	if len(keys) > 0 {
		parts = append(parts, "params: { "+strings.Join(keys, ", ")+" }")
	}
	if s.in != "" {
		params = append(params, "body: "+s.in)
		parts = append(parts, "body")
	}
	if s.query != "" {
		params = append(params, "query: "+s.query+" = {}")
		parts = append(parts, "query")
	}
	params = append(params, "extras: CallExtras = {}")
	parts = append([]string{"...extras"}, parts...)
	fmt.Fprintf(b, "export function %s(%s): Promise<%s> {\n", s.name, strings.Join(params, ", "), s.out)
	fmt.Fprintf(b, "  return r<%s>(%q, %q, { %s })\n}\n\n", s.out, s.route.Method, s.route.Pattern, strings.Join(parts, ", "))
}

// bodyFields 是请求体里的字段：带 json 标签、不是路径或查询参数的。
func bodyFields(t reflect.Type) string {
	t = deref(t)
	var b strings.Builder
	for i := range t.NumField() {
		f := t.Field(i)
		if f.PkgPath != "" || isPath(f) || isQuery(f) {
			continue
		}
		name, opts := splitTag(f.Tag.Get("json"))
		if name == "" || name == "-" {
			continue
		}
		fmt.Fprintf(&b, "  %s%s: %s;\n", name, optional(opts), tsType(f.Type, map[reflect.Type]bool{}))
	}
	return b.String()
}

// queryFields 是 `query:"…"` 标签的字段，一律可选（bind.go 空值不绑）。
func queryFields(t reflect.Type) string {
	if t == nil || deref(t).Kind() != reflect.Struct {
		return ""
	}
	t = deref(t)
	var b strings.Builder
	for i := range t.NumField() {
		f := t.Field(i)
		key, ok := f.Tag.Lookup("query")
		if !ok || f.PkgPath != "" {
			continue
		}
		ts := "string"
		switch deref(f.Type).Kind() {
		case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
			reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
			ts = "number"
		case reflect.Bool:
			ts = "boolean"
		}
		fmt.Fprintf(&b, "  %s?: %s;\n", key, ts)
	}
	return b.String()
}

// structFields 照 encoding/json 的规则列出字段：没写名字的匿名结构摊平进来，
// 其余没写 json 标签的用 Go 的字段名。
func structFields(t reflect.Type, visited map[reflect.Type]bool) string {
	visited = copyVisited(visited)
	visited[t] = true
	var b strings.Builder
	for i := range t.NumField() {
		f := t.Field(i)
		tag := f.Tag.Get("json")
		if tag == "-" || isPath(f) || isQuery(f) {
			continue
		}
		name, opts := splitTag(tag)
		if name == "" && f.Anonymous && deref(f.Type).Kind() == reflect.Struct && !isTime(deref(f.Type)) {
			b.WriteString(structFields(deref(f.Type), visited))
			continue
		}
		if f.PkgPath != "" {
			continue
		}
		if name == "" {
			name = f.Name
		}
		fmt.Fprintf(&b, "  %s%s: %s;\n", name, optional(opts), tsType(f.Type, visited))
	}
	return b.String()
}

var rawMessage = reflect.TypeOf(json.RawMessage{})

func tsType(t reflect.Type, visited map[reflect.Type]bool) string {
	if t == nil {
		return "unknown"
	}
	nullable := t.Kind() == reflect.Pointer
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
		switch {
		case t == rawMessage:
			out = "unknown"
		case t.Elem().Kind() == reflect.Uint8:
			out = "string" // []byte 编码成 base64
		default:
			elem := tsType(t.Elem(), visited)
			if strings.Contains(elem, " | ") {
				elem = "(" + elem + ")"
			}
			out = elem + "[]"
		}
	case reflect.Map:
		out = "Record<" + tsType(t.Key(), visited) + ", " + tsType(t.Elem(), visited) + ">"
	case reflect.Struct:
		switch {
		case isTime(t):
			out = "string"
		case visited[t]:
			out = "unknown"
		default:
			body := structFields(t, visited)
			if body == "" {
				out = "Record<string, never>"
			} else {
				out = "{ " + strings.ReplaceAll(strings.TrimRight(body, "\n"), "\n", " ") + " }"
			}
		}
	default:
		out = "unknown"
	}
	if nullable {
		return out + " | null"
	}
	return out
}

func pathKeys(t reflect.Type) []string {
	if t == nil || deref(t).Kind() != reflect.Struct {
		return nil
	}
	t = deref(t)
	var keys []string
	for i := range t.NumField() {
		if p, ok := t.Field(i).Tag.Lookup("path"); ok {
			keys = append(keys, p)
		}
	}
	return keys
}

func hasJSON(t reflect.Type) bool {
	if t == nil || deref(t).Kind() != reflect.Struct {
		return false
	}
	t = deref(t)
	for i := range t.NumField() {
		f := t.Field(i)
		name, _ := splitTag(f.Tag.Get("json"))
		if name == "" || name == "-" || isPath(f) || isQuery(f) {
			continue
		}
		return true
	}
	return false
}

func isPath(f reflect.StructField) bool {
	_, ok := f.Tag.Lookup("path")
	return ok
}

func isQuery(f reflect.StructField) bool {
	_, ok := f.Tag.Lookup("query")
	return ok
}

func isTime(t reflect.Type) bool {
	return t == reflect.TypeOf(time.Time{})
}

func optional(opts string) string {
	if strings.Contains(opts, "omitempty") {
		return "?"
	}
	return ""
}

func copyVisited(m map[reflect.Type]bool) map[reflect.Type]bool {
	cp := make(map[reflect.Type]bool, len(m))
	for k, v := range m {
		cp[k] = v
	}
	return cp
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
	// 连字符分段各自首字母大写（verify-email → VerifyEmail），
	// 不然生成的 TS 标识符带 `-`，一 import 就炸。
	parts := strings.Split(s, "-")
	for i, p := range parts {
		if p == "" {
			continue
		}
		parts[i] = strings.ToUpper(p[:1]) + p[1:]
	}
	return strings.Join(parts, "")
}
