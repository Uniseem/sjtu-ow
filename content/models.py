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
HOME_ARTICLE_COUNT = 3

# Slugs that would collide with Django routes registered before wagtail_urls
# (design 13.4). Enforced on HomePage children only.
RESERVED_CHILD_SLUGS = frozenset(
    {
        "admin",
        "accounts",
        "documents",
        "me",
        "api",
        "tournaments",
        "lfg",
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


class HomePage(SeoPageMixin, Page):
    """Site-unique homepage (design 5.1, 12.5.1)."""

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["content.ArticleIndexPage", "content.StandardPage"]

    content_panels = Page.content_panels + [
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
        # M4 / M6 / M3 data hooks: leave keys in context so templates stay put.
        context["open_tournaments"] = None
        context["upcoming_scrims"] = None
        # Anonymous (and prerendered) pages show 「登录后查看」; the signed-in
        # count arrives through the home-lfg slot (design 13.13.3).
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            from lfg import services as lfg_services

            context["lfg_open_count"] = lfg_services.open_count()
        else:
            context["lfg_open_count"] = None
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
    # M4: add tournament = ForeignKey("tournaments.Tournament", null=True,
    # blank=True, on_delete=SET_NULL, related_name="articles",
    # verbose_name="关联赛事"). Tournament does not exist yet; do not add a
    # placeholder FK.

    parent_page_types = ["content.ArticleIndexPage"]
    subpage_types = []
    base_form_class = ArticlePageForm

    content_panels = Page.content_panels + [
        FieldPanel("category"),
        FieldPanel("cover"),
        FieldPanel("summary"),
        FieldPanel("body"),
        FieldPanel("author"),
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
