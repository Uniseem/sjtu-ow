package apigen

import (
	"crypto/sha256"
	"fmt"
	"path"
	"reflect"
	"sort"
	"strings"
)

// recursiveStructs finds the named structs in recursive JSON graphs. Only
// recursive structs get named exports; existing non-recursive shapes stay inline.
func recursiveStructs(types []reflect.Type) map[reflect.Type]string {
	names := map[reflect.Type]string{}
	seen := map[reflect.Type]bool{}
	active := map[reflect.Type]int{}
	stack := []reflect.Type{}
	var walk func(reflect.Type)
	walk = func(t reflect.Type) {
		if t == nil {
			return
		}
		t = deref(t)
		if at, ok := active[t]; ok {
			for _, item := range stack[at:] {
				if item.Kind() == reflect.Struct && item.Name() != "" && !isTime(item) {
					sum := sha256.Sum256([]byte(item.PkgPath()))
					names[item] = fmt.Sprintf("Api%s%s_%x", export(path.Base(item.PkgPath())), export(item.Name()), sum[:3])
				}
			}
			return
		}
		if seen[t] || isTime(t) {
			return
		}
		seen[t] = true
		active[t] = len(stack)
		stack = append(stack, t)
		switch t.Kind() {
		case reflect.Struct:
			for i := range t.NumField() {
				f := t.Field(i)
				if f.PkgPath != "" || f.Tag.Get("json") == "-" || isPath(f) || isQuery(f) {
					continue
				}
				walk(f.Type)
			}
		case reflect.Slice, reflect.Array:
			walk(t.Elem())
		case reflect.Map:
			walk(t.Key())
			walk(t.Elem())
		}
		stack = stack[:len(stack)-1]
		delete(active, t)
	}
	for _, t := range types {
		walk(t)
	}
	return names
}

func writeRecursive(b *strings.Builder, names map[reflect.Type]string) {
	ordered := make([]reflect.Type, 0, len(names))
	for t := range names {
		ordered = append(ordered, t)
	}
	sort.Slice(ordered, func(i, j int) bool { return names[ordered[i]] < names[ordered[j]] })
	for _, t := range ordered {
		writeInterface(b, names[t], structFields(t, map[reflect.Type]bool{}, names))
	}
}
