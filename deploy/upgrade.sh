#!/usr/bin/env bash
# SJTU-OW 生产自动化升级脚本（12 号文档 11.2、M9）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.new.yml"
ENV_FILE="${SCRIPT_DIR}/../.env"

echo "=== SJTU-OW 自动化升级开始 ==="

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "错误：找不到 Compose 配置文件 $COMPOSE_FILE" >&2
    exit 1
fi

COMPOSE_CMD="docker compose -p sjtu-ow -f $COMPOSE_FILE"
if [[ -f "$ENV_FILE" ]]; then
    COMPOSE_CMD="$COMPOSE_CMD --env-file $ENV_FILE"
fi

# 1. 升级前安全热备份（自动保存至 data/backups/）
echo "1. 执行升级前数据热备份..."
$COMPOSE_CMD exec -T server backup || {
    echo "警告：容器未运行或备份命令执行失败，尝试以一次性容器执行备份..."
    $COMPOSE_CMD run --rm server backup || true
}

# 2. 构建最新镜像
echo "2. 构建最新镜像..."
$COMPOSE_CMD build

# 3. 执行数据库迁移
echo "3. 运行数据库模式迁移..."
$COMPOSE_CMD run --rm server migrate

# 4. 平滑重启各服务
echo "4. 重启应用容器服务..."
$COMPOSE_CMD up -d --remove-orphans

# 5. 冒烟健康检查
echo "5. 等待服务就绪并执行健康检查..."
MAX_RETRIES=15
SUCCESS=0
for i in $(seq 1 $MAX_RETRIES); do
    if $COMPOSE_CMD exec -T server reconcile > /dev/null 2>&1; then
        SUCCESS=1
        break
    fi
    echo "  等待服务启动中 ($i/$MAX_RETRIES)..."
    sleep 2
done

if [[ $SUCCESS -eq 1 ]]; then
    echo "=== 升级成功！所有服务已健康就绪 ==="
    $COMPOSE_CMD exec -T server reconcile
else
    echo "错误：升级后健康检查未能在预定时间内通过！" >&2
    exit 1
fi
