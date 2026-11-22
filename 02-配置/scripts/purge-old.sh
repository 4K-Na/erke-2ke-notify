#!/bin/bash
# ============================================================
# 记录消融 —— 定期清理过期数据，避免列表和库里越堆越多
#   讲座：结束超过 $LECTURE_KEEP_DAYS 天的删掉（连同它的推送明细）
#   活动：结束超过 $ACTIVITY_KEEP_DAYS 天的删掉（连同它的投递明细）
#   登录日志：保留 $LOG_KEEP_DAYS 天
#   操作日志：保留 $LOG_KEEP_DAYS 天
#
# 默认 30/60/90 天。加 --dry 只统计不删。
# ============================================================
set -uo pipefail

LECTURE_KEEP_DAYS=${LECTURE_KEEP_DAYS:-30}
ACTIVITY_KEEP_DAYS=${ACTIVITY_KEEP_DAYS:-60}
LOG_KEEP_DAYS=${LOG_KEEP_DAYS:-90}
DRY=0
[ "${1:-}" = "--dry" ] && DRY=1

export MYSQL_PWD='<DB_PASSWORD>'
MY="/www/server/mysql/bin/mysql -h127.0.0.1 -P3307 -uroot ry-2ke"

log() { echo "[$(date '+%F %T')] $*"; }

q() { $MY -N -B -e "$1" 2>/dev/null; }

log "===== 消融开始（dry=$DRY）====="

# ---------- 讲座 ----------
LEC=$(q "select count(*) from t_lecture where act_state in ('ended','gone')
         and open_end is not null and open_end < DATE_SUB(NOW(), INTERVAL $LECTURE_KEEP_DAYS DAY)")
log "讲座：结束超过 ${LECTURE_KEEP_DAYS} 天的 $LEC 条"
if [ "$DRY" = "0" ] && [ "$LEC" -gt 0 ]; then
    q "delete d from t_lecture_delivery d join t_lecture l on d.lecture_id = l.lecture_id
       where l.act_state in ('ended','gone')
         and l.open_end is not null and l.open_end < DATE_SUB(NOW(), INTERVAL $LECTURE_KEEP_DAYS DAY)"
    q "delete from t_lecture where act_state in ('ended','gone')
       and open_end is not null and open_end < DATE_SUB(NOW(), INTERVAL $LECTURE_KEEP_DAYS DAY)"
    log "  已清理"
fi

# ---------- 活动 ----------
ACT=$(q "select count(*) from t_activity where act_state in ('ended','gone')
         and end_at is not null and end_at < DATE_SUB(NOW(), INTERVAL $ACTIVITY_KEEP_DAYS DAY)")
log "活动：结束超过 ${ACTIVITY_KEEP_DAYS} 天的 $ACT 条"
if [ "$DRY" = "0" ] && [ "$ACT" -gt 0 ]; then
    q "delete d from t_delivery d join t_activity a on d.activity_id = a.activity_id
       where a.act_state in ('ended','gone')
         and a.end_at is not null and a.end_at < DATE_SUB(NOW(), INTERVAL $ACTIVITY_KEEP_DAYS DAY)"
    q "delete from t_activity where act_state in ('ended','gone')
       and end_at is not null and end_at < DATE_SUB(NOW(), INTERVAL $ACTIVITY_KEEP_DAYS DAY)"
    log "  已清理"
fi

# ---------- 日志 ----------
LOGIN=$(q "select count(*) from sys_logininfor where login_time < DATE_SUB(NOW(), INTERVAL $LOG_KEEP_DAYS DAY)")
OPER=$(q "select count(*) from sys_oper_log where oper_time < DATE_SUB(NOW(), INTERVAL $LOG_KEEP_DAYS DAY)")
log "日志：登录 $LOGIN 条 / 操作 $OPER 条 超过 ${LOG_KEEP_DAYS} 天"
if [ "$DRY" = "0" ]; then
    [ "$LOGIN" -gt 0 ] && q "delete from sys_logininfor where login_time < DATE_SUB(NOW(), INTERVAL $LOG_KEEP_DAYS DAY)"
    [ "$OPER" -gt 0 ] && q "delete from sys_oper_log where oper_time < DATE_SUB(NOW(), INTERVAL $LOG_KEEP_DAYS DAY)"
    [ "$LOGIN" -gt 0 ] || [ "$OPER" -gt 0 ] && log "  已清理"
fi

# ---------- 汇总 ----------
log "剩余：讲座 $(q 'select count(*) from t_lecture') 条（开放 $(q "select count(*) from t_lecture where act_state='open'")）"
log "      活动 $(q 'select count(*) from t_activity') 条（开放 $(q "select count(*) from t_activity where act_state='open'")）"
log "      库大小 $(q "select round(sum(data_length+index_length)/1024/1024,2) from information_schema.tables where table_schema='ry-2ke'") MB"
log "===== 消融结束 ====="
