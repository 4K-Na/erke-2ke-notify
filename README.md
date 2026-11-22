# 第二课堂通知系统

集美大学第二课堂活动与教务讲座的通知推送系统。抓取校内两个数据源，发现新内容后推送到学生微信。

服务于 30+ 名学生，日推送数十条，全自动运行。

---

## 这个仓库能做什么

**在一台全新的 Ubuntu 24.04 机器上，从零恢复整套服务。**

代码、配置、数据库结构、部署脚本、运维脚本全在这里。唯一需要你自己填的是凭据（企业微信密钥、教务账号密码、数据库密码）——这些以 `*.example` 模板形式提供。

---

## 系统做什么

```
第二课堂官网 (2ke.jmu.edu.cn)
  → collector_mysql.py（每 8 分钟）
  → t_activity 表
  → dispatcher.py（每 2 分钟，二元游标去重）
  → 企业微信 → 学生微信

教务系统 (jwxt.jmu.edu.cn)
  → collector_jwxt.py（每 30 分钟，CAS 自动登录）
  → t_lecture 表 + 直接推送
  → 企业微信 → 学生微信

管理后台（若依 Spring Boot + Vue 3）
  https://域名:18443/  → 列表、开关、手动推送
```

---

## 目录说明

```
.
├── 01-代码/
│   ├── 2ke-hub/           活动采集 + 分发（Python，核心）
│   │   ├── collector_mysql.py   抓官网，写 t_activity
│   │   ├── dispatcher.py        扫新活动，发企业微信（1100 行，最复杂）
│   │   ├── wecom_verify.py      企业微信回调验签
│   │   └── admin.py             Streamlit 运维面板（线上未启用）
│   ├── jwxt/              教务讲座采集（Python）
│   │   ├── collector_jwxt.py    抓讲座，直接推送
│   │   └── cas_auto_login.py    CAS 自动登录，拿 TGC
│   ├── jmu-2ke/           2ke 官网 API 客户端（Python）
│   ├── ruoyi-backend/     若依后端（Spring Boot 3 / JDK 17）
│   ├── ruoyi-frontend/    若依前端（Vue 3 / Element Plus / Vite）
│   ├── 2ke-subscribe/     微信插件订阅页（静态 HTML）
│   └── requirements.txt   Python 依赖（只有 2 个包）
│
├── 02-配置/
│   ├── etc/nginx/         nginx 完整配置（站点、限流、反代）
│   ├── etc/systemd/       全部 unit（服务 + 定时器）
│   ├── scripts/           运维脚本
│   │   ├── full-backup.sh   全量备份（代码+配置+数据+凭据）
│   │   ├── purge-old.sh     过期数据清理
│   │   └── jdk-guard.sh     JDK 变更后自动重启（防 spawn 失败）
│   ├── crontab.txt        定时任务清单
│   └── nginx-full.conf    nginx -T 完整输出（参考用）
│
├── 03-数据/
│   └── init.sql           数据库初始化（40 张表 + 菜单/字典/配置）
│
├── 05-文档/
│   ├── SYSTEM-档案.md（主文档）   ← 系统全貌、踩坑记录、运维手册
│   ├── 审计-数据与采集链路.md
│   ├── 审计-推送与后台.md
│   ├── 审计-运维安全隐私.md
│   └── 安全扫描报告.md
│
└── deploy.sh              一键部署脚本（Ubuntu 24.04）
```

---

## 从零恢复：完整步骤

### 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| OS | Ubuntu 24.04 | 其他发行版需调整 |
| Python | 3.12 | 采集器 |
| JDK | 17 | 若依后端 |
| Node | 20 | 前端构建 |
| Maven | 3.8+ | 后端编译 |
| MySQL | 5.7 或 8.0 | 端口随意，配置里改 |
| Redis | 7.0 | 若依缓存 |
| nginx | 1.24 | 反代 + 静态托管 |

**最低配置**：2 核 2G（1.6G 也能跑，但 swap 会很紧张）

### 第一步：拉代码

```bash
git clone <你的仓库地址> /opt/erke-source
cd /opt/erke-source
```

### 第二步：装系统依赖

```bash
apt update
apt install -y python3 python3-pip python3-venv openjdk-17-jdk-headless \
               nginx curl git maven
# Node 20（Ubuntu 源里的版本太老）
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
```

### 第三步：装 MySQL 和 Redis

```bash
apt install -y mysql-server redis-server
systemctl enable --now mysql redis-server
```

建库并设置密码：

```sql
CREATE DATABASE ry-2ke CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
ALTER USER 'root'@'localhost' IDENTIFIED BY '你的数据库密码';
FLUSH PRIVILEGES;
```

Redis 设置密码（`/etc/redis/redis.conf`）：

```
requirepass 你的Redis密码
```

然后 `systemctl restart redis-server`。

### 第四步：导入数据库结构

```bash
mysql -uroot -p ry-2ke < 03-数据/init.sql
mysql -uroot -p ry-2ke -e "show tables" | wc -l    # 应该 40
```

**默认管理员**：`admin` / `admin123`（登录后立刻改）

### 第五步：部署 Python 采集器

```bash
# 建运行用户
useradd -r -s /usr/sbin/nologin -M jmu2ke

# 复制代码
cp -r 01-代码/2ke-hub  /opt/
cp -r 01-代码/jwxt     /opt/
cp -r 01-代码/jmu-2ke  /opt/

# 装依赖（只有 2 个包）
pip3 install --break-system-packages -r 01-代码/requirements.txt

# 权限
chown -R jmu2ke:jmu2ke /opt/2ke-hub /opt/jmu-2ke
chown -R root:root /opt/jwxt
chmod 700 /opt/jwxt
```

### 第六步：填写凭据（关键）

```bash
# ① 企业微信配置
cp /opt/2ke-hub/wecom.json.example /opt/2ke-hub/wecom.json
vi /opt/2ke-hub/wecom.json
#   corp_id      企业微信后台 → 我的企业 → 企业ID
#   agent_id     应用管理 → 自建应用 → AgentId
#   corp_secret  应用 → Secret
#   aes_key      应用 → 接收消息 → EncodingAESKey
#   token        应用 → 接收消息 → Token
#   admin_userid 你的企业微信 UserID（接收告警用）

# ② 数据库连接（两个地方都要）
cp /opt/2ke-hub/db.json.example /opt/2ke-hub/db.json
cp /opt/jwxt/db.json.example    /opt/jwxt/db.json
#   改 host / port / password

# ③ 教务系统账号（自动登录拿 TGC）
cp /opt/jwxt/cas-auth.json.example /opt/jwxt/cas-auth.json

# ④ 2ke 官网 cookie
cp /opt/jmu-2ke/2ke_cookie.json.example /opt/jmu-2ke/2ke_cookie.json
#   浏览器登录 2ke.jmu.edu.cn → F12 → Application → Cookies → SESSION 和 TGC

# 权限
chmod 600 /opt/2ke-hub/wecom.json /opt/2ke-hub/db.json \
          /opt/jwxt/db.json /opt/jwxt/cas-auth.json /opt/jmu-2ke/2ke_cookie.json
chown jmu2ke:jmu2ke /opt/2ke-hub/*.json /opt/jmu-2ke/*.json
```

### 第七步：部署 systemd 服务

```bash
cp 02-配置/etc/systemd/system/*.service /etc/systemd/system/
cp 02-配置/etc/systemd/system/*.timer   /etc/systemd/system/
systemctl daemon-reload

systemctl enable --now 2ke-hub-mysql         # 每 8 分钟抓活动
systemctl enable --now 2ke-dispatcher        # 每 2 分钟发推送
systemctl enable --now 2ke-wecom             # 企业微信回调
systemctl enable --now jwxt-collector.timer  # 每 30 分钟抓讲座
systemctl enable --now jdk-guard.timer       # 防 JDK 升级故障
systemctl enable --now qr-upload             # 二维码上传
```

### 第八步：编译部署后端

```bash
cd 01-代码/ruoyi-backend

# 先改配置
vi ruoyi-admin/src/main/resources/application-druid.yml   # 数据库地址/密码
vi ruoyi-admin/src/main/resources/application.yml          # Redis 密码、上传路径

mvn clean package -pl ruoyi-system,ruoyi-admin -am -DskipTests

mkdir -p /opt/ruoyi
cp ruoyi-admin/target/ruoyi-admin.jar /opt/ruoyi/
cp ../../02-配置/etc/systemd/system/ruoyi-app.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now ruoyi-app
```

### 第九步：构建部署前端

```bash
cd 01-代码/ruoyi-frontend
npm install
npm run build:prod          # 约 1 分钟，2 核机器会占满 CPU

mkdir -p /opt/ruoyi-ui
cp -r dist /opt/ruoyi-ui/
```

### 第十步：配置 nginx

```bash
cp 02-配置/etc/nginx/conf.d/*.conf /etc/nginx/conf.d/
cp 02-配置/etc/nginx/sites-available/site-main.conf /etc/nginx/sites-available/

# 改域名和证书路径（模板里是 example.com）
vi /etc/nginx/sites-available/site-main.conf

# 申请证书
certbot --nginx -d 你的域名

# 启用
ln -s /etc/nginx/sites-available/site-main.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 第十一步：定时任务

```bash
crontab 02-配置/crontab.txt
crontab -l    # 确认
```

内容：

```
17 4 * * *   数据库备份
20 4 * * *   过期数据清理
50 4 * * *   全量备份
23 9 * * *   二维码临期提醒
30 4 * * 0   图片清理
```

### 第十二步：验证

```bash
# 服务状态
systemctl is-active 2ke-hub-mysql 2ke-dispatcher jwxt-collector.timer ruoyi-app nginx

# 采集日志
journalctl -u 2ke-hub-mysql -n 5
journalctl -u 2ke-dispatcher -n 5
journalctl -u jwxt-collector -n 5

# 后台可访问
curl -k https://你的域名:18443/ -o /dev/null -w "%{http_code}\n"    # 200

# 登录
curl -X POST https://你的域名:18443/prod-api/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"admin123"}'
# 期望 {"code":200,"token":"..."}
```

---

## 日常运维

### 看状态

```bash
systemctl status 2ke-hub-mysql 2ke-dispatcher jwxt-collector.timer ruoyi-app
journalctl -u 2ke-hub-mysql -n 20      # 采集最近一轮
journalctl -u 2ke-dispatcher -n 30     # 推送记录
tail -50 /var/log/ruoyi.log | grep -i error
```

### 常见故障

**后台打不开，502**

```bash
systemctl status ruoyi-app
journalctl -u ruoyi-app -n 50 | grep -i error
# 多数是 MySQL 或 Redis 连不上
```

**「执行采集失败：Cannot run program / Failed to exec spawn helper」**

JDK 被系统升级了但进程没重启：

```bash
systemctl restart ruoyi-app
# jdk-guard.timer 也会自动处理，最多 30 分钟
```

**讲座采集 403**

TGC 过期。采集器会自动重登；不行就检查：

```bash
vi /opt/jwxt/cas-auth.json
systemctl start jwxt-collector
journalctl -u jwxt-collector -n 20
```

**推送没发出去**

```bash
cat /opt/jwxt/push.json                  # 讲座推送开关
cat /opt/2ke-hub/dispatch_state.json     # 活动水位
journalctl -u 2ke-dispatcher -n 30 | grep -E '✅|失败|跳过'
```

### 手动操作

```bash
systemctl start jwxt-collector            # 立即采集讲座
python3 /opt/2ke-hub/collector_mysql.py   # 立即采集活动
/root/bin/full-backup.sh                  # 全量备份
/root/bin/purge-old.sh --dry              # 清理过期数据（先试运行）
```

---

## 关键设计（读代码前看这个）

**1. 活动去重：二元游标**

不用单一时间戳，用 `(first_seen, activity_id)` 元组作游标。同一秒可能产生多条活动，单用时间戳会漏读。见 `dispatcher.py` 的水位逻辑。

**2. 投递幂等：先占位再发送**

`t_delivery` 有 `UNIQUE(activity_id, subscriber_id)`。发送前先 INSERT 占位，插入成功才调用企业微信接口。插入失败说明已发过，直接跳过。重复采集、并发、重试都不会重复打扰学生。

**3. 讲座登录态：三级票据链**

```
TGC（长期）→ ticket（一次性）→ SESSION（业务会话）
```

任一级失效就走一遍重登。`cas_auto_login.py` 复现了前端的 RSA 加密（`__RSA__` 前缀 + PKCS#1 v1.5），不需要浏览器也能登录。

**4. 学分显示：取最大值**

学校部分活动采用分档发放（如「前 10 名 3 学分，其余 1 学分」），`credit` 字段是 JSON 数组。系统解析后取最大值作为「最高 X 学分」，并在文案标注是否分档。

---

## 已知限制

**1. 二维码 7 天需手工更换**

企业微信插件二维码没有开放 API，爬虫也被风控拦。到期前系统发提醒，需要在后台点两下换掉。

**2. 讲座采集依赖 TGC**

TGC 有效期约 16 小时。采集器会自动重登；但账号密码变了、或教务系统改登录流程时，需手工更新 `cas-auth.json`。

**3. 单机部署，无冗余**

所有服务在一台机器上。备份做了三份（本机、异地服务器、个人电脑），恢复靠手动执行上面第十二步。

**4. 无自动化测试**

3900 行 Python 没有单元测试，改动靠「跑起来看看」验证。

---

## 更新日志

详细记录见 `05-文档/SYSTEM-档案.md`。

| 日期 | 变更 |
|---|---|
| 2026-11 | 加入 JDK 变更自检（jdk-guard），防止升级后 spawn 失败 |
| 2026-11 | 讲座推送接入，CAS 自动登录实现 |
| 2026-10 | 三路安全审计 + 修复；关闭无关端口；数据库密码外置 |
| 2026-10 | 后台加入「强制刷新」按钮、讲座列表默认只看开放 |
| 2026-10 | 订阅页改版；二维码临期提醒 |

---

## 许可

个人项目，供学习参考。

业务逻辑（去重游标、幂等投递、票据续期）是通用的，可以直接拿去做别的校园系统。

**注意**：`01-代码/ruoyi-backend` 和 `01-代码/ruoyi-frontend` 基于 [RuoYi-Vue](https://gitee.com/y_project/RuoYi-Vue)，遵循其 MIT 许可。
