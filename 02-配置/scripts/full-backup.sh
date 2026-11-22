#!/bin/bash
# ============================================================
# 第二课堂通知系统 —— 全量备份（代码 + 数据 + 配置 + 凭据）
# 每天 04:50 由 cron 触发，产物放 /root/full-backup/full-YYYYmmdd-HHMM.tar.gz
# 本机再用 sync-full-backup.js 定时拉走；服务器侧保留 7 天。
# ============================================================
set -uo pipefail

DEST=/root/full-backup
KEEP_DAYS=7
TS=$(date +%Y%m%d-%H%M)
WORK=$(mktemp -d /tmp/fb-XXXXXX)
mkdir -p "$DEST"

log() { echo "[$(date '+%F %T')] $*"; }

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

log "开始备份 $TS（工作目录 $WORK）"

# ---------- 1. 数据库 ----------
MYCNF=/root/.fb-my.cnf
cat > "$MYCNF" <<'EOF'
[client]
host=127.0.0.1
port=3307
user=root
password=<DB_PASSWORD>
default-character-set=utf8mb4
EOF
chmod 600 "$MYCNF"

if /www/server/mysql/bin/mysqldump --defaults-extra-file="$MYCNF" \
      --single-transaction --quick --routines --triggers --events \
      ry-2ke 2>"$WORK/dump.err" | gzip -6 > "$WORK/db-ry-2ke.sql.gz"; then
    log "  数据库 OK  $(du -h "$WORK/db-ry-2ke.sql.gz" | cut -f1)"
else
    log "  !! 数据库导出失败：$(tail -1 "$WORK/dump.err")"
    rm -f "$MYCNF"
    exit 1
fi
rm -f "$MYCNF" "$WORK/dump.err"

# ---------- 2. 代码（排除体积大且可重建的） ----------
tar czf "$WORK/code.tar.gz" \
    --exclude='node_modules' --exclude='target' --exclude='.git' \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
    --exclude='*.log' --exclude='.cache' \
    -C / \
    opt/ruoyi opt/ruoyi-ui opt/2ke-hub opt/jwxt opt/jmu-2ke \
    var/www/2ke-subscribe 2>"$WORK/code.err" || {
    log "  !! 代码打包失败：$(tail -1 "$WORK/code.err")"; exit 1; }
log "  代码 OK    $(du -h "$WORK/code.tar.gz" | cut -f1)"
rm -f "$WORK/code.err"

# ---------- 3. 配置 ----------
tar czf "$WORK/config.tar.gz" \
    -C / etc/nginx etc/systemd/system etc/logrotate.d 2>/dev/null
crontab -l > "$WORK/crontab.txt" 2>/dev/null || echo "(无 crontab)" > "$WORK/crontab.txt"
systemctl list-units --type=service --state=running --no-legend --no-pager \
    > "$WORK/running-services.txt" 2>/dev/null
nginx -T > "$WORK/nginx-full.conf" 2>/dev/null
log "  配置 OK    $(du -h "$WORK/config.tar.gz" | cut -f1)"

# ---------- 4. 凭据（单独一个包，恢复时必需） ----------
tar czf "$WORK/secrets.tar.gz" \
    --warning=no-file-changed \
    -C / \
    opt/2ke-hub/wecom.json \
    opt/jwxt/cookie.txt opt/jwxt/tgc.txt opt/jwxt/push.json opt/jwxt/state.json \
    opt/jmu-2ke/2ke_cookie.json 2>/dev/null || true
chmod 600 "$WORK/secrets.tar.gz" 2>/dev/null
log "  凭据 OK    $(du -h "$WORK/secrets.tar.gz" 2>/dev/null | cut -f1)"

# ---------- 5. 清单 ----------
{
    echo "# 第二课堂通知系统 · 全量备份清单"
    echo "备份时间: $(date '+%F %T %Z')"
    echo "主机: $(hostname)  $(uname -r)"
    echo
    echo "## 数据库"
    /www/server/mysql/bin/mysql --defaults-extra-file=<(printf '[client]\nhost=127.0.0.1\nport=3307\nuser=root\npassword=<DB_PASSWORD>\n') \
        -N -B -e "select table_name, table_rows, round((data_length+index_length)/1024,1) kb from information_schema.tables where table_schema='ry-2ke' order by table_name;" 2>/dev/null
    echo
    echo "## 关键计数"
    /www/server/mysql/bin/mysql --defaults-extra-file=<(printf '[client]\nhost=127.0.0.1\nport=3307\nuser=root\npassword=<DB_PASSWORD>\n') ry-2ke -N -B \
        -e "select 't_activity', count(*) from t_activity union all
            select 't_subscriber', count(*) from t_subscriber union all
            select 't_delivery', count(*) from t_delivery union all
            select 't_lecture', count(*) from t_lecture union all
            select 't_lecture_delivery', count(*) from t_lecture_delivery union all
            select 't_notice', count(*) from t_notice;" 2>/dev/null
    echo
    echo "## 包含的目录"
    echo "opt/ruoyi opt/ruoyi-ui opt/2ke-hub opt/jwxt opt/jmu-2ke var/www/2ke-subscribe"
    echo "etc/nginx etc/systemd/system etc/logrotate.d + crontab + 运行中服务列表"
    echo
    echo "## 恢复方法"
    echo "1) 解包：tar xzf full-*.tar.gz -C /"
    echo "2) 数据库：zcat db-ry-2ke.sql.gz | mysql -h127.0.0.1 -P3307 -uroot -p ry-2ke"
    echo "3) 重新编译前端/后端见 SYSTEM-档案.md §9"
    echo "4) 凭据在 secrets.tar.gz（600）"
} > "$WORK/MANIFEST.txt" 2>/dev/null

# ---------- 6. 合成一个包 ----------
OUT="$DEST/full-$TS.tar.gz"
if tar czf "$OUT" -C "$WORK" . ; then
    chmod 600 "$OUT"
    SIZE=$(du -h "$OUT" | cut -f1)
    log "  完成 $OUT ($SIZE)"
else
    log "  !! 合成失败"; exit 1
fi

# ---------- 7. 轮转 ----------
DEL=$(find "$DEST" -name 'full-*.tar.gz' -mtime +$KEEP_DAYS -print -delete | wc -l)
log "  清理 $DEL 个超过 $KEEP_DAYS 天的旧备份，现存 $(ls -1 "$DEST"/full-*.tar.gz 2>/dev/null | wc -l) 份"

# 输出最新包名，供本机拉取脚本识别
echo "$OUT" > "$DEST/.latest"
chmod 600 "$DEST/.latest"
log "备份结束"
