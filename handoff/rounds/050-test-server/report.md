# 050 实现报告

## 结论

**完成。** 测试机的信息核对后写进了 `AGENTS.md`，上线计划写进了 `STATUS.md`。没有部署，也没改服务器。

## 核对

### 域名

开发机本地的 DNS 被代理软件接管，返回的是代理的虚拟地址 `198.18.1.9`，不能用。改用公共 DNS（Google 的 DNS-over-HTTPS）：

```
sjtu.ow-shanghaiuniversity.com.  CNAME  sjtu-ow-wesite-china-mainland-full-optimized.anylocate.cc.
sjtu-ow-wesite-china-mainland-full-optimized.anylocate.cc.  A  185.99.135.224
```

中间经过一个线路优化服务的 CNAME。这类服务可能按访问者地区返回不同的 IP，**如果证书机构（在海外）查到的不是这台机器，HTTP 验证会失败**。所以带上不同来源的网段各查一次：

```
交大 (202.120.0.0/16): 185.99.135.224
国内 (114.114.114.0/24): 185.99.135.224
美国 (8.8.8.0/24): 185.99.135.224
海外 (1.1.1.0/24): 185.99.135.224
```

全部一致。没有 IPv6 记录。

### 登录与机器

SSH 密钥登录成功。Debian 12，8 核，11 GiB 内存，系统盘 197G、已用 18%，Docker 29.8，Compose v5.5.1。

**机器上已经有别的东西**：

- 另一套 Docker Compose 项目在跑（5 个容器，对外占用 8091 端口）
- `/opt` 下有一个服务器监控探针
- 80、443 空闲；`/srv` 是空的

所以 `AGENTS.md` 写明了只动 `/srv/sjtu-ow` 和本项目的容器，不做全局清理。

**安全设置**（只读查看，没改）：

```
permitrootlogin yes
pubkeyauthentication yes
passwordauthentication yes
```

主机防火墙没有规则（`INPUT ACCEPT`）。用户说用密钥登录，但**密码登录仍然开着**。建议关掉，但这是改系统安全配置，改错了会把自己锁在外面，留给用户决定。

### 证书和跳转

`deploy/Caddyfile` 的站点地址来自 `CADDY_SITE_ADDRESS`。填域名本身（不带 `http://`）时 Caddy 自动申请证书，并默认把 HTTP 跳到 HTTPS。`.env.example` 里现在的值是 `http://localhost`，部署时要改。**跳转是否生效要部署后实测**，已写进 `AGENTS.md`。

## 改动文件

```
AGENTS.md                      新增「测试机与部署」
handoff/STATUS.md              上线计划
handoff/rounds/050-test-server/
```
