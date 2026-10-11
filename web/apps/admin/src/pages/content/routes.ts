import type { RouteRecordRaw } from "vue-router"

export const contentRoutes: RouteRecordRaw[] = [
  { path: "/admin/articles/", name: "admin-articles", component: () => import("./ArticlesPage.vue"), meta: { section: "content", tab: "articles", title: "文章" } },
  { path: "/admin/articles/new/", name: "admin-article-new", component: () => import("./ArticleEditPage.vue"), meta: { section: "content", tab: "articles", title: "写文章" } },
  { path: "/admin/articles/:id(\\d+)/", name: "admin-article-edit", component: () => import("./ArticleEditPage.vue"), meta: { section: "content", tab: "articles", title: "编辑文章" } },
  { path: "/admin/articles/:id(\\d+)/preview/", name: "admin-article-preview", component: () => import("./ArticlePreviewPage.vue"), meta: { section: "content", tab: "articles", title: "预览草稿" } },
  { path: "/admin/articles/:id(\\d+)/revisions/", name: "admin-article-revisions", component: () => import("./ArticleRevisionsPage.vue"), meta: { section: "content", tab: "articles", title: "文章修订" } },
  { path: "/admin/articles/:id(\\d+)/revisions/:revision(\\d+)/", name: "admin-article-revision", component: () => import("./ArticleRevisionPage.vue"), meta: { section: "content", tab: "articles", title: "查看修订" } },
  { path: "/admin/categories/", name: "admin-categories", component: () => import("./CategoriesPage.vue"), meta: { section: "content", tab: "categories", title: "分类" } },
  { path: "/admin/categories/new/", name: "admin-category-new", component: () => import("./CategoryEditPage.vue"), meta: { section: "content", tab: "categories", title: "新建分类" } },
  { path: "/admin/categories/:id(\\d+)/", name: "admin-category-edit", component: () => import("./CategoryEditPage.vue"), meta: { section: "content", tab: "categories", title: "编辑分类" } },
  { path: "/admin/pages/", name: "admin-pages", component: () => import("./PagesPage.vue"), meta: { section: "content", tab: "pages", title: "网站页面" } },
  { path: "/admin/pages/pins/", name: "admin-home-pins", component: () => import("./HomePinsPage.vue"), meta: { section: "content", tab: "pages", title: "首页的置顶文章" } },
  { path: "/admin/pages/intro/", name: "admin-news-intro", component: () => import("./NewsIntroPage.vue"), meta: { section: "content", tab: "pages", title: "资讯栏目的介绍" } },
  { path: "/admin/pages/:id(\\d+)/", name: "admin-page-edit", component: () => import("./PlainPageEditPage.vue"), meta: { section: "content", tab: "pages", title: "编辑页面" } },
  { path: "/admin/images/", name: "admin-images", component: () => import("./ImagesPage.vue"), meta: { section: "content", tab: "images", title: "图片" } },
  { path: "/admin/images/upload/", name: "admin-image-upload", component: () => import("./ImageUploadPage.vue"), meta: { section: "content", tab: "images", title: "上传图片" } },
  { path: "/admin/images/collections/", name: "admin-collections", component: () => import("./CollectionsPage.vue"), meta: { section: "content", tab: "images", title: "集合", superuser: true } },
  { path: "/admin/images/:id(\\d+)/", name: "admin-image-edit", component: () => import("./ImageEditPage.vue"), meta: { section: "content", tab: "images", title: "编辑图片" } },
]
