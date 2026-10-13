#!/usr/bin/env bash
# Strict rehearsal: explicit old SQLite + media, or one old backup archive.
set -euo pipefail
umask 077
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
if [[ $# -lt 1 || $# -gt 2 || ! -f "$1" ]]; then
    echo "用法: rehearse.sh <旧库> <旧媒体目录> 或 rehearse.sh <旧备份.tar.gz>" >&2
    exit 64
fi
WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/sjtuow-rehearsal-XXXXXX")
cleanup() {
    rm -rf -- "$WORK_DIR"
    test ! -e "$WORK_DIR" && echo REHEARSAL-PRIVATE-WORK-REMOVED
}
trap cleanup EXIT
TOTAL_START=$(date +%s)
MEDIA_INPUT=$(python3 "$SCRIPT_DIR/rehearsal_input.py" "$1" "${2:-}" "$WORK_DIR")
mkdir -p "$WORK_DIR/data" "$WORK_DIR/media"
export DATA_DIR="$WORK_DIR/data" MEDIA_DIR="$WORK_DIR/media" SJTUOW_ENV=dev
export SITE_URL="${SITE_URL:-https://example.invalid}"
export SIGNING_KEY="${SIGNING_KEY:-rehearsal-signing-key-32-characters}"
export FIELD_ENCRYPTION_KEY="${FIELD_ENCRYPTION_KEY:-eWVhcnRvZGF5c2VjcmV0ZmllbGRlbmNyeXB0aW9ua2V5MTI=}"
SJTUOW_BIN="$WORK_DIR/sjtuow"
(cd "$REPO_DIR/server" && go build -o "$SJTUOW_BIN" ./cmd/sjtuow)
step() {
    local name=$1
    shift
    local started=$(date +%s)
    # Import stdout can contain titles in diagnostics; store it privately.
    # A failure is reported by kind and exit code only, never real identities.
    if "$@" >"$WORK_DIR/step.log" 2>&1; then
        # Reconcile's revised report contains table counts and match flags,
        # never real addresses, names or titles; keep that actual evidence.
        if [[ "$name" = reconcile ]]; then cat "$WORK_DIR/step.log"; fi
        printf 'REHEARSAL_STEP %s elapsed=%s exit=0\n' "$name" "$(( $(date +%s) - started ))"
    else
        local code=$?
        printf 'REHEARSAL_STEP %s exit=%s (private diagnostics on test machine)\n' "$name" "$code" >&2
        if [[ "$name" = reconcile ]]; then cat "$WORK_DIR/step.log"; fi
        # Preserve diagnostics only when explicitly requested by a fixture test.
        if [[ -n "${REHEARSAL_DIAGNOSTICS_DIR:-}" ]]; then
            mkdir -p "$REHEARSAL_DIAGNOSTICS_DIR"
            chmod 700 "$REHEARSAL_DIAGNOSTICS_DIR"
            cp "$WORK_DIR/step.log" "$REHEARSAL_DIAGNOSTICS_DIR/$name.log"
        fi
        return "$code"
    fi
}
step migrate "$SJTUOW_BIN" migrate
step import "$SJTUOW_BIN" import "$WORK_DIR/legacy-source.sqlite3"
step import-media "$SJTUOW_BIN" import-media "$MEDIA_INPUT"
step import-fonts "$SJTUOW_BIN" import-fonts "$WORK_DIR/legacy-source.sqlite3" "$MEDIA_INPUT"
step reconcile "$SJTUOW_BIN" reconcile "$WORK_DIR/legacy-source.sqlite3"
step rulecheck "$SJTUOW_BIN" rulecheck --repo "$REPO_DIR"
step parity "$SJTUOW_BIN" parity --signing-key "$SIGNING_KEY"
if [[ "${REHEARSAL_BROWSER_CHECK:-0}" = 1 ]]; then
    step pages uv run python "$REPO_DIR/e2e/journeys/rehearsal_pages.py" "$SJTUOW_BIN" "$WORK_DIR"
fi
TOTAL_DURATION=$(( $(date +%s) - TOTAL_START ))
echo "REHEARSAL_TOTAL elapsed=$TOTAL_DURATION budget=900"
if (( TOTAL_DURATION > 900 )); then
    echo REHEARSAL-BUDGET-FAILED >&2
    exit 1
fi
echo REHEARSAL-OK
