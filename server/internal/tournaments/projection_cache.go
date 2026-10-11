package tournaments

import (
	"context"
)

type projectionCacheKey struct{}

type memberProblemKey struct {
	Tournament int64
	User       int64
	Self       bool
}

type conflictKey struct {
	Tournament int64
	User       int64
	Excluded   int64
}

// projectionCache is confined to one consistent read snapshot. It avoids
// rebuilding the same member's eligibility when the form needs both an overall
// problem list and per-member messages. Writers never share this cache.
type projectionCache struct {
	members   map[memberProblemKey][]string
	conflicts map[conflictKey]string
}

func cachedProjectionContext(ctx context.Context) context.Context {
	return context.WithValue(ctx, projectionCacheKey{}, &projectionCache{
		members: map[memberProblemKey][]string{}, conflicts: map[conflictKey]string{},
	})
}

func projectionCacheFrom(ctx context.Context) *projectionCache {
	cache, _ := ctx.Value(projectionCacheKey{}).(*projectionCache)
	return cache
}
