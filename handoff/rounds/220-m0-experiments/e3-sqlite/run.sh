#!/bin/sh
# Usage: sh run.sh [processes] [steps per process] [db path]
# Four processes, each with four goroutines, all write the same file.
set -e
P=${1:-4}; STEPS=${2:-1000}; DB=${3:-/tmp/e3.sqlite}
BIN=${E3_BIN:-./bin/e3}
$BIN -mode init -db "$DB"
i=0; pids=""
while [ $i -lt "$P" ]; do
  $BIN -mode work -db "$DB" -steps "$STEPS" -conc 4 $E3_EXTRA > /tmp/e3.out.$i &
  pids="$pids $!"; i=$((i+1))
done
for p in $pids; do wait $p; done
cat /tmp/e3.out.*; rm -f /tmp/e3.out.*
$BIN -mode verify -db "$DB"
echo "expected counter=$((P*STEPS))"
