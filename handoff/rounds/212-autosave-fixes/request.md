# 212 自动保存收尾（T1、A1、A3、F2、F4、B6、D3、D2）

## 背景

210 全站复核（`handoff/rounds/210-full-review/review.md`）的建议修法顺序里，第 1 步是「202–207 自动保存的收尾，一起修」。211 插进来修了高严重度的 D1，本轮按 STATUS.md 做这八条，全部出自复核报告（编号即报告里的编号）：

- **T1**（中）：赛事自动保存的跨字段规则落错字段时，改动的那一项照样落库。`valid_changes` 只在 `NON_FIELD_ERRORS` 时才看 `autosave_together`（死代码），而 v7.10 起跨字段规则按设计落在单个字段上（`TournamentForm.clean` 报在 `registration_closes_at` / `roster_max`）。改「报名开始」越过截止：`opens` 单独 `update_fields` 落库 → 撞 `tournament_registration_window` 约束 → 新建/复制路径 `obj.save()` 没捕获 → IntegrityError 500、`autosave.js` 每 5 秒重试；编辑路径 `save_valid_fields` 捕获后返回 `saved=[]`，同一次请求里其它合法改动也丢了，页面却写「其余已保存」。复核还要求连带查 `ScrimForm` 有没有同类规则（已查：没有，`Scrim` 模型无约束、表单无 `clean`，写进报告）
- **A1**（中）：联系方式把类型改成已有的类型 → 500。唯一约束 `(user, type)` 含不在表单里的 `user`，`form.is_valid()` 跳过；`ContactMethodForm.save` 里 `full_clean()` 抛 `ValidationError`，自动保存分支没有 `try`
- **A3**（低）：`ContactMethodForm.autosave_together = ("type", "value")` 不起作用（同 T1 的根因）：只改类型、内容不匹配新类型时错误落在 `value` 上，`type` 单独落库绕过 `clean()`，库里出现「微信 12345」
- **F2**（中）：自动保存失败后每 5 秒无限重试，不看状态码、不退避；会话过期（302 → 登录页 200）、403、500 一个待遇，不提示重新登录；战队管理页是 multipart，每次重试都重传队标文件
- **F4**（低）：密钥框存过一次后明文留在 DOM 里，这张表单之后每次自动保存都把密钥再发一遍、服务端重新加密存一遍；`apply()` 只清 `values` 里点名的字段，设置页的自动保存分支不返回 `values`
- **B6**（低）：新建分类、成员分组时第一次改动若有错（撞名 slug、排序非数字）对象不建、`location` 为空，和 13.17「第一次改动就建好」不一致；赛事、内战、文章用 `new_from_valid_fields` 做到了
- **D3**（中）：两个人同时改同一篇文章/网站页面，后存的把先存的整个顶掉：自动保存发整张表单、不带修订号，`save_draft` 把表单里有效的字段套在这次请求读到的最新修订上，没有「我打开以后别人改过」的判断
- **D2**（中）：删分类只数页面行（`category.articles.count()`），草稿修订里引用的分类删得掉；删了以后那篇文章的编辑页、预览、定时上线全部 500（`get_latest_revision_as_object` → modelcluster 对 `on_delete=PROTECT` 直接抛）。违反设计 5.3「还有文章（包括草稿）在用的分类不能删除」

## 本轮范围

做：

1. `core/autosave.py` 的 `valid_changes`：`autosave_together` 里**任何一个字段有错误**时，整组字段这次都不存（不再只看 `NON_FIELD_ERRORS`）——一条改动同时修 T1、A3，也让 `TournamentForm` / `ContactMethodForm` / `CategoryForm` / `MemberGroupForm` 上现有的 `autosave_together` 全部生效
2. `ContactMethodForm` 加表单级唯一性检查（同一人同类型已有一条 → 错误落在 `type` 上），A1 的 500 消失；`save` 里的 `full_clean()` 保留作兜底
3. `static/js/autosave.js` 的失败处理（F2）：
   - 会话失效（非 JSON 的 200，即被跳去登录页）、401、403、404：认定为这次登录/权限的问题，**不再重试**，状态栏写「保存失败：登录状态已失效或没有权限，重新登录后再改」；这种失败不再拦住离开页面（`beforeunload`）
   - 网络错误、5xx、429：退避重试，5 秒起步逐次翻倍、封顶 60 秒；存好后归零
   - 表单里有已选文件的文件框（队标）：失败后**不自动重试**（避免反复重传文件），状态栏写明「保存失败，再改一次会重新尝试」
4. 设置页自动保存分支（`backoffice/views/settings.py`）：存过的密钥字段随响应返回 `values[字段]=""`，客户端保存后清空框里的明文（F4）
5. 分类、成员分组的新建改用 `new_from_valid_fields`：第一次改动就建行，有错的那几项不存、其余照存，`location` 照回（B6）
6. 草稿并发守卫（D3）：文章、网站页面、首页置顶、栏目介绍的编辑表单带隐藏 `latest_revision` 编号；保存（自动保存和整张提交都算）时发现和库里最新修订不一致就不存，回「别人在你打开以后改过了」；存好后响应把新修订号写回隐藏框。修订号没传（旧页面）时不拦
7. 删分类（D2）：计数从「页面行」扩到「页面行 + 最新草稿修订 + 已排定时上线的修订」里引用这个分类的文章；有一处引用就不给删，提示语照旧
8. 每条新规则配「拆掉就红」的测试，并做变异验证（把检查改坏确认测试红，再改回来）
9. 设计文档同步：13.17 补失败重试和并发守卫两句话，附录 D 记版本

明确不做：

- 210 复核的其它条目（S1、S2、T2、C1–C3……按顺序在 213 及以后）
- F8（几条测试只断言 JS 源码子串）本身不改；本轮 JS 的测试沿用现有的子串断言方式，在报告里注明这个弱点
- 不改变非自动保存路径的用户可见行为（表单错误长什么样、提示文案不动）
- 不加新依赖

## 任务

1. `core/autosave.py` `valid_changes`：`autosave_together` 组内任一字段出现在 `form.errors` 里，整组都不算可存
   - 验证：新测试——赛事编辑只改 `registration_opens_at` 越过截止 → 200，`opens` 没存、同请求的 `description` 存了、错误在；删掉 `TournamentForm.autosave_together` 这四行该测试要红（T9 顺带解决）。联系方式只改 `type` 使内容不匹配 → `type` 没存
2. `accounts/forms.py` `ContactMethodForm.clean`（或 `clean_type`）：同用户同类型已存在 → `type` 字段错误
   - 验证：新测试——带 `X-Autosave: 1` 把 QQ 那条的类型改成微信 → 200 + 字段错误，不再 500；非自动保存路径同样不 500
3. `static/js/autosave.js`：按上面第 3 条改 `save()` 的失败分支和 `pending()`
   - 验证：`core/tests/test_autosave_js.py`（或现有等价文件）补子串断言：退避封顶、永久失败不重试、含文件表单不重试、`pending()` 不算永久失败
4. `backoffice/views/settings.py` + `core/forms.py`：存过的密钥字段进 `values` 清空
   - 验证：新测试——填 SMTP 密码自动保存后响应 `values.smtp_password == ""`；再改别的字段，请求体里不再带密码（客户端行为由 `apply()` 现有逻辑保证，断言子串）
5. `backoffice/views/categories.py`、`backoffice/views/members.py` 新建分支：`new_from_valid_fields`
   - 验证：新测试——新建分类第一次改动是撞名 slug → 行建起来了、`location` 回了编辑地址、slug 没存、名称存了；成员分组同样（排序非数字）
6. `content/drafts.py` 加并发守卫 + 文章/页面/置顶/栏目介绍四处视图和模板接上隐藏 `latest_revision`
   - 验证：新测试——两个 client 各 GET 一次编辑页，交替自动保存不同字段：后存的（带旧修订号）被拒、提示「别人改过」，先存的还在；存好的响应里 `values.latest_revision` 是新编号，带着它能继续存
7. `backoffice/views/categories.py` 删除计数 + `content` 侧一个「分类被引用的文章数」的查询函数（页面行 ∪ 最新修订 ∪ 定时上线修订）
   - 验证：新测试——内容编辑自动保存新文章、编辑页选分类 X（只进草稿修订）→ 删 X 被拒并说出篇数； GET 编辑页不 500。改掉修订计数那一半，测试要红
8. 全部新检查做变异验证（逐处改坏 → 红 → 改回）
9. `docs/design.md`：13.17 补两句（重试退避与永久失败；草稿带修订号），附录 D 记 v7.15

## 验收标准

- `bash scripts/remote-check.sh` 全绿（ruff、Tailwind、pytest 分片、迁移检查、生产 `check --deploy`、Docker 构建）
- 每条新规则的变异验证记录在 `report.md`（改坏什么 → 哪条测试红）
- CI 推送后看结果
