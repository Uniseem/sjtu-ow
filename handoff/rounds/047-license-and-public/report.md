# 047 实现报告

## 结论

**许可证部分完成；改公开没做，等用户选。** 公开前检查发现，强制推送之前的旧提交在 GitHub 上仍然能按编号打开，上面有用户的真实姓名和邮箱。

## 公开前的检查

### 旧提交（有问题）

```
$ gh api repos/Uniseem/sjtu-ow/commits/7ec6a2a1fb4c21f698fc7e0b60a109f1ff0608d1 --jq '"\(.sha[0:7]) author=\(.commit.author.name) <\(.commit.author.email)>"'
7ec6a2a author=<真实姓名> <个人邮箱>
$ gh api repos/Uniseem/sjtu-ow/commits/9bc97f246961b715352571ff61095980595a654b --jq '"\(.sha[0:7]) author=\(.commit.author.name)"'
9bc97f2 author=<真实姓名>
```

（姓名和邮箱在报告里隐去。）

强制推送只是让 `main` 不再指向旧提交，**GitHub 上的对象不会马上删除**。私有仓库只有 Uniseem 能看，没关系；一公开，任何人拿到编号就能打开。043 的报告里就写着 `7ec6a2a`。

可选的处理方式：

| 方式 | 做法 | 代价 |
|---|---|---|
| **A. 换一个新仓库** | 现在的私有仓库改名（比如 `sjtu-ow-old`，保持私有），新建同名公开仓库 `Uniseem/sjtu-ow`，推送改写后的干净历史。新仓库里根本没有旧对象 | 旧仓库的 CI 运行记录留在旧仓库。旧仓库要删的话得用户自己删（我这边的 GitHub 令牌没有删除仓库的权限） |
| B. 请 GitHub 清理 | 按 GitHub「从仓库删除敏感数据」的流程联系支持，请他们清掉没被引用的提交，清完再公开 | 要等 GitHub 处理 |
| C. 直接公开 | — | 旧提交上的真实姓名和邮箱可被看到 |

### 其他检查（没问题）

**仓库内容**：邮箱只有测试用的 `Player@Example.com`；没有 IP 地址；本机路径在 022 报告里已经写成 `/Users/...`；搜不到真实姓名、个人邮箱、用户名。

**全部历史**（043 那次改写后的 42 个提交，逐个补丁搜）：搜不到真实姓名、个人邮箱、用户名；没有真实密钥，密码类的赋值全是测试值（`Correct-Horse-Battery-1`、`test-key`、`AKIAEXAMPLE` 等）。

**截图**：仓库里 21 张，看了最可能拍到个人信息的 6 张（注册、找回密码、基本资料、游戏 ID、联系方式、投稿者后台），都是测试数据（昵称「验收五乙」、`LiveFive#1234`、`QQ 123456789`）。

**依赖许可证**：77 个已安装的包里，唯一带限制的是 `certifi`（MPL-2.0）。MPL 只约束它自己的文件，我们没改也没放进仓库，不影响。没有 GPL、AGPL。

## 许可证

**`LICENSE.md`**：第一行 `Required Notice: Copyright 2026 Uniseem (https://github.com/Uniseem)`，后面是 PolyForm Strict 1.0.0 原文，从官方仓库的 1.0.0 标签下载。和官方文件逐字节一致：

```
$ tail -n +3 LICENSE.md | shasum -a 256
9eb48619fbc193ab7bb327b090cfcc703000265b83e670f81f231d0b1c43c56e  -
$ shasum -a 256 PolyForm-Strict-1.0.0.md
9eb48619fbc193ab7bb327b090cfcc703000265b83e670f81f231d0b1c43c56e
```

许可方写 Uniseem，不用真实姓名。

**PolyForm Strict 实际允许什么**（给用户的说明，以原文为准）：非商业用途的使用是允许的，包括个人学习研究和教育机构、公益组织的使用；**不允许分发、修改、基于它做新作品**；原文专门写了不限制合理使用。所以它挡不住「非商业地跑起来用」，也挡不住合理引用。

**`THIRD_PARTY_NOTICES.md`**：`static/vendor/` 下三个文件原样收录，不能被 PolyForm Strict 覆盖。Alpine.js 和 SortableJS 是 MIT，要求分发时保留版权声明——仓库一公开就是分发，所以附上原文（从对应版本的标签下载）。htmx 是 0BSD，不要求声明，一并列出。

**文档**：`README.md` 加「许可证」一节；设计新增 17.8（附录 D v1.5.11）；`AGENTS.md` 的依赖规则加上许可证检查，文档维护表加 `THIRD_PARTY_NOTICES.md`。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
213 files already formatted
```

211 → 213：新增的 `LICENSE.md` 和 `THIRD_PARTY_NOTICES.md`（ruff 也检查 Markdown）。没改代码，不重跑 pytest。

## 改动文件

```
LICENSE.md                      新建
THIRD_PARTY_NOTICES.md          新建
README.md                       许可证一节
docs/design.md                  17.8、附录 D
AGENTS.md                       依赖许可证；文档维护表
handoff/STATUS.md
handoff/rounds/047-license-and-public/
```
