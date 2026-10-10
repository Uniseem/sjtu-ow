package api

import "reflect"

// nonNil 把答复里没赋值的切片和映射换成空的，编码出来是 `[]`、`{}` 而不是
// `null`。这样 apigen 生成的类型可以照实写 `T[]`，前端不用每处 `?? []`
// （frontend-migration A4）。指针照旧：`*T` 为 nil 仍是 `null`，类型写 `T | null`。
//
// 只改副本的顶层；嵌在切片元素和指针后面的值是就地改的——都是服务层刚造出来
// 给这次答复用的，把 nil 换成空不改变含义。
func nonNil(out any) any {
	v := reflect.ValueOf(out)
	if !v.IsValid() {
		return out
	}
	cp := reflect.New(v.Type()).Elem()
	cp.Set(v)
	fillNil(cp, 0)
	return cp.Interface()
}

func fillNil(v reflect.Value, depth int) {
	if depth > 32 {
		return
	}
	switch v.Kind() {
	case reflect.Pointer:
		if !v.IsNil() {
			fillNil(v.Elem(), depth+1)
		}
	case reflect.Struct:
		for i := range v.NumField() {
			f := v.Field(i)
			if f.CanSet() {
				fillNil(f, depth+1)
			}
		}
	case reflect.Slice:
		// []byte（含 json.RawMessage）编码成字符串或原文，空的 RawMessage 会让
		// 编码出错，原样放过。
		if v.Type().Elem().Kind() == reflect.Uint8 {
			return
		}
		if v.IsNil() {
			if v.CanSet() {
				v.Set(reflect.MakeSlice(v.Type(), 0, 0))
			}
			return
		}
		for i := range v.Len() {
			fillNil(v.Index(i), depth+1)
		}
	case reflect.Map:
		if v.IsNil() && v.CanSet() {
			v.Set(reflect.MakeMap(v.Type()))
		}
	}
}
