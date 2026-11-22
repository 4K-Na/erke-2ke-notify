#!/bin/bash
# ============================================================
# 第二课堂通知系统 · 一键部署脚本
#
# 适用：Ubuntu 24.04 全新机器
# 用法：
#   1. 把整个仓库放到 /opt/erke-source
#   2. cd /opt/erke-source && sudo bash deploy.sh
#   3. 按提示填写 04-凭据 里的配置
#
# 这个脚本做的是「把代码和配置放到位」，
# 不理解系统结构的话，先读 README.md 和 05-文档/SYSTEM-档案.md
# ============================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log()  { echo -e "\033[36m[$(date '+%H:%M:%S')]\033[0m $*"; }
ok()   { echo -e "  \033[32m✓\033[0m $*"; }
warn() { echo -e "  \033[33m!\033[0m $*"; }
die()  { echo -e "  \033[31m✗\033[0m $*"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 或 sudo 运行"

# ============================================================
# 0. 参数（可用环境变量覆盖）
# ============================================================
DB_PORT="${DB_PORT:-3307}"
DB_USER="${DB_USER:-root}"
DB_PASS="${DB_PASS:-}"
DB_NAME="${DB_NAME:-ry-2ke}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASS="${REDIS_PASS:-}"
APP_USER="${APP_USER:-jmu2ke}"      # 采集器运行用户
DOMAIN="${DOMAIN:-example.com}"      # 你的域名

log "开始部署：$DB_NAME@$DB_PORT，域名 $DOMAIN"

# ============================================================
# 授权校验
# ============================================================
LICENSE_HASH="dab3dfe8c5273bb8e23851d17f3929059663bb99d086333fc14298779e9566f6"

_auth_check() {
    local key=""
    if [ -f /opt/erke-license ]; then
        key=$(cat /opt/erke-license 2>/dev/null | tr -d '\n\r')
    fi
    if [ -z "$key" ]; then
        echo
        echo "本程序需要授权码才能部署。"
        echo "请向维护者索取，输入时不显示字符。"
        echo
        read -rsp "授权码: " key
        echo
    fi
    local got
    got=$(printf '%s' "$key" | sha256sum | cut -d' ' -f1)
    if [ "$got" != "$LICENSE_HASH" ]; then
        echo
        echo "授权码错误，部署中止。"
        echo
        exit 107
    fi
    printf '%s' "$key" > /opt/erke-license
    chmod 600 /opt/erke-license
    ok "授权通过"
}

_auth_check


# ============================================================
# 1. 系统依赖
# ============================================================
log "步骤 1/9 检查系统依赖"
MISSING=()
for c in curl git nginx python3 pip3; do
    command -v $c >/dev/null 2>&1 || MISSING+=("$c")
done
if [ ${#MISSING[@]} -gt 0 ]; then
    warn "缺少: ${MISSING[*]}"
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv nginx curl git >/dev/null
fi
ok "基础工具就绪"

# Java 17
if ! command -v java >/dev/null 2>&1; then
    log "  安装 OpenJDK 17"
    apt-get install -y -qq openjdk-17-jdk-headless >/dev/null
fi
ok "Java: $(java -version 2>&1 | head -1)"

# Node 20
if ! command -v node >/dev/null 2>&1; then
    warn "未装 Node，前端无法构建。建议手动装 Node 20 后重跑"
else
    ok "Node: $(node -v)"
fi

# Maven
if ! command -v mvn >/dev/null 2>&1; then
    warn "未装 Maven，后端无法编译。建议 apt install maven 后重跑"
else
    ok "Maven: $(mvn -v 2>/dev/null | head -1 | cut -d' ' -f1-3)"
fi

# ============================================================
# 2. Python 依赖
# ============================================================
log "步骤 2/9 安装 Python 依赖"
pip3 install --quiet --break-system-packages -r "$ROOT/01-代码/requirements.txt" 2>&1 | grep -v WARNING || true
if python3 -c "import pymysql, cryptography" 2>/dev/null; then
    ok "pymysql / cryptography 已装"
else
    die "Python 依赖安装失败"
fi

# ============================================================
# 3. 运行用户
# ============================================================
log "步骤 3/9 创建运行用户 $APP_USER"
id "$APP_USER" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -M "$APP_USER"
ok "用户 $APP_USER 就绪"

# ============================================================
# 4. 数据库
# ============================================================
log "步骤 4/9 初始化数据库 $DB_NAME"
if [ -z "$DB_PASS" ]; then
    warn "DB_PASS 未设置。请先建好 MySQL 用户，然后手动导入："
    warn "  mysql -h127.0.0.1 -P$DB_PORT -u$DB_USER -p -e 'CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4'"
    warn "  mysql -h127.0.0.1 -P$DB_PORT -u$DB_USER -p $DB_NAME < $ROOT/03-数据/init.sql"
else
    export MYSQL_PWD="$DB_PASS"
    mysql -h127.0.0.1 -P$DB_PORT -u"$DB_USER" \
        -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci" \
        || die "连不上数据库，检查 MySQL 是否启动、端口是否正确"
    mysql -h127.0.0.1 -P$DB_PORT -u"$DB_USER" "$DB_NAME" < "$ROOT/03-数据/init.sql" \
        || die "导入 init.sql 失败"
    TABLES=$(mysql -h127.0.0.1 -P$DB_PORT -u"$DB_USER" -N -B "$DB_NAME" -e "show tables" | wc -l)
    ok "已建 $TABLES 张表"
    unset MYSQL_PWD
fi

# ============================================================
# 5. Python 采集器
# ============================================================
log "步骤 5/9 部署采集器"
for d in 2ke-hub jwxt jmu-2ke; do
    mkdir -p "/opt/$d"
    rsync -a --exclude='.git*' --exclude='__pycache__' "$ROOT/01-代码/$d/" "/opt/$d/"
done
chown -R "$APP_USER:$APP_USER" /opt/2ke-hub /opt/jmu-2ke
chown -R root:root /opt/jwxt
chmod 700 /opt/jwxt
ok "已放到 /opt/{2ke-hub,jwxt,jmu-2ke}"

warn "接下来必须手工填写配置（参考 *.example）："
warn "  /opt/2ke-hub/wecom.json     企业微信 CorpID / Secret / AgentId / AESKey"
warn "  /opt/2ke-hub/db.json        数据库连接"
warn "  /opt/jwxt/db.json           数据库连接"
warn "  /opt/jwxt/cas-auth.json     教务系统账号密码"
warn "  /opt/jmu-2ke/2ke_cookie.json  2ke 官网 cookie"
warn "  填完统一改权限: chmod 600 <文件>; chown $APP_USER <文件>"

# ============================================================
# 6. systemd
# ============================================================
log "步骤 6/9 安装 systemd 服务"
for u in 2ke-hub-mysql 2ke-dispatcher 2ke-wecom jwxt-collector jwxt-collector.timer jdk-guard jdk-guard.timer qr-upload; do
    SRC="$ROOT/02-配置/etc/systemd/system/$u.service"
    [ -f "$SRC" ] || SRC="$ROOT/02-配置/etc/systemd/system/$u"
    [ -f "$SRC" ] && cp "$SRC" /etc/systemd/system/ && ok "$u"
done
systemctl daemon-reload
ok "已 reload（下一步填完配置再启动）"

# 运维脚本
mkdir -p /root/bin
for s in full-backup.sh purge-old.sh jdk-guard.sh; do
    [ -f "$ROOT/02-配置/scripts/$s" ] && cp "$ROOT/02-配置/scripts/$s" /root/bin/ && chmod 700 "/root/bin/$s"
done
ok "运维脚本已放 /root/bin"

# ============================================================
# 7. 后端
# ============================================================
log "步骤 7/9 构建后端"
if command -v mvn >/dev/null 2>&1; then
    ( cd "$ROOT/01-代码/ruoyi-backend" && \
      mvn clean package -pl ruoyi-system,ruoyi-admin -am -DskipTests -q ) \
      && ok "后端 jar 已生成" || warn "后端编译失败，看上面的报错"
else
    warn "跳过（无 Maven）"
fi

# ============================================================
# 8. 前端
# ============================================================
log "步骤 8/9 构建前端"
if command -v npm >/dev/null 2>&1; then
    ( cd "$ROOT/01-代码/ruoyi-frontend" && npm install --silent && npm run build:prod ) \
      && ok "前端 dist 已生成" || warn "前端构建失败"
else
    warn "跳过（无 Node）"
fi

# ============================================================
# 9. nginx
# ============================================================
log "步骤 9/9 配置 nginx"
for f in "$ROOT"/02-配置/etc/nginx/conf.d/*.conf; do
    [ -f "$f" ] && cp "$f" /etc/nginx/conf.d/ && ok "$(basename $f)"
done
cp "$ROOT/02-配置/etc/nginx/sites-available/"*.conf /etc/nginx/sites-available/ 2>/dev/null
warn "站点配置在 /etc/nginx/sites-available/，需要自己软链到 sites-enabled/"
warn "  并按实际域名/证书路径修改（模板里是 example.com）"
nginx -t 2>&1 | tail -2

# ============================================================
# 完成
# ============================================================
cat <<EOF

══════════════════════════════════════════════
  代码和配置已就位，还需要手工做这几件事：

  1. 填写 5 个配置文件（见步骤 5 的提示）
  2. 改 nginx 站点配置里的域名和证书路径
  3. 软链站点配置：
       ln -s /etc/nginx/sites-available/site-main.conf /etc/nginx/sites-enabled/
       nginx -t && systemctl reload nginx
  4. 启动服务：
       systemctl enable --now 2ke-hub-mysql 2ke-dispatcher 2ke-wecom
       systemctl enable --now jwxt-collector.timer jdk-guard.timer qr-upload
       systemctl enable --now ruoyi-app
  5. 导入定时任务：
       crontab $ROOT/02-配置/crontab.txt
  6. 访问后台确认：https://你的域名:18443/
       默认 admin / admin123（立即改密码）

  详细说明见 README.md 和 05-文档/SYSTEM-档案.md
══════════════════════════════════════════════
EOF
