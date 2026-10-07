#!/bin/sh
# 只在北京时间的指定整点才执行命令（218，217 复核 09-9）。
#
#   sh at-shanghai.sh 小时 [星期] -- 命令 参数...
#
# 小时是北京时间的 0–23；星期是北京时间的星期，0 是周日、6 是周六，不写就每天。
#
# 为什么要有它：Debian 自带的 cron 不支持 CRON_TZ，以前把北京时间按服务器所在
# 时区换算成小时写死。正式站的服务器在 Europe/Berlin，夏令时结束（2026-10-25）
# 以后每一条都整体晚一小时，设计 16.5 的时间表就不对了。现在 crontab 里每条都是
# 「每小时的某一分钟」，由这个脚本判断北京时间到没到；中国没有夏令时，用 POSIX
# 写法 CST-8（东八区）算，不依赖服务器上装没装时区数据库，也不受服务器时区影响。
#
# 测试用：AT_SHANGHAI_EPOCH=<秒数> 代替「现在」。
set -eu

usage() {
    echo "用法：sh at-shanghai.sh 小时 [星期] -- 命令 参数..." >&2
    exit 64
}

[ $# -ge 3 ] || usage
hour=$1
shift
weekday=
if [ "$1" != "--" ]; then
    weekday=$1
    shift
fi
[ "$1" = "--" ] || usage
shift
[ $# -ge 1 ] || usage

case $hour in
    [0-9] | [0-9][0-9]) ;;
    *) usage ;;
esac
[ "$hour" -le 23 ] || usage
case $weekday in
    "" | [0-6]) ;;
    *) usage ;;
esac

if [ -n "${AT_SHANGHAI_EPOCH:-}" ]; then
    stamp=$(TZ=CST-8 date -d "@$AT_SHANGHAI_EPOCH" '+%H %w' 2>/dev/null ||
        TZ=CST-8 date -r "$AT_SHANGHAI_EPOCH" '+%H %w')
else
    stamp=$(TZ=CST-8 date '+%H %w')
fi
now_hour=${stamp% *}
now_weekday=${stamp#* }
case $now_hour in
    0?) now_hour=${now_hour#0} ;;
esac

[ "$now_hour" -eq "$hour" ] || exit 0
if [ -n "$weekday" ] && [ "$now_weekday" != "$weekday" ]; then
    exit 0
fi
exec "$@"
