"""Wagtail page types and article categories (design 5.1–5.3, 12.5)."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page

from content.blocks import ARTICLE_BODY_BLOCKS
from content.forms import ArticlePageForm
from content.seo import build_seo

ARTICLES_PER_PAGE = 12
MAX_PINNED_ARTICLES = 3
MAX_CAROUSEL_SLIDES = 6
HOME_ARTICLE_COUNT = 3

# Slugs that would collide with Django routes registered before wagtail_urls
# (design 13.4). Enforced on HomePage children only.
RESERVED_CHILD_SLUGS = frozenset(
    {
        "admin",
        "accounts",
        "comments",
        "documents",
        "me",
        "api",
        "tournaments",
        "members",
        "teams",
        "scrims",
        "submit",
        "_fragments",
        "healthz",
        "sitemap.xml",
        "robots.txt",
    }
)


class ArticleCategory(models.Model):
    """Snippet: article category (design 12.5.2)."""

    name = models.CharField("名称", max_length=32)
    slug = models.SlugField("网址片段", max_length=64, unique=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    allow_submission = models.BooleanField("开放投稿", default=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("sort_order"),
        FieldPanel("allow_submission"),
    ]

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "文章分类"
        verbose_name_plural = "文章分类"

    def __str__(self):
        return self.name


class SeoPageMixin:
    """Open Graph / canonical helpers. ``seo_kind`` is the 13.14 table row."""

    seo_kind = "other"

    def get_share_title(self):
        return self.seo_title or self.title

    def get_share_description(self):
        return self.search_description or None

    def get_share_image(self):
        return None

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["seo"] = build_seo(
            request,
            title=self.get_share_title(),
            description=self.get_share_description(),
            image=self.get_share_image(),
            kind=self.seo_kind,
            page=self,
        )
        return context


class ReservedSlugMixin:
    def clean(self):
        slug = (self.slug or "").lower()
        if slug in RESERVED_CHILD_SLUGS:
            raise ValidationError(
                {"slug": f"网址片段「{self.slug}」与固定路由冲突，请换一个。"}
            )
        super().clean()


class HomePagePinnedArticle(Orderable):
    page = ParentalKey(
        "content.HomePage",
        on_delete=models.CASCADE,
        related_name="pinned_articles",
    )
    article = models.ForeignKey(
        "content.ArticlePage",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="文章",
    )

    panels = [FieldPanel("article")]

    class Meta(Orderable.Meta):
        verbose_name = "置顶文章"
        verbose_name_plural = "置顶文章"
        constraints = [
            models.UniqueConstraint(
                fields=["page", "article"],
                name="content_homepinned_unique_article",
            ),
        ]

    def clean(self):
        super().clean()
        self._enforce_pin_limit()

    def save(self, *args, **kwargs):
        self._enforce_pin_limit()
        return super().save(*args, **kwargs)

    def _enforce_pin_limit(self):
        if not self.page_id:
            return
        qs = HomePagePinnedArticle.objects.filter(page_id=self.page_id)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.count() >= MAX_PINNED_ARTICLES:
            raise ValidationError("置顶文章最多 3 篇。")


class HomePageCarouselItem(Orderable):
    """One photo in the homepage carousel (焦点图, round 065)."""

    page = ParentalKey(
        "content.HomePage",
        on_delete=models.CASCADE,
        related_name="carousel_items",
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="图片",
        help_text="横图，建议 1600×700 以上。",
    )
    title = models.CharField("标题", max_length=60)
    link_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="链接到页面",
    )
    link_url = models.CharField(
        "或链接地址",
        max_length=200,
        blank=True,
        help_text="站内地址以 / 开头，比如 /tournaments/3/；站外地址以 https:// 开头。",
    )

    panels = [
        FieldPanel("image"),
        FieldPanel("title"),
        FieldPanel("link_page"),
        FieldPanel("link_url"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = "焦点图"
        verbose_name_plural = "焦点图"

    def clean(self):
        super().clean()
        url = self.link_url.strip()
        if (
            url
            and not (url.startswith("/") and not url.startswith("//"))
            and not url.startswith("https://")
        ):
            raise ValidationError(
                {"link_url": "站内地址以 / 开头，站外地址以 https:// 开头。"}
            )

    @property
    def url(self) -> str:
        if self.link_page_id and self.link_page.live:
            return self.link_page.url
        return self.link_url.strip()


class HomePage(SeoPageMixin, Page):
    """Site-unique homepage (design 5.1, 12.5.1)."""

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["content.ArticleIndexPage", "content.StandardPage"]

    content_panels = Page.content_panels + [
        InlinePanel(
            "carousel_items",
            label="焦点图",
            max_num=MAX_CAROUSEL_SLIDES,
            help_text="首页顶部轮播的图片。一张都没有时，用最近带封面的文章。",
        ),
        InlinePanel(
            "pinned_articles",
            label="置顶文章",
            max_num=MAX_PINNED_ARTICLES,
        ),
    ]

    def clean(self):
        super().clean()
        if self.pinned_articles.count() > MAX_PINNED_ARTICLES:
            raise ValidationError({"pinned_articles": "置顶文章最多 3 篇。"})

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        pinned = [
            rel.article
            for rel in self.pinned_articles.select_related(
                "article__category",
                "article__author",
            )
            if rel.article.live
        ][:MAX_PINNED_ARTICLES]
        if pinned:
            context["home_articles"] = pinned
        else:
            context["home_articles"] = list(
                ArticlePage.objects.live()
                .public()
                .select_related("category", "author")
                .order_by("-first_published_at", "-last_published_at")[
                    :HOME_ARTICLE_COUNT
                ]
            )
        from scrims.services import upcoming_scrims
        from tournaments.services import open_tournaments

        context["open_tournaments"] = open_tournaments()
        context["upcoming_scrims"] = upcoming_scrims()

        from content import home

        context["carousel"] = home.carousel_slides(self)
        context["picture_news"] = home.picture_news()
        context["news_list"] = home.news_list(pinned)
        context["calendar"] = home.scrim_calendar()
        context["event_cards"] = home.event_cards(
            context["open_tournaments"], context["upcoming_scrims"]
        )
        context["home_teams"] = home.teams()
        return context

    class Meta:
        verbose_name = "首页"


class ArticleIndexPage(SeoPageMixin, ReservedSlugMixin, Page):
    intro = RichTextField(
        "栏目介绍",
        blank=True,
        features=["bold", "italic", "link"],
    )

    parent_page_types = ["content.HomePage"]
    subpage_types = ["content.ArticlePage"]

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        articles = (
            ArticlePage.objects.live()
            .public()
            .descendant_of(self)
            .select_related("category", "author", "cover")
            .order_by("-first_published_at", "-last_published_at")
        )
        category_slug = (request.GET.get("category") or "").strip()
        if category_slug:
            articles = articles.filter(category__slug=category_slug)
        paginator = Paginator(articles, ARTICLES_PER_PAGE)
        page_obj = paginator.get_page(request.GET.get("page") or 1)
        query = request.GET.copy()
        query.pop("page", None)
        context["page_obj"] = page_obj
        context["articles"] = page_obj
        context["categories"] = ArticleCategory.objects.all()
        context["active_category"] = category_slug
        context["extra_query"] = query.urlencode()
        return context

    class Meta:
        verbose_name = "文章栏目"


class ArticlePage(SeoPageMixin, Page):
    seo_kind = "article"

    category = models.ForeignKey(
        ArticleCategory,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name="分类",
    )
    cover = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="封面",
    )
    summary = models.CharField("摘要", max_length=200, blank=True)
    body = StreamField(
        ARTICLE_BODY_BLOCKS,
        blank=True,
        verbose_name="正文",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_articles",
        verbose_name="作者",
    )
    comments_enabled = models.BooleanField(
        "开放评论",
        default=True,
        help_text="关闭后已有评论仍显示，只是不能再发。",
    )
    tournament = models.ForeignKey(
        "tournaments.Tournament",
        verbose_name="关联赛事",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="articles",
        help_text="选填。关联后这篇文章会显示在赛事页面上。",
    )

    parent_page_types = ["content.ArticleIndexPage"]
    subpage_types = []

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        # The news sidebar lists every category (round 065).
        context["categories"] = ArticleCategory.objects.all()
        # Design 5.6: the comment section, read-only for visitors; a signed-in
        # live render gets the interactive one (13.13.3).
        from comments.rendering import section_context

        user = getattr(request, "user", None)
        context.update(
            section_context(
                request,
                self,
                interactive=bool(user and user.is_authenticated),
                page_number=request.GET.get("comments"),
            )
        )
        return context

    base_form_class = ArticlePageForm

    content_panels = Page.content_panels + [
        FieldPanel("category"),
        FieldPanel("cover"),
        FieldPanel("summary"),
        FieldPanel("body"),
        FieldPanel("tournament"),
        FieldPanel("author"),
        FieldPanel("comments_enabled"),
    ]

    def get_share_image(self):
        return self.cover

    def get_share_description(self):
        return self.search_description or self.summary or None

    def save(self, *args, **kwargs):
        if not self.author_id and self.owner_id:
            self.author_id = self.owner_id
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = "文章"


class StandardPage(SeoPageMixin, ReservedSlugMixin, Page):
    body = StreamField(
        ARTICLE_BODY_BLOCKS,
        blank=True,
        verbose_name="正文",
    )

    parent_page_types = ["content.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "普通页面"
