# 第二课堂通知系统

集美大学第二课堂活动与教务讲座的通知推送系统。自动抓取校内两个数据源，发现新内容后推送到学生微信。

一台空机器，一条 `git clone`，一个部署脚本，20 分钟重建整套服务。

---

## 部署环境

### 必需

| 组件 | 版本 | 用途 |
|---|---|---|
| Ubuntu | 24.04 | 其他发行版需调整 apt 包名 |
| Python | 3.12+ | 采集器与分发器 |
| JDK | 17 | 若依后端 |
| Node.js | 20 | 前端构建 |
| Maven | 3.8+ | 后端编译 |
| MySQL | 5.7 / 8.0 | 40 张表，库名 `ry-2ke` |
| Redis | 7.0 | 若依缓存与登录态 |
| Nginx | 1.24 | 反向代理与静态托管 |

### 服务器配置

**最低 2 核 2G**。1.6G 内存也能跑，但需要 3G swap，前端构建期间后端会卡顿。

磁盘 20G 起步（系统 + 依赖 + 日志 + 备份约 8G）。

### 端口

| 端口 | 用途 | 是否对外 |
|---|---|---|
| 443 | HTTPS 主站（订阅页、公告） | 是 |
| 18443 | HTTPS 管理后台 | 是 |
| 18081 | 后端应用 | 否（仅本机） |
| 3307 | MySQL | 否（仅本机） |
| 6379 | Redis | 否（仅本机） |

### 外部依赖

| 项 | 说明 |
|---|---|
| 域名 | 用于 HTTPS。没域名也能跑，但后台走明文 HTTP |
| 企业微信 | 需自建应用，拿到 CorpID / AgentId / Secret / EncodingAESKey |
| 校外访问 | 需能访问 `2ke.jmu.edu.cn` 和 `jwxt.jmu.edu.cn` |

---

## 部署

以 `root` 在 Ubuntu 24.04 上执行。

### 1. 装系统依赖

```bash
apt update
apt install -y python3 python3-pip python3-venv \
               openjdk-17-jdk-headless maven \
               mysql-server redis-server nginx curl git

curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

systemctl enable --now mysql redis-server nginx
```

### 2. 配置 MySQL 与 Redis

```bash
mysql -uroot -p
```

```sql
CREATE DATABASE ry-2ke CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
ALTER USER 'root'@'localhost' IDENTIFIED BY '换成你的密码';
FLUSH PRIVILEGES;
```

Redis 设密码，编辑 `/etc/redis/redis.conf`：

```
requirepass 换成你的密码
```

```bash
systemctl restart redis-server
```

### 3. 拉代码并导库

```bash
git clone https://github.com/<你的账号>/erke-2ke-notify /opt/erke
cd /opt/erke

mysql -uroot -p ry-2ke < 03-数据/init.sql
mysql -uroot -p ry-2ke -e "show tables" | wc -l   # 输出 40
```

默认管理员 `admin` / `admin123`，登录后立刻改。

### 4. 部署采集器

```bash
useradd -r -s /usr/sbin/nologin -M jmu2ke

cp -r 01-代码/2ke-hub  /opt/
cp -r 01-代码/jwxt     /opt/
cp -r 01-代码/jmu-2ke  /opt/

pip3 install --break-system-packages -r 01-代码/requirements.txt

chown -R jmu2ke:jmu2ke /opt/2ke-hub /opt/jmu-2ke
chown -R root:root /opt/jwxt && chmod 700 /opt/jwxt
```

### 5. 填凭据

五个文件，从 `*.example` 复制后填真实值。

**企业微信** `/opt/2ke-hub/wecom.json`

```bash
cp /opt/2ke-hub/wecom.json.example /opt/2ke-hub/wecom.json
```

```json
{
  "corp_id":      "企业微信后台 → 我的企业 → 企业ID",
  "agent_id":     1000002,
  "corp_secret":  "应用管理 → 自建应用 → Secret",
  "aes_key":      "应用 → 接收消息 → EncodingAESKey",
  "token":        "应用 → 接收消息 → Token",
  "admin_userid": "你的 UserID，接收告警"
}
```

**数据库连接** `/opt/2ke-hub/db.json` 和 `/opt/jwxt/db.json`

```bash
cp /opt/2ke-hub/db.json.example /opt/2ke-hub/db.json
cp /opt/jwxt/db.json.example    /opt/jwxt/db.json
```

```json
{
  "host": "127.0.0.1",
  "port": 3306,
  "user": "root",
  "password": "第 2 步设的密码",
  "database": "ry-2ke",
  "charset": "utf8mb4"
}
```

**教务账号** `/opt/jwxt/cas-auth.json`

```bash
cp /opt/jwxt/cas-auth.json.example /opt/jwxt/cas-auth.json
```

```json
{ "username": "学号", "password": "密码" }
```

采集器用它自动登录拿票据，不需要人工维护 cookie。

**2ke 官网 cookie** `/opt/jmu-2ke/2ke_cookie.json`

浏览器登录 `2ke.jmu.edu.cn` → F12 → Application → Cookies，复制 `SESSION` 和 `TGC` 的值填进去。

最后统一收权限：

```bash
chmod 600 /opt/2ke-hub/wecom.json /opt/2ke-hub/db.json \
          /opt/jwxt/db.json /opt/jwxt/cas-auth.json /opt/jmu-2ke/2ke_cookie.json
chown jmu2ke:jmu2ke /opt/2ke-hub/*.json /opt/jmu-2ke/*.json
```

### 6. 启采集与分发

```bash
cp 02-配置/etc/systemd/system/*.service /etc/systemd/system/
cp 02-配置/etc/systemd/system/*.timer   /etc/systemd/system/
systemctl daemon-reload

systemctl enable --now 2ke-hub-mysql         # 每 8 分钟抓活动
systemctl enable --now 2ke-dispatcher        # 每 2 分钟发推送
systemctl enable --now 2ke-wecom             # 企业微信回调
systemctl enable --now jwxt-collector.timer  # 每 30 分钟抓讲座
systemctl enable --now jdk-guard.timer       # JDK 变更自愈
systemctl enable --now qr-upload             # 二维码上传
```

### 7. 编译后端

先改配置再编译，配置是打进 jar 的。

```bash
cd /opt/erke/01-代码/ruoyi-backend

vi ruoyi-admin/src/main/resources/application-druid.yml   # 数据库地址密码
vi ruoyi-admin/src/main/resources/application.yml          # Redis 密码、上传路径

mvn clean package -pl ruoyi-system,ruoyi-admin -am -DskipTests

mkdir -p /opt/ruoyi
cp ruoyi-admin/target/ruoyi-admin.jar /opt/ruoyi/
cp /opt/erke/02-配置/etc/systemd/system/ruoyi-app.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now ruoyi-app
```

启动约 50 秒。日志在 `/var/log/ruoyi.log`。

### 8. 构建前端

```bash
cd /opt/erke/01-代码/ruoyi-frontend
npm install
npm run build:prod

mkdir -p /opt/ruoyi-ui
cp -r dist /opt/ruoyi-ui/
```

构建约 1 分钟，2 核机器会跑满 CPU。

### 9. 配置 nginx

```bash
cp /opt/erke/02-配置/etc/nginx/conf.d/*.conf /etc/nginx/conf.d/
cp /opt/erke/02-配置/etc/nginx/sites-available/site-main.conf /etc/nginx/sites-available/

vi /etc/nginx/sites-available/site-main.conf   # 改 server_name 和证书路径

certbot --nginx -d 你的域名

ln -s /etc/nginx/sites-available/site-main.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 10. 定时任务

```bash
crontab /opt/erke/02-配置/crontab.txt
crontab -l
```

装了五个：数据库备份（04:17）、过期数据清理（04:20）、全量备份（04:50）、二维码临期提醒（09:23）、图片清理（每周日 04:30）。

---

## 验证

```bash
# 服务全绿
systemctl is-active 2ke-hub-mysql 2ke-dispatcher 2ke-wecom \
                    jwxt-collector.timer jdk-guard.timer qr-upload \
                    ruoyi-app nginx

# 采集正常（应看到 ok ... open=N ended=N）
journalctl -u 2ke-hub-mysql -n 5
journalctl -u jwxt-collector -n 5

# 后台可访问
curl -k https://你的域名:18443/ -o /dev/null -w "%{http_code}\n"    # 200

# 登录
curl -X POST https://你的域名:18443/prod-api/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"admin123"}'
# 返回 {"code":200,"token":"..."}
```

后台进去后，首页能看到活动数、订阅者数、投递记录，采集状态显示「采集正常」即为部署完成。

---

## 日常维护

```bash
# 立即采集一次
systemctl start jwxt-collector
python3 /opt/2ke-hub/collector_mysql.py

# 手动备份
/root/bin/full-backup.sh

# 清理过期数据（先看再执行）
/root/bin/purge-old.sh --dry
/root/bin/purge-old.sh

# 看出问题的地方
journalctl -u 2ke-dispatcher -n 30
tail -50 /var/log/ruoyi.log | grep -i error
```

### 三个常见故障

**后台 502**

```bash
systemctl status ruoyi-app
journalctl -u ruoyi-app -n 50 | grep -i error
```

多数是 MySQL 或 Redis 连不上，配置改过没重启。

**「执行采集失败：Failed to exec spawn helper」**

JDK 被系统升级了，但进程还是旧的。`systemctl restart ruoyi-app` 即可。`jdk-guard.timer` 每 30 分钟检查一次，会自动处理。

**讲座采集 403**

TGC 过期。采集器会用 `cas-auth.json` 里的账号密码自动重登；持续失败说明教务系统改了登录流程，需要更新 `cas-auth.json`。

---

## 技术栈

采集与分发用 Python，不依赖框架，只用 `pymysql` 和 `cryptography` 两个包。数据落 MySQL，Redis 给若依做缓存。后台基于 RuoYi-Vue（Spring Boot 3 + MyBatis + Spring Security + Vue 3 + Element Plus + Vite）。调度全部用 systemd 与 cron，没有消息队列，没有微服务。

三个核心机制：活动去重用 `(first_seen, activity_id)` 二元游标，避免同秒多条记录漏读；投递幂等靠 `UNIQUE(activity_id, subscriber_id)`，先占位再发送，重复采集不会重复推送；讲座登录态走 TGC → ticket → session 三级票据链，失效自动重登。

详细设计、踩坑记录和运维手册见 `05-文档/SYSTEM-档案.md`。
