package apigen

import (
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

type recursiveComment struct {
	ID       int                 `json:"id"`
	Replies  []*recursiveComment `json:"replies,omitempty"`
	EditedAt *time.Time          `json:"edited_at"`
}
type mutualA struct {
	B *mutualB `json:"b"`
}
type mutualB struct {
	A *mutualA `json:"a,omitempty"`
}
type recursiveOut struct {
	Comments []*recursiveComment `json:"comments"`
	Other    *mutualA            `json:"other"`
}

func TestRecursiveJSONTypes(t *testing.T) {
	reg := &api.Registry{}
	api.Get(reg, "/api/recursive", api.Public, func(*app.Ctx, struct{}) (recursiveOut, error) { return recursiveOut{}, nil })
	index, _ := Render(reg)
	names := recursiveStructs([]reflect.Type{reflect.TypeOf(recursiveOut{})})
	comment := names[reflect.TypeOf(recursiveComment{})]
	a := names[reflect.TypeOf(mutualA{})]
	b := names[reflect.TypeOf(mutualB{})]
	if comment == "" || a == "" || b == "" || a == b || strings.Contains(index, "unknown") {
		t.Fatalf("recursive names=%v index=%s", names, index)
	}
	for _, want := range []string{"export interface " + comment + " {", "replies?: (" + comment + " | null)[];", "edited_at: string | null;", "comments: (" + comment + " | null)[];", "b: " + b + " | null;", "a?: " + a + " | null;"} {
		if !strings.Contains(index, want) {
			t.Fatalf("missing %s: %s", want, index)
		}
	}
	again, _ := Render(reg)
	if again != index {
		t.Fatal("unstable recursive output")
	}
}
