package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"reflect"
	"strings"
)

// maxBody 是单个请求体的上限（12 号文档 3.4 / 14-2：上传接口另算，走文件接口）。
const maxBody = 1 << 20

// bindRequest 把请求绑到 In 上：`path:"id"` 标签的字段从路径参数取（一律过
// ParseID，不合格 404），其余带 `json` 标签的字段从请求体取。
//
// 顺序是先 JSON 后路径：就算有人在 JSON 里塞了和路径同名的字段，最后也会被
// 路径值覆盖，改不了地址里指向的对象。
func bindRequest(w http.ResponseWriter, req *http.Request, rt *Route, in any) error {
	v := reflect.ValueOf(in)
	if v.Kind() != reflect.Pointer || v.IsNil() {
		return Invalid("请求解析失败")
	}
	v = v.Elem()
	t := v.Type()

	hasBody := false
	for i := range t.NumField() {
		f := t.Field(i)
		if _, isPath := f.Tag.Lookup("path"); isPath {
			continue
		}
		if _, hasJSON := f.Tag.Lookup("json"); hasJSON {
			hasBody = true
		}
	}
	if hasBody {
		if err := decodeBody(w, req, in); err != nil {
			return err
		}
	}
	// 路径参数最后写，覆盖 JSON 里可能混进来的同名字段。
	for i := range t.NumField() {
		f := t.Field(i)
		p, isPath := f.Tag.Lookup("path")
		if !isPath {
			continue
		}
		id, ok := ParseID(req.PathValue(p))
		if !ok {
			return NotFound("地址不对")
		}
		v.Field(i).SetInt(int64(id))
	}
	return nil
}

// decodeBody 严格解析 JSON：Content-Type 必须是 application/json、未知字段
// 拒收（400）、超过 1 MB 拒收（400）。POST 等写动作「只收 JSON」是跨站防护
// 的一层（12 号文档 4 节 CSRF 选型）。
func decodeBody(w http.ResponseWriter, req *http.Request, in any) error {
	ct := req.Header.Get("Content-Type")
	if !strings.HasPrefix(ct, "application/json") {
		return Invalid("请求体得是 JSON（Content-Type: application/json）")
	}
	if req.Body == nil || req.ContentLength == 0 {
		return Invalid("请求体是空的")
	}
	req.Body = http.MaxBytesReader(w, req.Body, maxBody)
	dec := json.NewDecoder(req.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(in); err != nil {
		var maxErr *http.MaxBytesError
		if errors.As(err, &maxErr) {
			return Invalid("请求体太大，最多 1 MB")
		}
		return Invalid("请求体读不懂：" + shortDecodeErr(err))
	}
	return nil
}

// shortDecodeErr 把 json 的报错变成人话，不漏内部细节。
func shortDecodeErr(err error) string {
	msg := err.Error()
	// 只留第一个词到冒号前的码（如 "json: unknown field"），说明性质就够了
	if i := strings.Index(msg, ":"); i > 0 {
		msg = msg[:i]
	}
	return strings.TrimPrefix(msg, "json ")
}
