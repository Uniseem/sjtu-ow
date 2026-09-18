# 064 复核结果

## 结论

**通过。**

## 逐项

| 要求 | 结果 |
|---|---|
| 设计先改 | 数据卷表 `static` 一行，附录 D v1.5.15 |
| worker 挂 static | 测试机 `docker inspect`：`/app/staticfiles rw=false` |
| 清单跟上新版本 | 单元测试两种存储各一遍；5/5 变异被抓到 |
| 测试机上真的触发 | 发布后 33 秒静态页更新，失败记录 0 |

## 判断里最没把握的

- **重新读清单用的是 Django 没写进文档的接口**：`load_manifest()` 返回 `(hashed_files, manifest_hash)`、实例上的 `hashed_files` / `manifest_hash` 两个属性。Django 6 的 `ManifestFilesMixin.__init__` 就是这么写的；以后升级 Django 如果改了，参数化测试会红（两种存储都会）
- **按 `(mtime_ns, size)` 判断变没变**：`collectstatic` 是整个重写清单文件的，时间一定会变。同一纳秒内写两次、大小又一样的情况不考虑
- **竞争本身没在服务器上复现**，只有单元测试
- 每次渲染多一次 `stat`，全量生成 9 页可以忽略；页面多了也只是每页一次系统调用
