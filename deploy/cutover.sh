#!/usr/bin/env bash
# SJTU-OW 生产割接自动化执行脚本（12 号文档 8.4、M10/M11）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NEW_COMPOSE="${SCRIPT_DIR}/docker-compose.new.yml"
OLD_COMPOSE="${SCRIPT_DIR}/docker-compose.yml"
OLD_COMPOSE_VPS="${SCRIPT_DIR}/docker-compose.vps.yml"
ENV_FILE="${REPO_DIR}/.env"

echo "============================================="
echo "   SJTU-OW 生产停机割接自动化流水线"
echo "============================================="

# 0. 验证环境配置
if [[ ! -f "$NEW_COMPOSE" ]]; then
    echo "错误: 找不到新栈 Compose 文件 $NEW_COMPOSE" >&2
    exit 1
fi

COMPOSE_NEW="docker compose -f $NEW_COMPOSE"
if [[ -f "$ENV_FILE" ]]; then
    COMPOSE_NEW="$COMPOSE_NEW --env-file $ENV_FILE"
fi

# 1. 确认割接意向
echo "警告: 即将执行停机割接流水线！旧栈写入服务将被停止，数据将导入新栈。"
read -p "是否确认开始执行割接? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "割接已取消。"
    exit 0
fi

START_TIME=$(date +%s)

# 2. 停用旧栈写入服务（进入只读维护）
echo "[1/6] 停止旧栈写入服务..."
if docker compose -f "$OLD_COMPOSE" -f "$OLD_COMPOSE_VPS" ps -q web 2>/dev/null | grep -q .; then
    docker compose -f "$OLD_COMPOSE" -f "$OLD_COMPOSE_VPS" stop web worker || true
else
    echo "  旧栈服务未在运行，继续割接流程..."
fi

# 3. 创建旧库最终快照
echo "[2/6] 创建旧库只读快照..."
LEGACY_DB="/srv/sjtu-ow/data/sjtuow.sqlite3"
SNAPSHOT_DB="/srv/sjtu-ow/data/legacy-final-$(date +%Y%m%d%H%M%S).sqlite3"

if [[ -f "$LEGACY_DB" ]]; then
    cp "$LEGACY_DB" "$SNAPSHOT_DB"
    echo "  已创建最终快照: $SNAPSHOT_DB"
else
    echo "  注意: 未检测到宿主 $LEGACY_DB，使用临时空白测试快照"
    SNAPSHOT_DB="/tmp/legacy-empty.sqlite3"
    touch "$SNAPSHOT_DB"
fi

# 4. 初始化新库模式
echo "[3/6] 初始化新栈数据库模式..."
$COMPOSE_NEW run --rm server /srv/sjtuow/sjtuow migrate

# 5. 执行全领域数据导入
echo "[4/6] 导入存量历史数据..."
if [[ -s "$SNAPSHOT_DB" ]]; then
    $COMPOSE_NEW run --rm -v "$(realpath "$SNAPSHOT_DB")":/tmp/legacy.sqlite3:ro server /srv/sjtuow/sjtuow import /tmp/legacy.sqlite3
fi

# 6. 全量数据对账自检（门禁红线）
echo "[5/6] 运行对账自检与一致性核验..."
if [[ -s "$SNAPSHOT_DB" ]]; then
    $COMPOSE_NEW run --rm -v "$(realpath "$SNAPSHOT_DB")":/tmp/legacy.sqlite3:ro server /srv/sjtuow/sjtuow reconcile /tmp/legacy.sqlite3
else
    $COMPOSE_NEW run --rm server /srv/sjtuow/sjtuow reconcile
fi

# 7. 启动新栈全量容器集群
echo "[6/6] 启动新栈应用集群 (Server + Worker + SSR + Caddy)..."
$COMPOSE_NEW up -d

# 8. 冒烟健康检查
echo "等待新栈就绪与健康检查..."
MAX_RETRIES=20
READY=0
for i in $(seq 1 $MAX_RETRIES); do
    if $COMPOSE_NEW exec -T server /srv/sjtuow/sjtuow reconcile > /dev/null 2>&1; then
        READY=1
        break
    fi
    echo "  等待应用响应中 ($i/$MAX_RETRIES)..."
    sleep 2
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [[ $READY -eq 1 ]]; then
    echo "============================================="
    echo "   割接成功完成！总停机耗时: ${DURATION} 秒"
    echo "   新站已正式对外提供服务！"
    echo "============================================="
else
    echo "错误: 新栈健康检查未能在预定时间内通过！请检查容器日志并按 docs/cutover.md 执行回滚！" >&2
    exit 1
fi
