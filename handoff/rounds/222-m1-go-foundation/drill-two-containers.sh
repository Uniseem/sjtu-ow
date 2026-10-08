#!/bin/sh
# 222 轮：两个容器共享数据卷，跨容器的 flock 是否有效（13 号文档 C 节）。
# api 和 worker 将来是两个容器挂同一个 data 卷；220 轮 E3 只验过两个进程。
# 用真实的 WriteTx（server/tools/txhammer，静态二进制）压，caddy:2.10-alpine 容器（测试机上现成）跑。
# 在测试机上经 remote-check.sh run 执行：go 和 docker 都在，编译也在测试机做。
set -eu

dir=/tmp/sjtuow-flock-drill
rm -rf "$dir"
mkdir -p "$dir/data"
cleanup() {
  docker rm -f sjtuow-flock-a sjtuow-flock-b >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== 在测试机上编译 txhammer（CGO 关，静态二进制）"
cd server
CGO_ENABLED=0 go build -trimpath -o "$dir/txhammer" ./tools/txhammer

echo "== 初始化"
docker run --rm -v "$dir:/w" --entrypoint /w/txhammer caddy:2.10-alpine -mode init -db /w/data/drill.sqlite

echo "== 两个容器同时压（各 2000 步、每容器 4 个并发）"
start=$(date +%s)
docker run -d --name sjtuow-flock-a -v "$dir:/w" --entrypoint /w/txhammer caddy:2.10-alpine \
  -mode work -db /w/data/drill.sqlite -steps 2000 -conc 4 >/dev/null
docker run -d --name sjtuow-flock-b -v "$dir:/w" --entrypoint /w/txhammer caddy:2.10-alpine \
  -mode work -db /w/data/drill.sqlite -steps 2000 -conc 4 >/dev/null
code_a=$(docker wait sjtuow-flock-a)
code_b=$(docker wait sjtuow-flock-b)
elapsed=$(( $(date +%s) - start ))

echo "-- 容器 a（退出码 $code_a）"
docker logs sjtuow-flock-a
echo "-- 容器 b（退出码 $code_b）"
docker logs sjtuow-flock-b

echo "== 核对"
# txhammer -steps 2000 -conc 4：每个容器 4×500 = 2000 步，两个容器共 4000
out=$(docker run --rm -v "$dir:/w" --entrypoint /w/txhammer caddy:2.10-alpine -mode verify -db /w/data/drill.sqlite)
echo "$out"

[ "$code_a" = 0 ] && [ "$code_b" = 0 ] || { echo "有容器非零退出"; exit 1; }
echo "$out" | grep -q '^counter=4000 log_rows=4000$' || { echo "计数对不上（应 4000/4000）"; exit 1; }
docker logs sjtuow-flock-a 2>&1 | grep -q 'failed=0' || { echo "容器 a 有失败步"; exit 1; }
docker logs sjtuow-flock-b 2>&1 | grep -q 'failed=0' || { echo "容器 b 有失败步"; exit 1; }
echo "耗时 ${elapsed}s：两容器共享数据卷、WriteTx 的跨进程 flock 全程零 SQLITE_BUSY、零丢更新"
echo FLOCK-DRILL-OK
