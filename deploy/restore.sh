#!/usr/bin/env bash
# SJTU-OW 生产灾难恢复与还原脚本（12 号文档 473、M9）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.new.yml"
ENV_FILE="${SCRIPT_DIR}/../.env"

if [[ $# -lt 1 ]]; then
    echo "用法: $0 <backup-archive.tar.gz> [--yes]"
    echo "提示: 默认仅进行归档完整性与校验和演练 (dry-run)；追加 --yes 参数将执行真正替换。"
    exit 2
fi

ARCHIVE_PATH="$1"
APPLY_FLAG="${2:-}"

if [[ ! -f "$ARCHIVE_PATH" ]]; then
    echo "错误: 备份归档文件不存在: $ARCHIVE_PATH" >&2
    exit 1
fi

COMPOSE_CMD="docker compose -f $COMPOSE_FILE"
if [[ -f "$ENV_FILE" ]]; then
    COMPOSE_CMD="$COMPOSE_CMD --env-file $ENV_FILE"
fi

echo "=== SJTU-OW 备份恢复演练与还原 ==="
echo "目标归档: $ARCHIVE_PATH"

# 1. 演练校验
echo "1. 执行完整性校验 (Dry Run)..."
docker run --rm \
    -v "$(dirname "$(realpath "$ARCHIVE_PATH")")":/archive:ro \
    -v /tmp/sjtuow-dryrun:/srv/sjtuow/data \
    --entrypoint /srv/sjtuow/sjtuow \
    sjtu-ow-server:latest restore "/archive/$(basename "$ARCHIVE_PATH")" || {
        echo "警告: 本地未检索到 sjtu-ow-server:latest 镜像，尝试使用 Compose 运行演练..."
        $COMPOSE_CMD run --rm -v "$(realpath "$ARCHIVE_PATH")":/tmp/backup.tar.gz:ro server /srv/sjtuow/sjtuow restore /tmp/backup.tar.gz
    }

if [[ "$APPLY_FLAG" != "--yes" ]]; then
    echo "演练已完成，归档有效。未执行任何实际替换。若需正式恢复，请执行: $0 $ARCHIVE_PATH --yes"
    exit 0
fi

echo ""
echo "警告: 即将执行真正的数据还原替换！"
read -p "确认继续操作吗? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "操作已取消。"
    exit 0
fi

# 2. 停止当前服务以防写入冲突
echo "2. 停止正在运行的应用服务..."
$COMPOSE_CMD stop server worker web || true

# 3. 真正执行恢复
echo "3. 恢复数据库与媒体目录..."
$COMPOSE_CMD run --rm -v "$(realpath "$ARCHIVE_PATH")":/tmp/backup.tar.gz:ro server /srv/sjtuow/sjtuow restore /tmp/backup.tar.gz --yes

# 4. 重启服务
echo "4. 重启应用容器..."
$COMPOSE_CMD up -d

# 5. 校验健康状态
echo "5. 校验恢复后服务自检..."
sleep 3
$COMPOSE_CMD exec -T server /srv/sjtuow/sjtuow reconcile

echo "=== 灾备恢复成功完成！ ==="
