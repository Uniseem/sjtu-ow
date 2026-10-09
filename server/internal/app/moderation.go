package app

import "context"

// ModerationSink 是内容送审的入口（规则 185–186）：各域在内容变更后调它，把文本放进待巡查记录。
// 失败只记日志，绝不阻塞操作。审核域的 Submit 就是它；没接上（nil）就不送。
type ModerationSink interface {
	Submit(ctx context.Context, targetType string, targetID int64, field, text, url string, authorID int64) error
}
