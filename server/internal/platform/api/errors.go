package api

import (
	"encoding/json"
	"fmt"
	"net/http"
)

// Error 是接口层唯一的错误形状（12 号文档 5.4）。服务层返回它（或包着它的
// error），注册表负责渲染成 JSON；别的 error 一律按 500 处理。
type Error struct {
	Status  int
	Code    string
	Message string
	// Fields 是 422 的字段错误：字段名 → 一组中文说明。`__all__` 放整表单的。
	Fields map[string][]string
	// Header 附加响应头（限流的 Retry-After 之类，后续轮次用）。
	Header http.Header
}

func (e *Error) Error() string {
	return fmt.Sprintf("api %d %s: %s", e.Status, e.Code, e.Message)
}

// NewErr 造一个指定状态的错误。
func NewErr(status int, code, message string) *Error {
	return &Error{Status: status, Code: code, Message: message}
}

// Invalid 是 400：请求本身坏了（类型不对、JSON 坏）。
func Invalid(message string) *Error { return NewErr(http.StatusBadRequest, "invalid", message) }

// Unauthorized 是 401：没登录（前端跳 /accounts/login/?next=）。停用账号也算。
func Unauthorized(message string) *Error {
	return NewErr(http.StatusUnauthorized, "unauthorized", message)
}

// Forbidden 是 403：没权限。文案固定、不说原因（规则 12）。
func Forbidden() *Error {
	return NewErr(http.StatusForbidden, "forbidden", "没有权限做这件事")
}

// NotFound 是 404：不存在。没权限看的东西对没权限的人也长这样（规则 148）。
func NotFound(message string) *Error {
	return NewErr(http.StatusNotFound, "not_found", message)
}

// InvalidFields 是 422：业务校验不过，带字段错误（自动保存共用，5.5）。
func InvalidFields(fields map[string][]string) *Error {
	return &Error{
		Status:  http.StatusUnprocessableEntity,
		Code:    "invalid_fields",
		Message: "有几处要改",
		Fields:  fields,
	}
}

// body 是对外渲染的形状：
//
//	{ "error": { "code": "invalid", "message": "…" }, "fields": { "name": ["…"] } }
type errorBody struct {
	Error  errorHead           `json:"error"`
	Fields map[string][]string `json:"fields,omitempty"`
}

type errorHead struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func writeError(w http.ResponseWriter, err *Error) {
	body := errorBody{Error: errorHead{Code: err.Code, Message: err.Message}, Fields: err.Fields}
	w.Header().Set("Content-Type", "application/json")
	for k, vs := range err.Header {
		for _, v := range vs {
			w.Header().Add(k, v)
		}
	}
	w.WriteHeader(err.Status)
	_ = json.NewEncoder(w).Encode(body)
}
