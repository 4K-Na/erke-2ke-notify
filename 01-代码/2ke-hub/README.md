# 2ke-hub · 采集与存储层

集美大学第二课堂新活动采集器。**只采集、只落库，不发任何通知。**
通知层后续接入时只读 `activities` / `deliveries` 两张表，不需要改动本模块。

## 管理后台

```
地址：  http://<SERVER_IP>:18089
认证：  HTTP Basic（用户名 admin，密码见 /root/.2ke_admin_pass）
服务：  2ke-hub-admin.service（Streamlit 1.66，venv 在 /opt/2ke-hub/venv）
反代：  受保护站点在 /etc/nginx/conf.d/zz-2ke-admin.conf
        注意文件名必须以 z 开头 —— 18089 端口上 openclaw 站点是默认 server，
        排序靠前的配置会把它顶掉。
```

五个页面：

| 页面 | 内容 |
|---|---|
| 概览 | 订阅人数、今日新活动、今日/累计发送、投递成功率、14 天趋势图、当前开放活动 |
| 订阅者 | 增删改查、启停、按通道（wxpusher/wecom/email/rss）管理 |
| 投递记录 | 状态筛选（pending/sent/failed）、失败重试、90 天清理 |
| 活动库 | 按状态/级别/学院/关键词筛选 169 条活动，可导出 CSV |
| 运维 | 手动采集、Cookie 到期时间、采集日志、库状态、服务状态 |

改代码后重启：`systemctl restart 2ke-hub-admin`

## 部署

```
/opt/2ke-hub/
├── collector.py           采集器主程序（systemd 管理）
└── data/
    ├── 2ke.db             SQLite 主库（WAL 模式）
    ├── 2ke.db-wal
    └── collector.lock     单实例锁
```

依赖：复用 `/opt/jmu-2ke/jmu_2ke_api.py`（RSC flight 解析 + 会话失效识别）与
`/opt/jmu-2ke/2ke_cookie.json`（登录 Cookie），**这两个文件本身不改动**。

服务：`2ke-hub-collector.service`（User=jmu2ke，Restart=always，MemoryMax=256M）

```bash
systemctl status  2ke-hub-collector
systemctl restart 2ke-hub-collector
journalctl -u 2ke-hub-collector -f
```

## 数据表

| 表 | 用途 | 写入方 |
|---|---|---|
| `activities` | 活动主表，按活动 ID 唯一 | 采集器 |
| `fetch_log` | 每次采集的耗时/字节/成功与否 | 采集器 |
| `subscribers` | 订阅者（通道 + 外部 ID） | **通知层** |
| `rules` | 订阅规则（关键词/级别/学院/学分下限/静默时段） | **通知层** |
| `deliveries` | 投递记录，`UNIQUE(activity_id, subscriber_id)` 保证不重发 | **通知层** |

### activities 关键列

- `id` — 2ke 活动 ID，主键，天然幂等键
- `state` — `open` / `ended`
- `first_seen` — 首次被采集到的时间（**通知层靠这个判断"新活动"**）
- `last_seen` — 最近一次被采集到的时间
- `changed_count` — 状态真正发生变化的次数（不是采集次数）
- `activity_type_code` — `yard`（院级）/ `school`（校级）
- `dept_label` — 主办学院/部门
- `credit_total` — 学分数值
- `signin_start` / `signin_end` — 报名窗口
- `raw` — 原始 JSON，便于后续重新解析

## 通知层接入约定

新活动的判定，不要用内存集合，直接查库：

```sql
-- 某时间点之后首次出现的活动
SELECT * FROM activities
WHERE first_seen > ? AND state = 'open'
ORDER BY first_seen;

-- 投递幂等：重复执行不会重发
INSERT INTO deliveries (activity_id, subscriber_id, channel, status, created_at)
VALUES (?, ?, ?, 'pending', ?)
ON CONFLICT(activity_id, subscriber_id) DO NOTHING;
```

## 运维注意

1. **Cookie 会过期**（当前到期 2026-11-20）。失效时采集器会打
   `SESSION_EXPIRED` 并退避 30 分钟重试，但不会自动恢复，必须更新
   `/opt/jmu-2ke/2ke_cookie.json`（用 `/opt/jmu-2ke/set-cookie.sh`）。
   建议加一条告警：`fetch_log` 里连续 `ok=0` 超过 2 小时就推给管理员。

2. **不要和老服务 `jmu-2ke-watch` 同时跑**。两者都会轮询 dashboard，
   同时开会双倍请求 2ke。老服务当前是 `disabled` + `inactive`，
   以后只用其中一个。

3. **采集频率不要缩短**。实测单次响应 298,738 字节（291 KB），
   服务器不返回 gzip、也不支持 ETag/Last-Modified 条件请求，
   所以每次都是全量。480s 间隔 = 每天 180 次 ≈ 52.5 MB 出站 ≈ 1.58 GB/月。
   1000 人订阅和 10 人订阅，这个数字完全一样（采集与用户数无关）。

4. **已知数据特性**（不是 bug）：
   - 同一个活动可能返回多条记录（不同报名批次），ID 相同而
     `signup_record_id` 不同 —— 主表按活动 ID 去重，只留一条。
   - 刚结束的活动可能同时出现在 `open` 和 `ended` 列表里，
     采集器固定「先写 ended、后写 open」，保证 `open` 状态最终生效。

## 常用命令

```bash
# 打印库内统计 + 当前 open 活动
sudo -u jmu2ke python3 /opt/2ke-hub/collector.py --stats

# 手动采一次
sudo -u jmu2ke python3 /opt/2ke-hub/collector.py --once

# 直接查库
sudo -u jmu2ke python3 -c "
import sqlite3
c = sqlite3.connect('/opt/2ke-hub/data/2ke.db')
for r in c.execute(\"SELECT title, credit_total, start_at, dept_label FROM activities WHERE state='open' ORDER BY start_at\"):
    print(r)
"

# 备份
sudo -u jmu2ke sqlite3 /opt/2ke-hub/data/2ke.db ".backup /opt/2ke-hub/data/2ke.db.bak"
```
