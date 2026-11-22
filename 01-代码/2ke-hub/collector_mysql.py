#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2ke-hub 采集器 · MySQL 版
=========================
把集美大学第二课堂活动直接写入若依的 MySQL 库（ry-2ke.t_activity），
供 RuoYi 后台直接做 CRUD 与统计，不再经过 SQLite。

数据源：GET https://2ke.jmu.edu.cn/dashboard  (Header: RSC: 1)
解析：复用 /opt/jmu-2ke/jmu_2ke_api.py

用法：
    python3 collector_mysql.py --once
    python3 collector_mysql.py                 # 守护运行
    python3 collector_mysql.py --stats
"""
import argparse
import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta, timezone

import pymysql

sys.path.insert(0, "/opt/jmu-2ke")
try:
    from jmu_2ke_api import Client, SessionExpired, PayloadInvalid, COOKIE_FILE
except Exception as e:  # pragma: no cover
    sys.exit("无法导入 jmu_2ke_api: %r" % (e,))

CST = timezone(timedelta(hours=8))
def _load_db_config():
    """数据库连接参数从 db.json 读（600 权限），不硬编码在源码里。"""
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.json")
    with open(_p, "r", encoding="utf-8") as _f:
        return json.load(_f)


_DB_PWD = _load_db_config()["password"]


DB = dict(unix_socket="/run/ruoyi-mysql/mysql.sock", user="root",
          password=_DB_PWD, database="ry-2ke", charset="utf8mb4",
          autocommit=False)
INTERVAL = 480
JITTER = 30


def now_iso():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def conn():
    c = pymysql.connect(**DB)
    c.autocommit(False)
    return c


_DT_FAIL = {"n": 0}          # _dt 解析失败计数（修复 P2-1：不再静默变 NULL）


def _dt(v):
    """'2026-10-22 09:30' / '2026-10-22 09:30:00' / '' -> MySQL DATETIME 或 None

    修复 P2-1：解析失败不再静默返回 None —— 计数并打日志。否则平台把时间格式换成
    带毫秒/带 T 的形态时，start_at/end_at/signin_* 会**静默**全部变 NULL，
    日志里一个字都没有。
    注意：这里只做"本地时间"口径的解析；带 Z/+08:00 的时区串刻意不接受
    （那应该由 jmu_2ke_api._local() 先转成北京时间，否则会静默错 8 小时）。
    """
    if not v:
        return None
    v = str(v).strip()
    if not v or v in ("None", "null"):
        return None
    cand = v
    if "T" in cand and not cand.endswith("Z") and "+" not in cand[10:]:
        cand = cand.replace("T", " ")
    if "." in cand:
        cand = cand.split(".", 1)[0]          # 丢掉毫秒
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(cand, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    _DT_FAIL["n"] += 1
    if _DT_FAIL["n"] <= 3 or _DT_FAIL["n"] % 50 == 0:
        print("  !! 时间字段无法解析（第 %d 次，共 %d 次）：%r —— 该字段会落 NULL"
              % (_DT_FAIL["n"], _DT_FAIL["n"], v[:60]), flush=True)
    return None


class TracingClient(Client):
    last_ms = 0
    last_bytes = 0

    def flight(self, path="/dashboard", rsc=True):
        t0 = time.time()
        txt = super().flight(path, rsc)
        self.last_ms = int((time.time() - t0) * 1000)
        self.last_bytes = len(txt.encode("utf-8"))
        return txt


UPSERT = """
INSERT INTO t_activity
  (activity_id, title, activity_type, activity_type_label, dept_label,
   creator_college, credit_total, credit_detail, credit_type_name,
   start_at, end_at, signin_start, signin_end, signup_way, address, quota,
   act_state, first_seen, last_seen, raw_json, create_by, create_time, remark)
VALUES
  (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'collector',NOW(),NULL)
ON DUPLICATE KEY UPDATE
  title=VALUES(title), activity_type=VALUES(activity_type),
  activity_type_label=VALUES(activity_type_label), dept_label=VALUES(dept_label),
  creator_college=VALUES(creator_college), credit_total=VALUES(credit_total),
  credit_detail=VALUES(credit_detail), credit_type_name=VALUES(credit_type_name),
  start_at=VALUES(start_at), end_at=VALUES(end_at),
  signin_start=VALUES(signin_start), signin_end=VALUES(signin_end),
  signup_way=VALUES(signup_way), address=VALUES(address), quota=VALUES(quota),
  act_state=VALUES(act_state), last_seen=VALUES(last_seen),
  raw_json=VALUES(raw_json), update_time=NOW()
"""


def _credit_json(credit, limit=500):
    """序列化学分明细。

    credit_detail 字段是 varchar(500)，直接 [:500] 截断会把 JSON 切成非法串，
    导致下游 parse_credit() 解析失败、退化成没意义的 credit_total。
    超长时逐档减少，保证存进去的永远是合法 JSON。
    """
    if not isinstance(credit, (list, dict)):
        return None
    try:
        full = json.dumps(credit, ensure_ascii=False)
    except Exception:
        return None
    if len(full) <= limit:
        return full
    if isinstance(credit, list):
        for n in range(len(credit) - 1, 0, -1):
            try:
                part = json.dumps(credit[:n], ensure_ascii=False)
            except Exception:
                break
            if len(part) <= limit:
                return part
    return None


def _quota(v):
    """名额：0/负数归一成 NULL（修复 P2-3）。

    平台 `activity.number=0` 不是解析错误，但原样落库会让推送文案出现
    「名额：0 人」，学生直接理解成"没名额了"。库里存 NULL，展示层按"不限"处理
    （dispatcher.render 对 falsy 值本来就走"不限"）。
    """
    if v is None:
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def row_of(a, state, ts):
    credit = a.get("credit")
    credit_json = _credit_json(credit, 500)
    sw = a.get("signin_window") or [None, None]
    raw = a.get("raw")
    raw_json = json.dumps(raw, ensure_ascii=False) if raw is not None else None
    return (
        str(a.get("id") or a.get("activityId") or "")[:64],
        (a.get("title") or "")[:500],
        (a.get("activity_type_code") or "")[:20],
        (a.get("activity_type_label") or "")[:50],
        (a.get("dept_label") or "")[:120],
        (a.get("creator_college") or "")[:200],
        a.get("credit_total"),
        credit_json,
        (a.get("credit_type_name") or "")[:255],
        _dt(a.get("start_local")), _dt(a.get("end_local")),
        _dt(sw[0] if len(sw) > 0 else None), _dt(sw[1] if len(sw) > 1 else None),
        (a.get("signin_way") or "")[:30],
        (a.get("address") or "")[:255],
        _quota(a.get("quota")),
        state, ts, ts, raw_json,
    )


def collect_once(c, client, verbose=True):
    ts = now_iso()
    ok = 0
    err = None
    n_open = n_ended = n_new = 0
    ms = nbytes = None
    t0 = time.time()
    try:
        # snapshot() 内部已做载荷断言（缺失 primary/ended、open+ended 全为空
        # 都会抛 PayloadInvalid）—— 修复 A8。旧版这里什么都不校验：Next.js 一旦把
        # `"primary":[...]` 换成引用块形态，解析静默返回 {}，于是 open 恒为 0、
        # ended 照常刷新 last_seen，日志仍是 `ok ... open=0 ended=148`，
        # 后台"一切正常"，而新活动永久不入库、学生再也收不到推送。
        snap = client.snapshot()
        ms = getattr(client, "last_ms", None)
        nbytes = getattr(client, "last_bytes", None)
        with c.cursor() as cur:
            # 先 ended 后 open：交集时以 open 为准
            for state, arr in (("ended", snap["ended"]), ("open", snap["open"])):
                for a in arr:
                    r = row_of(a, state, ts)
                    if not r[0]:
                        continue
                    cur.execute(UPSERT, r)
                    if cur.rowcount == 1:      # 1 = 新插入
                        n_new += 1
        # ---- 陈旧回收（P0-1）：上游把活动移出 open/ended 后，库里会永远卡 open ----
        # 用 last_seen 兜底而不是"本轮没返回就标 gone"，这样不依赖上游列表是否被截断。
        STALE_HOURS = 12
        with c.cursor() as _cur:
            _cur.execute("UPDATE t_activity SET act_state='gone'"
                         " WHERE act_state='open' AND last_seen < DATE_SUB(NOW(), INTERVAL %s HOUR)",
                         (STALE_HOURS,))
            _stale = _cur.rowcount
        if _stale:
            print("[%s]   陈旧回收：%d 条超过 %d 小时未出现在上游，标为 gone"
                  % (ts[11:19], _stale, STALE_HOURS), flush=True)
        c.commit()

        n_open = len(snap["open"])
        n_ended = len(snap["ended"])
        ok = 1

        # 修复 A7：每轮成功采集后把滚动后的新 session token 落盘。
        # 不写的话进程不重启时靠内存里的 token 一直续着，重启就回退到文件里的旧
        # token（30 天 exp），一过就是永久 SESSION_EXPIRED。落盘失败不影响本轮采集。
        try:
            client.save_cookies()
        except Exception as e:
            print("[%s]   !! cookie 回写失败（不影响本轮入库）：%r"
                  % (ts[11:19], e), flush=True)
    except SessionExpired as e:
        err = "SESSION_EXPIRED: %r" % (e,)
        try:
            c.rollback()      # 修复 P2-11：与下面通用分支同款保护，rollback 本身失败
        except Exception:     # 也不能把异常抛出 collect_once（会打死守护进程）
            pass
    except PayloadInvalid as e:
        err = "PAYLOAD_INVALID: %s" % (e,)
        try:
            c.rollback()
        except Exception:
            pass
    except Exception as e:
        try:
            c.rollback()
        except Exception:
            pass
        err = "%s: %s" % (type(e).__name__, e)

    if verbose:
        if ok:
            print("[%s] ok %sms %sKB open=%d ended=%d new=%d (%.1fs)"
                  % (ts[11:19], ms, (nbytes or 0) // 1024, n_open, n_ended, n_new,
                     time.time() - t0), flush=True)
        else:
            print("[%s] FAIL %s" % (ts[11:19], err), flush=True)
    return ok, err


def print_stats(c):
    with c.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM t_activity")
        total = cur.fetchone()[0]
        cur.execute("SELECT act_state, COUNT(*) FROM t_activity GROUP BY act_state")
        by_state = cur.fetchall()
        cur.execute("""SELECT title, activity_type_label, credit_total, start_at, dept_label
                       FROM t_activity WHERE act_state='open'
                       ORDER BY start_at LIMIT 12""")
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM t_activity WHERE DATE(first_seen)=CURDATE()")
        today = cur.fetchone()[0]
    print("\n=== 库内统计 (ry-2ke.t_activity) ===")
    print("  活动总数:", total)
    for s, n in by_state:
        print("  状态=%-6s %s" % (s, n))
    print("  今日新发现:", today)
    print("\n=== 当前 open ===")
    for t, lv, cr, st, dp in rows:
        print("  %-30s %-6s %s学分  %s  %s"
              % ((t or "")[:30], lv or "-", cr if cr is not None else "-",
                 str(st or "-")[:16], (dp or "")[:12]))
    print()


def acquire_lock():
    try:
        import fcntl
    except ImportError:
        return None
    os.makedirs("/var/lib/2ke-hub", exist_ok=True)
    fh = open("/var/lib/2ke-hub/collector-mysql.lock", "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("已有采集器实例在运行。")
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--interval", type=int, default=INTERVAL)
    ap.add_argument("--jitter", type=int, default=JITTER)
    args = ap.parse_args()

    c = conn()
    if args.stats:
        print_stats(c)
        return

    if not os.path.exists(COOKIE_FILE):
        sys.exit("缺少 cookie: %s" % COOKIE_FILE)
    client = TracingClient.from_cookie_file()

    if args.once:
        ok, err = collect_once(c, client)
        print_stats(c)
        sys.exit(0 if ok else 2)

    _lock = acquire_lock()
    stopping = {"v": False}
    signal.signal(signal.SIGTERM, lambda *a: stopping.update(v=True))
    signal.signal(signal.SIGINT, lambda *a: stopping.update(v=True))

    try:
        print("会话到期：%s" % (client.session_expiry() or "未知"), flush=True)
    except Exception:
        pass
    print("开始采集 -> MySQL ry-2ke.t_activity，间隔 %ds + 0~%ds 抖动"
          % (args.interval, args.jitter), flush=True)

    fail = 0
    while not stopping["v"]:
        try:
            c.ping(reconnect=True)
        except Exception:
            try:
                c = conn()
            except Exception:
                pass
        ok, err = collect_once(c, client)
        if ok:
            fail = 0
            delay = args.interval + random.randint(0, args.jitter)
        else:
            fail += 1
            if err and err.startswith("SESSION_EXPIRED"):
                print("!! 会话失效，30 分钟后重试", flush=True)
                delay = 1800
            elif err and err.startswith("PAYLOAD_INVALID"):
                # 修复 A8：平台载荷结构变了（解析半失效）。这一轮什么都没写库，
                # 按普通失败退避重试并在日志留痕；dispatcher 的 40 分钟巡检会因为
                # last_seen 不再刷新而告警，不会再出现"看着一切正常、其实没有新活动"。
                delay = min(args.interval * min(fail, 6), 3600)
                print("!! 载荷解析失效（第 %d 次连续失败），%d 秒后重试" % (fail, delay),
                      flush=True)
            else:
                delay = min(args.interval * min(fail, 6), 3600)
        deadline = time.time() + delay
        while time.time() < deadline and not stopping["v"]:
            time.sleep(min(5, max(0, deadline - time.time())))
    c.close()
    print("已停止。", flush=True)


if __name__ == "__main__":
    main()
