#!/bin/bash
# ============================================================
# JDK 变更自检 —— 防止「Java 升级了但进程没重启」导致
# ProcessBuilder 调子进程失败（Cannot run program / Failed to exec spawn helper）
#
# 原理：jspawnhelper 的 mtime 比 ruoyi 进程启动时间新 = 二进制被换过
#      老进程内存里还是旧 JDK → 调 spawn 必失败 → 自动重启
# ============================================================
set -uo pipefail

JH=/usr/lib/jvm/java-17-openjdk-amd64/lib/jspawnhelper
SVC=ruoyi-app

log() { echo "[$(date '+%F %T')] $*"; }

[ -x "$JH" ] || { log "跳过：找不到 $JH"; exit 0; }

JH_TS=$(stat -c %Y "$JH" 2>/dev/null || echo 0)
START_STR=$(systemctl show -p ActiveEnterTimestamp --value $SVC 2>/dev/null)
START_TS=$(date -d "$START_STR" +%s 2>/dev/null || echo 0)

log "jspawnhelper mtime: $(date -d @$JH_TS '+%F %T')"
log "ruoyi 启动时间:     $START_STR"

if [ "$START_TS" -eq 0 ]; then
    log "读不到启动时间，跳过"
    exit 0
fi

if [ "$JH_TS" -gt "$START_TS" ]; then
    GAP=$(( (JH_TS - START_TS) / 3600 ))
    log "⚠ jspawnhelper 比进程新 ${GAP} 小时 —— JDK 被换过，老进程 spawn 会失败"
    log "→ 自动重启 $SVC"
    systemctl restart $SVC
    for i in $(seq 1 90); do
        code=$(curl -s -o /dev/null -w '%{http_code}' -m 3 \
               http://127.0.0.1:18081/system/tnotice/public/list 2>/dev/null || echo 000)
        [ "$code" = "200" ] && { log "✓ 重启完成，用时 ${i}s"; exit 0; }
        sleep 1
    done
    log "!! 重启后仍未就绪，请手动检查"
    exit 1
fi

log "✓ JDK 未变更，无需处理"
