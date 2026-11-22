#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2ke-hub 管理后台
================
读取 /opt/2ke-hub/data/2ke.db，提供：
  · 概览：使用人数、今日新增活动、发送量、成功率
  · 订阅者：增删改、启停
  · 投递记录：状态筛选、失败重试
  · 活动：按级别/学院/学分/关键词筛选
  · 运维：手动采集、采集日志、Cookie 到期、库状态

只依赖 streamlit + pandas + 标准库。
"""
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

DB = "/opt/2ke-hub/data/2ke.db"
COLLECTOR = "/opt/2ke-hub/collector.py"
PY = "/usr/bin/python3"
CST = timezone(timedelta(hours=8))

st.set_page_config(page_title="2ke 通知管理后台", page_icon="📣", layout="wide")

# ---------------------------------------------------------------- 数据访问
def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def df(sql, params=()):
    con = connect()
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def run(sql, params=()):
    con = connect()
    try:
        with con:
            cur = con.execute(sql, params)
        return cur.rowcount
    finally:
        con.close()


def scalar(sql, params=(), default=0):
    d = df(sql, params)
    if d.empty:
        return default
    v = d.iloc[0, 0]
    return default if pd.isna(v) else v


def now_str():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- 侧边栏
st.sidebar.title("📣 2ke 通知后台")
st.sidebar.caption("集美大学第二课堂 · 采集与投递管理")

PAGES = ["概览", "订阅者", "投递记录", "活动库", "运维"]
page = st.sidebar.radio("导航", PAGES, label_visibility="collapsed")

st.sidebar.divider()
_alive = scalar("SELECT COUNT(*) FROM fetch_log WHERE ok=1 AND at >= ?",
                ((datetime.now(CST) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"),))
st.sidebar.metric("近 1 小时采集成功", int(_alive))
st.sidebar.caption("数据源：2ke.jmu.edu.cn\n采集间隔 480s")

# ---------------------------------------------------------------- 概览
if page == "概览":
    st.title("概览")

    subs_total = int(scalar("SELECT COUNT(*) FROM subscribers"))
    subs_active = int(scalar("SELECT COUNT(*) FROM subscribers WHERE active=1"))
    today = datetime.now(CST).strftime("%Y-%m-%d")
    new_today = int(scalar("SELECT COUNT(*) FROM activities WHERE substr(first_seen,1,10)=?", (today,)))
    sent_today = int(scalar(
        "SELECT COUNT(*) FROM deliveries WHERE status='sent' AND substr(sent_at,1,10)=?", (today,)))
    fail_today = int(scalar(
        "SELECT COUNT(*) FROM deliveries WHERE status='failed' AND substr(created_at,1,10)=?", (today,)))
    total_sent = int(scalar("SELECT COUNT(*) FROM deliveries WHERE status='sent'"))
    rate = scalar(
        "SELECT printf('%.1f%%', 100.0*SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END)/COUNT(*)) FROM deliveries")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("订阅人数", subs_total, f"活跃 {subs_active}")
    c2.metric("今日新活动", new_today)
    c3.metric("今日发送", sent_today, f"失败 {fail_today}" if fail_today else None)
    c4.metric("累计发送", total_sent)
    c5.metric("投递成功率", rate if not pd.isna(rate) else "—")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("近 14 天新发现活动")
        d = df("""SELECT substr(first_seen,1,10) AS 日期, COUNT(*) AS 数量
                  FROM activities
                  WHERE first_seen >= datetime('now','-14 day','+8 hours')
                  GROUP BY 1 ORDER BY 1""")
        if d.empty:
            st.info("暂无数据。等采集器多跑几轮，或用「运维 → 立即采集」手动触发。")
        else:
            st.bar_chart(d.set_index("日期"))

    with right:
        st.subheader("近 14 天采集情况")
        d = df("""SELECT substr(at,1,10) AS 日期,
                         SUM(ok) AS 成功, COUNT(*)-SUM(ok) AS 失败
                  FROM fetch_log
                  WHERE at >= datetime('now','-14 day','+8 hours')
                  GROUP BY 1 ORDER BY 1""")
        if d.empty:
            st.info("暂无采集记录。")
        else:
            st.line_chart(d.set_index("日期"))

    st.subheader("当前开放中的活动（按开始时间）")
    d = df("""SELECT title AS 活动, activity_type_label AS 级别, credit_total AS 学分,
                     start_at AS 开始, dept_label AS 主办, quota AS 名额
              FROM activities WHERE state='open' ORDER BY start_at LIMIT 30""")
    st.dataframe(d, use_container_width=True, hide_index=True, height=320)

    if fail_today:
        st.subheader("今日失败投递")
        st.dataframe(df("""SELECT id, activity_id, subscriber_id, channel, attempt, last_error, created_at
                           FROM deliveries WHERE status='failed'
                             AND substr(created_at,1,10)=? ORDER BY id DESC LIMIT 20""", (today,)),
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- 订阅者
elif page == "订阅者":
    st.title("订阅者管理")
    st.caption("channel：wxpusher / wecom / email / rss。external_id：WxPusher UID 或群 webhook 标识。")

    d = df("""SELECT id AS ID, channel AS 通道, external_id AS 外部ID,
                     label AS 备注, active AS 启用, created_at AS 创建时间
              FROM subscribers ORDER BY id""")
    if d.empty:
        st.info("还没有订阅者。下面添加第一个。")
    else:
        edited = st.data_editor(d, use_container_width=True, hide_index=True, num_rows="dynamic",
                                column_config={
                                    "启用": st.column_config.CheckboxColumn(default=True),
                                })
        if st.button("💾 保存修改", type="primary"):
            changed = 0
            for _, r in edited.iterrows():
                if pd.isna(r["ID"]):
                    run("""INSERT INTO subscribers (channel, external_id, label, active, created_at)
                           VALUES (?,?,?,?,?)""",
                        (r["通道"], r["外部ID"], r["备注"], 1 if r["启用"] else 0, now_str()))
                    changed += 1
                else:
                    run("UPDATE subscribers SET channel=?, external_id=?, label=?, active=? WHERE id=?",
                        (r["通道"], r["外部ID"], r["备注"], 1 if r["启用"] else 0, int(r["ID"])))
                    changed += 1
            st.success("已保存 %d 条" % changed)
            st.rerun()

    st.divider()
    st.subheader("新增订阅者")
    with st.form("add_sub", clear_on_submit=True):
        a, b, c, dd = st.columns([1, 2, 2, 1])
        ch = a.selectbox("通道", ["wxpusher", "wecom", "email", "rss"])
        ext = b.text_input("外部 ID", placeholder="UID_xxx / 群 webhook 标识")
        lab = c.text_input("备注", placeholder="例如：机械3班 张三")
        ok = dd.checkbox("启用", value=True)
        if st.form_submit_button("添加", type="primary"):
            if not ext.strip():
                st.error("外部 ID 不能为空")
            else:
                try:
                    run("""INSERT INTO subscribers (channel, external_id, label, active, created_at)
                           VALUES (?,?,?,?,?)""", (ch, ext.strip(), lab.strip(), 1 if ok else 0, now_str()))
                    st.success("已添加")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("该通道下这个外部 ID 已存在")

    st.divider()
    st.subheader("订阅规则")
    st.caption("一个订阅者可以有多条规则；没有规则的按「全部接收」处理。")
    r = df("""SELECT r.id AS ID, s.label AS 订阅者, s.channel AS 通道,
                     r.keywords AS 关键词, r.activity_types AS 级别, r.depts AS 学院,
                     r.credit_min AS 学分下限, r.quiet_hours AS 静默时段
              FROM rules r JOIN subscribers s ON s.id=r.subscriber_id ORDER BY r.id""")
    if r.empty:
        st.info("暂无规则（全部接收）。通知层接入后再启用规则编辑。")
    else:
        st.dataframe(r, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- 投递记录
elif page == "投递记录":
    st.title("投递记录")

    st_filter = st.selectbox("状态", ["全部", "pending", "sent", "failed"], index=0)
    where = "" if st_filter == "全部" else " WHERE d.status=?"
    params = () if st_filter == "全部" else (st_filter,)

    c1, c2, c3 = st.columns(3)
    c1.metric("待发送", int(scalar("SELECT COUNT(*) FROM deliveries WHERE status='pending'")))
    c2.metric("已发送", int(scalar("SELECT COUNT(*) FROM deliveries WHERE status='sent'")))
    c3.metric("失败", int(scalar("SELECT COUNT(*) FROM deliveries WHERE status='failed'")))

    d = df("""SELECT d.id AS ID, d.activity_id AS 活动ID, a.title AS 活动,
                     s.label AS 订阅者, d.channel AS 通道, d.status AS 状态,
                     d.attempt AS 尝试, COALESCE(d.last_error,'') AS 错误,
                     replace(substr(d.created_at,1,19),'T',' ') AS 创建, replace(substr(COALESCE(d.sent_at,''),1,19),'T',' ') AS 发送时间
              FROM deliveries d
              LEFT JOIN activities a ON a.id = d.activity_id
              LEFT JOIN subscribers s ON s.id = d.subscriber_id
              """ + where + " ORDER BY d.id DESC LIMIT 500", params)
    if d.empty:
        st.info("还没有投递记录。通知层接入后这里会有数据。")
    else:
        st.dataframe(d, use_container_width=True, hide_index=True, height=min(460, 40 + 35*min(100, int(scalar("SELECT COUNT(*) FROM deliveries")))))

    st.divider()
    st.subheader("批量操作")
    a, b, c = st.columns(3)
    if a.button("🔁 重试全部失败"):
        n = run("UPDATE deliveries SET status='pending', attempt=0 WHERE status='failed'")
        st.success("已重置 %d 条为待发送" % n)
    if b.button("🧹 清理 90 天前已发送"):
        n = run("DELETE FROM deliveries WHERE status='sent' AND sent_at < datetime('now','-90 day')")
        st.success("已清理 %d 条" % n)
    if c.button("♻️ 刷新"):
        st.rerun()

# ---------------------------------------------------------------- 活动库
elif page == "活动库":
    st.title("活动库")
    st.caption("数据来自 2ke.jmu.edu.cn 的 RSC 接口，每 480 秒同步一次。")

    f1, f2, f3, f4 = st.columns([1, 1, 1, 2])
    state = f1.selectbox("状态", ["全部", "open", "ended"])
    level = f2.selectbox("级别", ["全部"] + [x for x in df(
        "SELECT DISTINCT activity_type_label AS v FROM activities WHERE activity_type_label IS NOT NULL ORDER BY 1")["v"].tolist()])
    dept = f3.selectbox("学院", ["全部"] + [x for x in df(
        "SELECT DISTINCT dept_label AS v FROM activities WHERE dept_label IS NOT NULL ORDER BY 1")["v"].tolist()])
    kw = f4.text_input("标题关键词", placeholder="例如：志愿 / 讲座 / 音乐")

    cond, ps = [], []
    if state != "全部":
        cond.append("state=?")
        ps.append(state)
    if level != "全部":
        cond.append("activity_type_label=?")
        ps.append(level)
    if dept != "全部":
        cond.append("dept_label=?")
        ps.append(dept)
    if kw.strip():
        cond.append("title LIKE ?")
        ps.append("%" + kw.strip() + "%")
    w = (" WHERE " + " AND ".join(cond)) if cond else ""

    st.markdown("**匹配 %d 条**" % int(scalar("SELECT COUNT(*) FROM activities" + w, tuple(ps))))

    d = df("""SELECT title AS 活动, activity_type_label AS 级别, credit_total AS 学分,
                     start_at AS 开始, end_at AS 结束, address AS 地点, quota AS 名额,
                     dept_label AS 主办, signup_type AS 报名方式, state AS 状态,
                     replace(substr(first_seen,1,19),'T',' ') AS 首次发现, id AS 活动ID
              FROM activities""" + w + " ORDER BY start_at DESC LIMIT 500", tuple(ps))
    st.dataframe(d, use_container_width=True, hide_index=True, height=520)

    if not d.empty:
        st.download_button("⬇️ 导出当前结果 CSV",
                           d.to_csv(index=False).encode("utf-8-sig"),
                           "2ke-activities.csv", "text/csv")

# ---------------------------------------------------------------- 运维
else:
    st.title("运维")

    st.subheader("采集器")
    c1, c2, c3 = st.columns(3)
    c1.metric("采集次数", int(scalar("SELECT COUNT(*) FROM fetch_log")))
    c2.metric("成功率", scalar(
        "SELECT printf('%.1f%%', 100.0*SUM(ok)/COUNT(*)) FROM fetch_log") or "—")
    c3.metric("累计流量", "%.1f MB" % ((scalar("SELECT SUM(bytes) FROM fetch_log") or 0) / 1048576.0))

    a, b = st.columns([1, 3])
    if a.button("▶️ 立即采集一次", type="primary"):
        with st.spinner("正在向 2ke 取数…"):
            try:
                p = subprocess.run([PY, COLLECTOR, "--once"], capture_output=True,
                                   text=True, timeout=120)
                st.code((p.stdout or "") + (p.stderr or ""), language="text")
            except Exception as e:
                st.error("采集失败：%r" % (e,))
        st.rerun()

    st.subheader("Cookie 状态")
    ck = "/opt/jmu-2ke/2ke_cookie.json"
    if os.path.exists(ck):
        st_txt = datetime.fromtimestamp(os.path.getmtime(ck), CST).strftime("%Y-%m-%d %H:%M")
        st.info("Cookie 文件：`%s`\n\n最后更新：%s\n\n续期命令：`/opt/jmu-2ke/set-cookie.sh '<token>'`" % (ck, st_txt))
    else:
        st.error("找不到 Cookie 文件：%s" % ck)

    st.subheader("采集日志（最近 30 条）")
    d = df("""SELECT replace(substr(at,1,19),'T',' ') AS 时间, ok AS 成功, http_ms AS 耗时ms, bytes AS 字节,
                     open_count AS 开放, ended_count AS 已结束, new_count AS 新增, COALESCE(error,'') AS 错误
              FROM fetch_log ORDER BY id DESC LIMIT 30""")
    st.dataframe(d, use_container_width=True, hide_index=True, height=min(380, 40 + 35*min(30, int(scalar("SELECT COUNT(*) FROM fetch_log")))))

    st.subheader("数据库")
    if os.path.exists(DB):
        st.write("库文件：`%s`　大小：%.2f MB" % (DB, os.path.getsize(DB) / 1048576))
    for t in ["activities", "fetch_log", "subscribers", "rules", "deliveries"]:
        st.caption("%s：%d 行" % (t, int(scalar("SELECT COUNT(*) FROM " + t))))

    st.subheader("服务状态")
    try:
        for svc in ["2ke-hub-collector", "jmu-2ke-watch"]:
            r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=10)
            st.write("%s：**%s**" % (svc, (r.stdout or "").strip()))
    except Exception as e:
        st.warning("查不到服务状态：%r" % (e,))
