# 176 还有文章在用的分类不能删（报告）

## 做了什么

1. `content/wagtail_hooks.py`
   - `ArticleCategoryPermissionPolicy`：分类下还有文章时，对这个分类的「删除」权限为假（注册成这个模型的权限策略）。Wagtail 的批量删除逐个问这个权限，所以会跳过它
   - `ArticleCategoryIndexView.get_delete_url`：列表只问模型级权限（和 115 内战的情况一样），在用的分类不给删除链接
   - `ArticleCategoryDeleteView.dispatch`：直接打开删除地址时提示「还有 N 篇文章在「…」里，先把它们改到别的分类再删。」并回到编辑页
2. 设计 v6.59（5.3）
3. `content/tests/test_category_delete.py`（4 条，以内容编辑身份）

## 怎么查的

全站 `on_delete=PROTECT` 的外键 6 个：报名的战队、名单里的用户、评论作者、文章作者（指向战队或用户，后台删不了）；排版设置引用字体（表单在不是「自定义」时会清掉字体，删除前也检查）；文章引用分类——就是这一个会出事。临时脚本（没提交）：

```
GET 200 说被引用
POST 500 category still: True article still: True
```

写测试时第一版跳回编辑页用了 `self.get_edit_url()`，删除视图没有这个方法，测试抓到了 500；改用分类的片段视图集的地址名。

## 命令输出

变异（测试机，4 处，全部被抓到）：

```
baseline green, 3 tests
caught bulk delete asks nothing -> test_bulk_delete_skips_it
caught policy not registered -> test_bulk_delete_skips_it
caught the list offers it anyway -> test_only_empty_categories_offer_delete
caught the delete page goes ahead -> test_a_used_category_says_why_and_stays
restored and green; missed: none
```

整组检查（测试机）：

```
1649 条测试分成 4 片
分片 1：413 passed in 37.98s
分片 2：412 passed in 37.39s
分片 3：412 passed in 44.36s
分片 4：412 passed in 38.93s
== 全部通过 (05:50:01)
```

演示站升级后，在服务器上以演示站的内容编辑「林间小鹿」（测试客户端）：

```
在用的分类: 公告 4 篇；列表里有删除: False
提交删除: 302 /admin/snippets/content/articlecategory/edit/1/ 分类还在: True
```
