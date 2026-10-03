#!/usr/bin/env bash
# Split the test suite over N copies of the checkout and run them side by side
# (check.sh with CHECK_SHARDS=N, or auto for one per CPU; scripts/remote-check.sh
# asks for auto). Each copy is a git worktree with its own data/test.sqlite3,
# prerendered/ and .venv, so the runs share nothing on disk. They are kept in
# CHECK_SHARD_DIR (default ../shards) between runs, so only the first run pays
# for the virtualenvs.
#
# Runs what is committed at HEAD: on a checkout with uncommitted changes it
# falls back to one plain pytest, which sees them.
set -euo pipefail

n=$1
[ "$n" != auto ] || n=$(nproc)
if [ -n "$(git status --porcelain)" ]; then
  echo "工作区有未提交的改动，不分片"
  exec uv run pytest -q
fi

root=$(pwd)
dir=${CHECK_SHARD_DIR:-$root/../shards}
commit=$(git rev-parse HEAD)
mkdir -p "$dir"
rm -f "$dir"/ids.*

# Test by test in turn, so every shard gets a slice of each slow file. pytest
# reads the ids back one per line (@file), no shell quoting involved.
uv run pytest --collect-only -q 2>/dev/null | grep '::' |
  awk -v n="$n" -v dir="$dir" '{ print > (dir "/ids." ((NR - 1) % n + 1)) }'
echo "$(cat "$dir"/ids.* | wc -l) 条测试分成 $n 片"

pids=()
for i in $(seq 1 "$n"); do
  tree=$dir/$i
  [ -e "$tree/.git" ] || git worktree add -q --detach "$tree" "$commit"
  (
    cd "$tree"
    git checkout -qf --detach "$commit"
    git clean -fdq
    cp "$root/static/css/app.css" static/css/app.css
    uv sync --frozen --quiet
    uv run pytest -q -p no:cacheprovider "@$dir/ids.$i"
  ) >"$dir/log.$i" 2>&1 &
  pids+=("$!")
done

failed=0
for i in $(seq 1 "$n"); do
  if wait "${pids[$((i - 1))]}"; then
    echo "分片 $i：$(tail -n 1 "$dir/log.$i")"
  else
    failed=1
    echo "分片 $i 没通过："
    cat "$dir/log.$i"
  fi
done
exit "$failed"
