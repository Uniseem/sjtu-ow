# 049 实现报告

## 结论

**完成。** `github.com/Uniseem/sjtu-ow` 现在是公开的全新仓库，里面没有任何带真实身份的旧提交。旧仓库改名为 `sjtu-ow-old`，保持私有。

## 过程

### 1. 改名

```
$ gh repo view Uniseem/sjtu-ow-old --json name
GraphQL: Could not resolve to a Repository with the name 'Uniseem/sjtu-ow-old'. (repository)
$ gh repo rename sjtu-ow-old --repo Uniseem/sjtu-ow --yes
$ gh repo view Uniseem/sjtu-ow-old --json name,visibility,url
{"name":"sjtu-ow-old","url":"https://github.com/Uniseem/sjtu-ow-old","visibility":"PRIVATE"}
```

先确认新名字没被占用。

### 2. 新建（先私有）并推送

```
$ gh repo create Uniseem/sjtu-ow --private --description "上海交通大学守望先锋社区网站（Wagtail/Django）正式版"
https://github.com/Uniseem/sjtu-ow
$ git push -u origin main
 * [new branch]      main -> main
```

本地的远程地址没变，改名后旧名字的重定向被新仓库取代，直接指向新仓库。

### 3. 公开前验证

**确实是新仓库，不是改名后的旧仓库**：

```
id=1374722277 created=2026-09-17T16:24:22Z private=true
old id=1374637555 created=2026-09-17T15:19:34Z private=true
```

（时间是 UTC。）

**旧提交查不到**，完整编号和短编号都试了：

```
No commit found for SHA: 7ec6a2a1fb4c21f698fc7e0b60a109f1ff0608d1 (HTTP 422)
No commit found for SHA: 9bc97f246961b715352571ff61095980595a654b (HTTP 422)
No commit found for SHA: 7ec6a2a (HTTP 422)
```

**41 个旧提交逐个查**：

```
旧提交 41 个：新仓库里找到 0 个，找不到 41 个
```

**全部提交的身份**：

```
47 Uniseem <325086315+Uniseem@users.noreply.github.com> / Uniseem <325086315+Uniseem@users.noreply.github.com>
463bb3e 048: 准备请 GitHub 清理旧提交
```

47 个和本地 `git rev-list --count HEAD` 一致。

### 4. 改公开

```
$ gh repo edit Uniseem/sjtu-ow --visibility public --accept-visibility-change-consequences
PUBLIC https://github.com/Uniseem/sjtu-ow license=Other
PRIVATE        ← sjtu-ow-old
```

GitHub 不认识 PolyForm Strict，许可证显示为「Other」，不影响。

### 5. 从外面验证（不带登录）

```
200  https://github.com/Uniseem/sjtu-ow
200  https://github.com/Uniseem/sjtu-ow/commit/463bb3e
404  https://github.com/Uniseem/sjtu-ow/commit/7ec6a2a1fb4c21f698fc7e0b60a109f1ff0608d1
404  https://github.com/Uniseem/sjtu-ow/commit/7ec6a2a
404  https://github.com/Uniseem/sjtu-ow/commit/9bc97f246961b715352571ff61095980595a654b
404  https://github.com/Uniseem/sjtu-ow-old
Required Notice: Copyright 2026 Uniseem (https://github.com/Uniseem)

# PolyForm Strict License 1.0.0
--- 公开 API（不带令牌）:
  "message": "No commit found for SHA: 7ec6a2a1fb4c21f698fc7e0b60a109f1ff0608d1",
"login": "Uniseem"
```

旧仓库对外是 404（私有仓库对无权限的人一律 404）。贡献者只有 Uniseem。

## 验证中踩的坑

第一次写外部验证脚本时，循环变量名叫 `path`。**zsh 里 `path` 和 `PATH` 是绑定的**，一赋值就把 `PATH` 覆盖了，`curl` 和 `head` 全部「command not found」。改名重跑。这类错误结果是全部失败，不会误判成通过，但值得记一笔。

## 还剩的

- `sjtu-ow-old` 里仍有旧提交，只有 Uniseem 能看到。**要删由用户自己删**（设置 → Danger Zone → Delete this repository）；我这边的令牌没有删除仓库的权限
- 048 的工单不用提交了

## 改动文件

```
handoff/STATUS.md
handoff/rounds/048-await-github-cleanup/report.md   加更正说明
handoff/rounds/049-new-public-repo/
```
