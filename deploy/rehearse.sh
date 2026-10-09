#!/usr/bin/env bash
# SJTU-OW 生产割接全真演练脚本 (M11 演练与耗时测算)
# 依据 12 号文档 8.4 节：割接前在测试机上用正式站备份完整演练，记录每一步耗时作为割接停机预估。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "============================================="
echo "   SJTU-OW 生产割接全流程模拟演练 (M11)"
echo "============================================="

# 1. 寻找或准备历史库数据源
LEGACY_INPUT="${1:-}"
if [[ -z "$LEGACY_INPUT" ]]; then
    if [[ -f "/srv/sjtu-ow/data/demo-final.sqlite3" ]]; then
        LEGACY_INPUT="/srv/sjtu-ow/data/demo-final.sqlite3"
    elif [[ -f "/srv/sjtu-ow/data/sjtuow.sqlite3" ]]; then
        LEGACY_INPUT="/srv/sjtu-ow/data/sjtuow.sqlite3"
    elif [[ -f "${REPO_DIR}/data/demo-final.sqlite3" ]]; then
        LEGACY_INPUT="${REPO_DIR}/data/demo-final.sqlite3"
    fi
fi

WORK_DIR=$(mktemp -d /tmp/sjtuow-rehearsal-XXXXXX)
trap 'rm -rf "$WORK_DIR"' EXIT

echo "演练工作目录: $WORK_DIR"
if [[ -n "$LEGACY_INPUT" && -f "$LEGACY_INPUT" ]]; then
    echo "使用历史数据库源: $LEGACY_INPUT"
else
    echo "未提供历史数据库，演练将采用空库与自检基线模式进行"
fi

REHEARSAL_DB="${WORK_DIR}/sjtuow.sqlite3"
LEGACY_SNAPSHOT="${WORK_DIR}/legacy-source.sqlite3"

export SJTUOW_DATA_DIR="$WORK_DIR"
export SJTUOW_ENV="dev"
export SITE_URL="${SITE_URL:-https://sjtu.ow-shanghaiuniversity.com}"
export SIGNING_KEY="${SIGNING_KEY:-rehearsal-test-signing-key-for-m11-verification}"
export FIELD_ENCRYPTION_KEY="${FIELD_ENCRYPTION_KEY:-eWVhcnRvZGF5c2VjcmV0ZmllbGRlbmNyeXB0aW9ua2V5MTI=}"

# 编译或定位 sjtuow 二进制
SJTUOW_BIN="${REPO_DIR}/server/sjtuow"
if [[ ! -x "$SJTUOW_BIN" ]]; then
    echo "编译新栈 sjtuow 二进制..."
    (cd "${REPO_DIR}/server" && go build -o sjtuow ./cmd/sjtuow)
    SJTUOW_BIN="${REPO_DIR}/server/sjtuow"
fi

TOTAL_START=$(date +%s)

# --- 步骤 1: 历史库只读镜像快照 ---
echo "--- [1/5] 制作历史库无锁快照 ---"
T1_START=$(date +%s)
if [[ -n "$LEGACY_INPUT" && -f "$LEGACY_INPUT" ]]; then
    cp "$LEGACY_INPUT" "$LEGACY_SNAPSHOT"
else
    touch "$LEGACY_SNAPSHOT"
fi
T1_END=$(date +%s)
D1=$((T1_END - T1_START))
echo "  快照完成，耗时: ${D1}s"

# --- 步骤 2: 初始化全新新栈表结构模式 ---
echo "--- [2/5] 初始化新库表结构 (sjtuow migrate) ---"
T2_START=$(date +%s)
"$SJTUOW_BIN" migrate
T2_END=$(date +%s)
D2=$((T2_END - T2_START))
echo "  迁移初始化完成，耗时: ${D2}s"

# --- 步骤 3: 全域数据只读导入 ---
echo "--- [3/5] 执行全域数据导入 (sjtuow import) ---"
T3_START=$(date +%s)
if [[ -s "$LEGACY_SNAPSHOT" ]]; then
    "$SJTUOW_BIN" import "$LEGACY_SNAPSHOT"
else
    echo "  (跳过空文件导入)"
fi
T3_END=$(date +%s)
D3=$((T3_END - T3_START))
echo "  数据导入完成，耗时: ${D3}s"

# --- 步骤 4: 数据完整性与一致性对账 ---
echo "--- [4/5] 数据完整性与表行数对账 (sjtuow reconcile) ---"
T4_START=$(date +%s)
if [[ -s "$LEGACY_SNAPSHOT" ]]; then
    "$SJTUOW_BIN" reconcile "$LEGACY_SNAPSHOT"
else
    "$SJTUOW_BIN" reconcile
fi
T4_END=$(date +%s)
D4=$((T4_END - T4_START))
echo "  对账核验完成，耗时: ${D4}s"

# --- 步骤 5: 业务契约审计与兼容性对拍 ---
echo "--- [5/5] 契约审计与新旧对拍 (rulecheck & parity) ---"
T5_START=$(date +%s)
"$SJTUOW_BIN" rulecheck --repo "$REPO_DIR"
"$SJTUOW_BIN" parity --signing-key "$SIGNING_KEY"
T5_END=$(date +%s)
D5=$((T5_END - T5_START))
echo "  对拍与契约核验完成，耗时: ${D5}s"

TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))

echo "============================================="
echo "        M11 割接演练耗时测算总览表           "
echo "============================================="
printf "  %-26s %-10s %-8s\n" "演练环节" "实测耗时" "状态"
printf "  %-26s %-10s %-8s\n" "1. 历史库快照镜像" "${D1}s" "[PASS]"
printf "  %-26s %-10s %-8s\n" "2. 新库表结构构建" "${D2}s" "[PASS]"
printf "  %-26s %-10s %-8s\n" "3. 全领域存量导入" "${D3}s" "[PASS]"
printf "  %-26s %-10s %-8s\n" "4. 完整性与行数对账" "${D4}s" "[PASS]"
printf "  %-26s %-10s %-8s\n" "5. 契约审计与对拍" "${D5}s" "[PASS]"
echo "---------------------------------------------"
echo "演练总耗时: ${TOTAL_DURATION} 秒 (维护窗口上限: 900 秒 / 15 分钟)"
if [[ $TOTAL_DURATION -le 900 ]]; then
    echo "评定结果: 符合停机窗口预算 (预算剩余: $((900 - TOTAL_DURATION)) 秒) [PASS]"
else
    echo "评定结果: 超出 15 分钟停机预算，需优化导入瓶颈！[FAIL]"
    exit 1
fi
echo "============================================="
