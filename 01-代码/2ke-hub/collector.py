#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2ke-hub 采集器
==============
只做「采集 + 结构化落库」，不做任何通知。
通知层后续接入时读 activities / deliveries 两张表即可，无需改这里。

数据源：GET https://2ke.jmu.edu.cn/dashboard  (Header: RSC: 1)
解析：复用 /opt/jmu-2ke/jmu_2ke_api.py（RSC flight 解析 + 会话失效识别）
存储：/opt/2ke-hub/data/2ke.db (SQLite, WAL)

用法：
    python3 collector.py --once          # 采一次就退出
    python3 collector.py                 # 守护运行（systemd 用这个）
    python3 collector.py --interval 600  # 覆盖轮询间隔
    python3 collector.py --stats         # 只打印库内统计，不采集
"""

import argparse
import json
import os
import random
import signal
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/opt/jmu-2ke")
try:
    from jmu_2ke_api import Client, SessionExpired, COOKIE_FILE
except Exception as e:  # pragma: no cover
    sys.exit("无法导入 jmu_2ke_api: %r" % (e,))

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DB = os.path.join(DATA, "2ke.db")
LOCK = os.path.join(DATA, "collector.lock")
CST = timezone(timedelta(hours=8))

INTERVAL = 480      # 秒，与老服务一致
JITTER = 30         # 秒，避免整点打站点

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    id                  TEXT PRIMARY KEY,
    activity_id         TEXT,
    signup_record_id    TEXT,
    title               TEXT,
    address             TEXT,
    start_at            TEXT,
    end_at              TEXT,
    signin_start        TEXT,
    signin_end          TEXT,
    signin_way          TEXT,
    quota               INTEGER,
    credit_total        REAL,
    credit_detail       TEXT,
    activity_type_code  TEXT,
    activity_type_label TEXT,
    credit_type_id      TEXT,
    credit_type_name    TEXT,
    dept_id             TEXT,
    dept_label          TEXT,
    creator_college     TEXT,
    signup_type         TEXT,
    source_status       TEXT,
    state               TEXT NOT NULL,
    created_at          TEXT,
    updated_at          TEXT,
    first_seen          TEXT NOT NULL,
    last_seen           TEXT NOT NULL,
    changed_count       INTEGER NOT NULL DEFAULT 1,
    raw                 TEXT
);
CREATE INDEX IF NOT EXISTS idx_act_state      ON activities(state, start_at);
CREATE INDEX IF NOT EXISTS idx_act_first_seen ON activities(first_seen);
CREATE INDEX IF NOT EXISTS idx_act_type       ON activities(activity_type_code);
CREATE INDEX IF NOT EXISTS idx_act_dept       ON activities(dept_label);

CREATE TABLE IF NOT EXISTS fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    ok          INTEGER NOT NULL,
    http_ms     INTEGER,
    bytes       INTEGER,
    open_count  INTEGER,
    ended_count INTEGER,
    new_count   INTEGER,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_fetch_at ON fetch_log(at);

-- 以下两张表为通知层预留，采集器只建不写
CREATE TABLE IF NOT EXISTS subscribers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel     TEXT NOT NULL,
    external_id TEXT NOT NULL,
    label       TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    UNIQUE(channel, external_id)
);

CREATE TABLE IF NOT EXISTS rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    subscriber_id  INTEGER NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
    keywords       TEXT,
    activity_types TEXT,
    depts          TEXT,
    credit_min     REAL,
    quiet_hours    TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id   TEXT NOT NULL,
    subscriber_id INTEGER NOT NULL,
    channel       TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    attempt       INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT,
    created_at    TEXT NOT NULL,
    sent_at       TEXT,
    UNIQUE(activity_id, subscriber_id)
);
CREATE INDEX IF NOT EXISTS idx_del_status ON deliveries(status);
"""


def now_iso():
    return datetime.now(CST).isoformat(timespec="seconds")


def connect():
    os.makedirs(DATA, exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript(SCHEMA)
    c.commit()
    return c


class TracingClient(Client):
    """包一层，记录每次请求的真实耗时与响应字节数（不改动原始模块）。"""

    last_ms = 0
    last_bytes = 0

    def flight(self, path="/dashboard", rsc=True):
        t0 = time.time()
        txt = super().flight(path, rsc)
        self.last_ms = int((time.time() - t0) * 1000)
        self.last_bytes = len(txt.encode("utf-8"))
        return txt


def upsert(c, a, state, ts):
    """返回 True 表示首次见到这条活动。"""
    aid = a.get("id")
    if not aid:
        return False
    credit = a.get("credit")
    credit_json = (json.dumps(credit, ensure_ascii=False)
                   if isinstance(credit, (list, dict)) else None)
    sw = a.get("signin_window") or [None, None]
    raw = a.get("raw")
    raw_json = json.dumps(raw, ensure_ascii=False) if raw is not None else None

    vals = (
        a.get("activityId"), a.get("signup_record_id"), a.get("title"),
        a.get("address"), a.get("start_local"), a.get("end_local"),
        sw[0] if len(sw) > 0 else None, sw[1] if len(sw) > 1 else None,
        a.get("signin_way"), a.get("quota"), a.get("credit_total"), credit_json,
        a.get("activity_type_code"), a.get("activity_type_label"),
        a.get("credit_type_id"), a.get("credit_type_name"),
        a.get("dept_id"), a.get("dept_label"), a.get("creator_college"),
        a.get("signup_type"), a.get("status"),
        a.get("created_at"), a.get("updated_at"),
    )

    cur = c.execute("SELECT state FROM activities WHERE id=?", (aid,))
    prev = cur.fetchone()
    if prev is None:
        c.execute(
            """INSERT INTO activities
               (id, activity_id, signup_record_id, title, address, start_at, end_at,
                signin_start, signin_end, signin_way, quota, credit_total, credit_detail,
                activity_type_code, activity_type_label, credit_type_id, credit_type_name,
                dept_id, dept_label, creator_college, signup_type, source_status,
                created_at, updated_at, state, first_seen, last_seen, changed_count, raw)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
            (aid,) + vals + (state, ts, ts, raw_json),
        )
        return True

    # 只有状态真的变化才把 changed_count +1，避免每轮采集都把它刷成"一直变"
    state_changed = 1 if (prev["state"] or "") != state else 0
    c.execute(
        """UPDATE activities SET
             activity_id=?, signup_record_id=?, title=?, address=?, start_at=?, end_at=?,
             signin_start=?, signin_end=?, signin_way=?, quota=?, credit_total=?,
             credit_detail=?, activity_type_code=?, activity_type_label=?,
             credit_type_id=?, credit_type_name=?, dept_id=?, dept_label=?,
             creator_college=?, signup_type=?, source_status=?, created_at=?, updated_at=?,
             last_seen=?, changed_count=changed_count+?, raw=?, state=?
           WHERE id=?""",
        vals + (ts, state_changed, raw_json, state, aid),
    )
    return False


def collect_once(c, client, verbose=True):
    t0 = time.time()
    ts = now_iso()
    ok = 0
    err = None
    n_open = n_ended = n_new = 0
    ms = nbytes = None

    try:
        snap = client.snapshot()
        ms = getattr(client, "last_ms", None)
        nbytes = getattr(client, "last_bytes", None)

        with c:
            # 先落 ended，再落 open：同一活动可能同时出现在两个列表里（刚结束
            # 但仍在 primary 中的边界情况），必须让 open 的状态最终生效。
            for a in snap["ended"]:
                if upsert(c, a, "ended", ts):
                    n_new += 1
            for a in snap["open"]:
                if upsert(c, a, "open", ts):
                    n_new += 1
            n_open = len(snap["open"])
            n_ended = len(snap["ended"])
            c.execute(
                """INSERT INTO fetch_log
                   (at, ok, http_ms, bytes, open_count, ended_count, new_count, error)
                   VALUES (?,1,?,?,?,?,?,NULL)""",
                (ts, ms, nbytes, n_open, n_ended, n_new),
            )
        ok = 1
    except SessionExpired as e:
        err = "SESSION_EXPIRED: %r" % (e,)
    except Exception as e:
        err = "%s: %s" % (type(e).__name__, e)

    if not ok:
        try:
            with c:
                c.execute(
                    """INSERT INTO fetch_log
                       (at, ok, http_ms, bytes, open_count, ended_count, new_count, error)
                       VALUES (?,0,?,?,0,0,0,?)""",
                    (ts, ms, nbytes, err),
                )
        except Exception:
            pass

    if verbose:
        if ok:
            print("[%s] ok %sms %sKB open=%d ended=%d new=%d (%.1fs)"
                  % (ts[11:19], ms, (nbytes or 0) // 1024, n_open, n_ended, n_new,
                     time.time() - t0), flush=True)
        else:
            print("[%s] FAIL %s" % (ts[11:19], err), flush=True)
    return ok, err


def print_stats(c):
    def one(sql, *a):
        r = c.execute(sql, a).fetchone()
        return r[0] if r else None

    total = one("SELECT COUNT(*) FROM activities")
    print("\n=== 库内统计 ===")
    print("  活动总数       : %s" % total)
    print("  状态=open      : %s" % one("SELECT COUNT(*) FROM activities WHERE state='open'"))
    print("  状态=ended     : %s" % one("SELECT COUNT(*) FROM activities WHERE state='ended'"))
    print("  近 24h 新发现  : %s"
          % one("SELECT COUNT(*) FROM activities WHERE first_seen >= datetime('now','-1 day','+8 hours')"))
    print("  采集次数       : %s" % one("SELECT COUNT(*) FROM fetch_log"))
    print("  采集成功率     : %s"
          % one("SELECT printf('%.1f%%', 100.0*SUM(ok)/COUNT(*)) FROM fetch_log"))
    print("  累计采集字节   : %.1f MB"
          % ((one("SELECT SUM(bytes) FROM fetch_log") or 0) / 1048576.0))
    print("  最近一次       : %s"
          % one("SELECT at || '  ok=' || ok FROM fetch_log ORDER BY id DESC LIMIT 1"))
    print("\n=== 当前 open 活动 ===")
    rows = c.execute(
        """SELECT title, activity_type_label, credit_total, start_at, dept_label
           FROM activities WHERE state='open' ORDER BY start_at LIMIT 15""").fetchall()
    for r in rows:
        print("  %-28s %-6s %s学分  %s  %s"
              % ((r["title"] or "")[:28], r["activity_type_label"] or "-",
                 r["credit_total"] if r["credit_total"] is not None else "-",
                 (r["start_at"] or "-")[:16], (r["dept_label"] or "")[:14]))
    if not rows:
        print("  （空）")
    print()


def acquire_lock():
    try:
        import fcntl
    except ImportError:
        return None
    os.makedirs(DATA, exist_ok=True)
    fh = open(LOCK, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("已有采集器实例在运行，本次退出。")
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="只采集一次")
    ap.add_argument("--stats", action="store_true", help="只打印统计")
    ap.add_argument("--interval", type=int, default=INTERVAL)
    ap.add_argument("--jitter", type=int, default=JITTER)
    args = ap.parse_args()

    c = connect()

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

    # 守护模式
    _lock = acquire_lock()
    stopping = {"v": False}

    def _stop(signum, frame):
        stopping["v"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        print("会话到期：%s" % (client.session_expiry() or "未知"), flush=True)
    except Exception:
        pass
    print("开始采集，间隔 %ds + 0~%ds 抖动" % (args.interval, args.jitter), flush=True)

    fail = 0
    while not stopping["v"]:
        ok, err = collect_once(c, client)
        if ok:
            fail = 0
            delay = args.interval + random.randint(0, args.jitter)
        else:
            fail += 1
            if err and err.startswith("SESSION_EXPIRED"):
                print("!! 会话失效，需更新 cookie，30 分钟后重试", flush=True)
                delay = 1800
            else:
                delay = min(args.interval * min(fail, 6), 3600)
                print("   连续失败 %d 次，%ds 后重试" % (fail, delay), flush=True)
        # 分段睡眠，保证 SIGTERM 能及时响应
        deadline = time.time() + delay
        while time.time() < deadline and not stopping["v"]:
            time.sleep(min(5, deadline - time.time()))

    c.close()
    print("已停止。", flush=True)


if __name__ == "__main__":
    main()
