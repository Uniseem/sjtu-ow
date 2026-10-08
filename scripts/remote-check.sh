#!/usr/bin/env bash
# Run the checks on the test machine against this working tree, uncommitted
# changes included (AGENTS.md「测试机与部署」). The working tree travels as a
# git bundle, so the server checks out exactly what is here: LF line endings,
# new files in, deleted files gone. Nothing is staged or committed locally.
#
#   scripts/remote-check.sh            # the whole set, same as CI (scripts/check.sh):
#                                      # the Go stack only (229)
#   scripts/remote-check.sh run go test ./internal/platform/config/
#   scripts/remote-check.sh run uv run python handoff/rounds/NNN-name/mutate.py
#   scripts/remote-check.sh attach     # follow the latest run again
#
# The job runs detached on the server and this script polls its log every
# three seconds over short connections: on the way to the first test machine
# long ones were cut after a few minutes (128 saw 1m53s and 5m08s, output
# flowing, keepalives on), taking the job down with them. One job at a time:
# a second one waits for the lock. The exit code is the job's.
#
# CHECK_HOST picks the machine: default the SSH alias sjtu-ow-test, which
# your SSH config points at the test machine (2a0e:6a80:3:9c7::, IPv6 only)
# through the user's port forward 189.24.110.12:2222 (2026-10-05); the login
# user and key come from that config, never from the repository.
set -euo pipefail

host=${CHECK_HOST:-sjtu-ow-test}
# scp wants an IPv6 address in brackets.
case $host in *:*) copy_to="[$host]" ;; *) copy_to=$host ;; esac
base=${CHECK_DIR:-/srv/sjtu-ow-check}
ref=refs/remote-check/wip
cd "$(git rev-parse --show-toplevel)"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"; git update-ref -d "$ref" 2>/dev/null || true' EXIT

follow() {
  local run=$1 offset=0 code=""
  echo "日志：$host:$base/runs/$run.log"
  while :; do
    if ssh -o ConnectTimeout=20 "$host" \
      "printf '%s\n' \"\$(cat $base/runs/$run.status 2>/dev/null)\";
       tail -c +$((offset + 1)) $base/runs/$run.log 2>/dev/null" >"$tmp/poll"; then
      code=$(head -n 1 "$tmp/poll")
      tail -n +2 "$tmp/poll" >"$tmp/chunk"
      cat "$tmp/chunk"
      offset=$((offset + $(wc -c <"$tmp/chunk")))
      [ -z "$code" ] || exit "$code"
    else
      echo "（连接断了，重连）" >&2
    fi
    sleep 3
  done
}

case "${1:-check}" in
check) command="sh scripts/check.sh" ;;
run)
  shift
  [ $# -gt 0 ] || { echo "run 后面要跟命令" >&2; exit 2; }
  command=$(printf '%q ' "$@")
  ;;
attach)
  run=${2:-$(ssh "$host" "ls -t $base/runs/*.log 2>/dev/null | head -n 1 | xargs -r basename -s .log")}
  [ -n "$run" ] || { echo "测试机上还没有跑过检查" >&2; exit 2; }
  follow "$run"
  ;;
*) echo "用法：$0 [check | run 命令… | attach [编号]]" >&2; exit 2 ;;
esac

# The working tree as a commit on top of HEAD, built in a scratch index.
export GIT_INDEX_FILE="$tmp/index"
git read-tree HEAD
git -c core.safecrlf=false add -A
tree=$(git write-tree)
unset GIT_INDEX_FILE
snapshot=$(git commit-tree "$tree" -p HEAD -m "remote-check snapshot")
git update-ref "$ref" "$snapshot"
# The server fetches origin first, so the bundle only carries what is newer.
git bundle create --quiet "$tmp/job.bundle" "$ref" --not origin/main

run=$(date +%Y%m%d-%H%M%S)-${snapshot:0:7}
job=$base/runs/$run
headline=$(printf '%q' "$(git log -1 --format='%h %s')")
cat >"$tmp/job.sh" <<EOF
set -e
exec 9>"$base/lock"
flock -n 9 || { echo "另一次检查还在跑，等它结束……"; flock 9; }
export PATH="$base/uv/bin:\$PATH" UV_CACHE_DIR="$base/uv/cache" \
  UV_PYTHON_INSTALL_DIR="$base/uv/python"
# 新栈的工具链（222 起装在检查目录里：go/ gobin/ node24/）；没装也不影响 Python 检查
if [ -d "$base/go" ]; then
  export GOROOT="$base/go" GOPATH="$base/gopath" GOCACHE="$base/gocache" \\
    GOMODCACHE="$base/gomodcache" \\
    PATH="$base/go/bin:$base/gobin:$base/node24/bin:\$PATH"
fi
cd "$base/repo"
git fetch -q origin
git fetch -q "$job.bundle" "+$ref:$ref"
git checkout -qf --detach "$snapshot"
git clean -fdq
echo "测试机 \$(hostname)：" $headline "+ 工作区改动"
uv sync --frozen --quiet
$command
EOF

ssh "$host" "mkdir -p $base/runs && ls -t $base/runs/*.log 2>/dev/null | tail -n +31 |
  sed 's/\.log\$//' | xargs -r -I{} sh -c 'rm -f {}.*'"
scp -q "$tmp/job.bundle" "$copy_to:$job.bundle"
scp -q "$tmp/job.sh" "$copy_to:$job.sh"
# The exit code is written outside the job, so even a job that cannot start
# leaves one behind and follow() stops.
ssh "$host" "setsid -f sh -c 'bash $job.sh >$job.log 2>&1; printf %s \$? >$job.status' \
  </dev/null >/dev/null 2>&1"
follow "$run"
