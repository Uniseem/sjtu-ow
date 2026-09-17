# 048 实现报告

## 结论

**信息收齐，工单草稿写好了，等用户提交。** GitHub 文档写明**他们只帮忙清理敏感数据**，姓名和邮箱算不算要看他们判断，有被拒的可能。

> **049 轮更正**：用户改选了「旧仓库改名保持私有，新建仓库公开」，这份工单**不需要提交**。见 049 报告。

## GitHub 要什么

GitHub 文档「从仓库删除敏感数据」（Removing sensitive data from a repository）一节的要求，通过 <https://support.github.com> 提交：

1. 所有者和仓库名
2. 受影响的合并请求数量
3. 改写工具报告的「First Changed Commit(s)」
4. 如果有孤立的 LFS 对象，要说明

GitHub 会做的：处理受影响的合并请求、在服务器上跑垃圾回收删掉数据、清除缓存页面。

**限制**（文档原意）：GitHub 支持不会删除非敏感数据；只在「换掉泄露的凭据也解决不了风险」时才帮忙清理。姓名和邮箱没有「换凭据」这个选项，但它们算不算 GitHub 眼里的敏感数据，没有把握。

## 收集到的信息

```
$ gh api repos/Uniseem/sjtu-ow --jq '"forks=\(.forks_count) private=\(.private)"'
forks=0 private=true
$ gh api "repos/Uniseem/sjtu-ow/pulls?state=all" --jq 'length'
0
$ git rev-list --max-parents=0 7ec6a2a1fb4c21f698fc7e0b60a109f1ff0608d1
9bc97f246961b715352571ff61095980595a654b
$ git rev-list --count 7ec6a2a1fb4c21f698fc7e0b60a109f1ff0608d1
41
```

仓库根目录没有 `.gitattributes`，没用 LFS。

改写用的是 `git filter-branch`，不是 GitHub 文档里的 `git-filter-repo`，所以没有「First Changed Commit」这行输出。改的是作者信息，从第一个提交起就变了，所以**第一个被改的提交就是旧的根提交** `9bc97f2`，旧分支头是 `7ec6a2a`，中间一共 41 个。

## 工单草稿

用户在 <https://support.github.com> 提交。英文，GitHub 支持处理得快一些：

```
Subject: Purge dereferenced commits containing personal information (Uniseem/sjtu-ow)

Hello,

I rewrote the history of Uniseem/sjtu-ow to remove my real name and personal
email address from the author and committer fields of every commit, and
force-pushed main. The old commits are no longer referenced by any branch or
tag, but they can still be opened on GitHub by SHA and show my personal
information. The repository is private for now; I would like to make it
public once these objects are gone. Unlike a leaked credential, this cannot
be mitigated by rotation.

- Repository: Uniseem/sjtu-ow
- Affected pull requests: 0 (the repository has no pull requests and no forks)
- First changed commit: 9bc97f246961b715352571ff61095980595a654b
  (the root commit; the rewrite changed the author of all 41 commits, up to
  the old head 7ec6a2a1fb4c21f698fc7e0b60a109f1ff0608d1)
- Rewrite tool: git filter-branch (author/committer only; file contents unchanged)
- LFS objects: none

Could you please run garbage collection and remove cached views so these
commits can no longer be viewed?

Thank you.
```

## GitHub 清理完之后

1. 验证：`gh api repos/Uniseem/sjtu-ow/commits/7ec6a2a1fb4c21f698fc7e0b60a109f1ff0608d1` 应该返回找不到，`9bc97f2` 同样
2. 两个都找不到了，再把仓库改公开
3. **如果 GitHub 拒绝**：回到 047 报告里的方式 A——现在的仓库改名保持私有，新建同名公开仓库推送干净的历史

## 改动文件

```
handoff/STATUS.md
handoff/rounds/048-await-github-cleanup/
```
