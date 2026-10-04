# 164 服务器上验证字体处理，记下 159、163 踩到的坑（报告）

## 做了什么

1. 在演示站上跑了一次字体处理（脚本在服务器上用 `manage.py shell` 执行，跑完删掉了脚本）：`core.fonts.services.create_family()` 建「验证字体164」（来源「网址下载」，开源授权），`add_face_from_url()` 下载 Barlow Regular（Google Fonts 仓库，SIL OFL），由 worker 切片；轮询状态，检查分片文件，再 `delete_family()`
2. `handoff/REVIEW-GUIDE.md`：064 那段后面加「164 轮补充」
3. `AGENTS.md`「已知的坑」加五条（163 两条加一条方法，159 两条）

## 命令输出

演示站：

```
排队: 1 400 normal pending
等了约 5 秒，状态: ready 进度: 100 错误: 无
分片: 2 总字节: 24428 字形: 525
分片文件都在: True ['fonts/1/400-000.b831757b.woff2', 'fonts/1/400-001.e9979ced.woff2']
删除后还在: False 文件还在: False
```

脚本跑在 `web` 容器里，切片由 `worker` 容器做（`add_face_from_url` 只排队），所以「分片文件都在」说明 worker 写进了两个容器共享的 media 卷。

写 AGENTS 时 Git Bash 的 heredoc 又吃掉了一层反斜杠，「`\n`」变成了真换行，用编辑工具改回来了（这个坑 AGENTS 里本来就有）。

整组检查（测试机，只改了文档）：见下。

```
1618 条测试分成 4 片
分片 1：405 passed in 35.50s
分片 2：405 passed in 37.12s
分片 3：404 passed in 36.42s
分片 4：404 passed in 34.88s
== 全部通过 (02:27:43)
```
