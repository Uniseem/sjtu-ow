package content

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

// HomePins 公开投影不回传草稿/私密；后台沿用自身权限和完整选中列表。
func (s *Service) HomePins(ctx *app.Ctx, publicOnly bool) (HomePinsOut, error) {
	if !publicOnly && (ctx.Viewer == nil || ctx.Viewer.ID <= 0 || !ctx.Viewer.HasCap(CapArticlesEditAny)) {
		return HomePinsOut{}, api.Forbidden()
	}
	pins, err := s.store.GetHomePins(ctx.Context)
	if err != nil {
		return HomePinsOut{}, err
	}
	articles := []*Article{}
	for _, pin := range pins {
		a := pin.Article
		if a != nil && (!publicOnly || (a.Live && a.Public)) {
			articles = append(articles, a)
		}
	}
	pool, err := media.LoadPool(ctx.Context, s.store.d.ReadPool(), "default_cover")
	if err != nil {
		return HomePinsOut{}, err
	}
	items, err := s.store.newsItems(ctx.Context, articles, pool)
	if err != nil {
		return HomePinsOut{}, err
	}
	return HomePinsOut{Items: items}, nil
}
