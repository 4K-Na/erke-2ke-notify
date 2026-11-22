# ERKE · 第二课堂通知系统 完整快照

导出时间：2026-11-22
来源服务器：<SERVER_IP>（阿里云 ECS，Ubuntu 24.04）
导出方式：服务器全量打包 `full-backup.sh` → SFTP 下载 → 本地重组

---

## 目录结构

```
ERKE/
├─ 01-代码/                     源码，可直接阅读和修改
│   ├─ 2ke-hub/                 第二课堂采集 + 企业微信分发（Python）
│   ├─ jwxt/                    教务讲座采集（Python，含 CAS 自动登录）
│   ├─ jmu-2ke/                 2ke 官网 API 客户端（Python）
│   ├─ ruoyi-backend/           若依后端源码（Java / Spring Boot）
│   ├─ ruoyi-frontend/          若依前端源码（Vue 3）
│   └─ 2ke-subscribe/           微信插件订阅页（静态 HTML）
│
├─ 02-配置/                     服务器配置
│   ├─ etc/nginx/               全部 nginx 配置（含站点、限流、证书指向）
│   ├─ etc/systemd/system/      全部 systemd unit
│   ├─ etc/logrotate.d/         日志轮转规则
│   ├─ scripts/                 运维脚本（备份、消融、JDK 自检）
│   ├─ crontab.txt              定时任务清单
│   ├─ nginx-full.conf          nginx -T 的完整输出（含所有 include）
│   ├─ running-services.txt     导出时运行中的服务列表
│   └─ *.tar.gz                 原始打包（code / config / secrets / full）
│
├─ 03-数据/
│   └─ db-ry-2ke.sql.gz         全库 dump（40 张表，明文约 2.7MB）
│
├─ 04-凭据/                     敏感，勿外传
│   ├─ wecom.json               企业微信 CorpID / Secret / AgentId
│   ├─ cas-auth.json            教务系统账号密码（自动登录用）
│   ├─ cookie.txt / tgc.txt     2ke 会话 cookie / CAS 票据
│   ├─ 2ke_cookie.json          2ke 官网登录 cookie
│   ├─ db.json ×2               数据库连接配置
│   └─ push.json / state.json   推送开关、采集状态
│
└─ 05-文档/
    ├─ SYSTEM-档案.md（主文档）  系统全貌、架构、踩坑记录、运维手册
    ├─ 审计-数据与采集链路.md
    ├─ 审计-推送与后台.md
    ├─ 审计-运维安全隐私.md
    └─ 安全扫描报告.md
```

---

## 快速了解这个系统

**它做什么**：监控集美大学第二课堂官网的活动 + 教务系统的讲座，有新的就推送到学生微信。

**两条独立链路**：

```
2ke 官网 dashboard (Next.js RSC)
  → collector_mysql.py（systemd，每 8 分钟）
  → t_activity 表
  → dispatcher.py（systemd，每 2 分钟）
  → 企业微信 → 学生微信

教务 jwxt (EAMS)
  → collector_jwxt.py（systemd timer，每 30 分钟）
  → t_lecture 表 + 直接推送
  → 企业微信 → 学生微信
```

**技术栈**：Python 3.12（无框架）+ MySQL 5.7 + Redis + 若依（Spring Boot 3 / Vue 3）+ nginx

详细说明见 `05-文档/SYSTEM-档案.md`，那份文档覆盖了架构、数据表、调度、所有踩过的坑和运维命令。

---

## 恢复方法

### 恢复数据库

```bash
zcat 03-数据/db-ry-2ke.sql.gz | mysql -h127.0.0.1 -P3307 -uroot -p ry-2ke
```

### 恢复代码

```bash
# Python 采集器
cp -r 01-代码/2ke-hub   /opt/
cp -r 01-代码/jwxt      /opt/
cp -r 01-代码/jmu-2ke   /opt/
chown -R jmu2ke:jmu2ke /opt/2ke-hub /opt/jmu-2ke

# 后端（编译）
cd 01-代码/ruoyi-backend
mvn clean package -pl ruoyi-system,ruoyi-admin -am -DskipTests

# 前端（构建）
cd 01-代码/ruoyi-frontend
npm install && npm run build:prod

# 订阅页
cp -r 01-代码/2ke-subscribe /var/www/
```

### 恢复配置

```bash
cp -r 02-配置/etc/nginx    /etc/
cp -r 02-配置/etc/systemd  /etc/
cp 02-配置/crontab.txt /tmp/ && crontab /tmp/crontab.txt
systemctl daemon-reload && nginx -t && systemctl reload nginx
```

### 恢复凭据

把 `04-凭据/` 里的文件放回各自目录，权限改 600：

```bash
chmod 600 /opt/2ke-hub/wecom.json /opt/jwxt/{cookie.txt,tgc.txt,cas-auth.json,db.json}
chown jmu2ke:jmu2ke /opt/2ke-hub/db.json /opt/jmu-2ke/2ke_cookie.json
```

---

## 注意事项

**1. 04-凭据 里是明文密码和密钥**

包括教务系统账号密码、企业微信 Secret、数据库密码。拷贝 U 盘、发人之前想清楚。

**2. 01-代码 里也含凭据**

因为服务器打包时没排除（备份需要完整性）。所以 `01-代码/2ke-hub/wecom.json`、`01-代码/jwxt/cas-auth.json` 这些文件同样敏感。

**3. 数据库 dump 含学生姓名**

`t_subscriber`、`t_delivery` 里有学生真实姓名和班级。按个人信息对待。

**4. 这个快照是某一时刻的静态副本**

服务器上的代码会继续变化。要最新版本，重新跑服务器上的 `/root/bin/full-backup.sh` 再下载。

---

## 关键信息（部署时需要）

| 项 | 值 |
|---|---|
| 域名 | example.com |
| 后台入口 | https://example.com:18443/ |
| 订阅页 | https://example.com/ |
| 后端端口 | 18081（仅本机） |
| MySQL | 127.0.0.1:3307，库 ry-2ke |
| Redis | 127.0.0.1:6379（有密码，见 ruoyi.conf） |
| 企业微信 | CorpID <WECOM_CORPID>，AgentId 1000002 |
| 定时任务 | 见 02-配置/crontab.txt + systemd timer |
