#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2ke-hub 推送器（Dispatcher）
============================
把 t_activity 里新出现的活动，按 t_subscriber 的规则推给订阅者（企业微信），
并把每次投递结果写进 t_delivery。

幂等保证：
  t_delivery 上有 UNIQUE(activity_id, subscriber_id)
  → INSERT ... ON DUPLICATE KEY 只有在"首次"才真正插入
  → 只有插入成功（affected_rows==1）才发消息，绝不会重复推送

规则字段（t_subscriber）：
  keywords    逗号分隔，活动标题包含任一即命中；空=不限
  学分过滤、静默时段均已下线：不做学分和时段判断，所有活动都推
  only_school '1' 只看校级；'0'/空=不限

用法：
  python3 dispatcher.py --once      跑一轮
  python3 dispatcher.py             常驻（systemd 用）
  python3 dispatcher.py --dry-run   只读试跑：不发送、不写库、不写状态、不推进水位
  python3 dispatcher.py --stats     看统计

水位游标（2026-10-23 修复 A1）：
  旧版只用 first_seen 单值水位 + LIMIT 200，而采集器"同一轮写入的所有新活动
  共享同一个 first_seen 秒值"；单轮新增 >=200 条时被 LIMIT 切掉的余数会落在
  水位之下、永久漏推。现在水位是 (last_dispatch, last_activity_id) 元组游标。

水位推进（2026-10-23 修复 P0-7 / A2）：
  · dry-run 一律不写状态、不动水位、不碰 t_delivery；
  · 空转（本轮 0 条新活动）不再把水位设成 now()（旧行为会与采集器写
    first_seen 抢同一秒，把那一批永久越过去）；
  · 只在「本批已处理完」时推进到 (acts[-1].first_seen, acts[-1].activity_id)。
"""
import argparse
import json
import os
import random
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "wecom.json")
STATE = os.path.join(HERE, "dispatch_state.json")

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

INTERVAL = 120          # 每 2 分钟扫一次（活动分发）
JITTER = 20
SYNC_INTERVAL = 60      # 通讯录同步单独跑，60 秒一次（成员增删能更快反映）
CHECK_TICK = 10         # 主循环醒来的最小粒度（秒）
API = "https://qyapi.weixin.qq.com/cgi-bin"

UNKNOWN = -1            # wecom_send 的"结果未知"哨兵：绝不可自动重试
IDLE_REWIND_ROUNDS = 24     # 连续空转多少轮后允许"水位兜底回退"（24×300s ≈ 2 小时）
REWIND_COOLDOWN = 6 * 3600  # 水位兜底回退的最小间隔，防止反复重扫
CONTACT_LOW_ROUNDS = 3      # 通讯录人数骤降连续多少轮才接受新基线（防误停用）

# dry-run 期间禁止一切落盘/落库。save_state() 会检查这个开关。
DRY = {"on": False}


# ---------------------------------------------------------------- 工具
def now():
    return datetime.now(CST)


def log(msg):
    print("[%s] %s" % (now().strftime("%H:%M:%S"), msg), flush=True)


def load_conf():
    with open(CONF, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    st = None
    if os.path.exists(STATE):
        try:
            with open(STATE, encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            st = None
    if not isinstance(st, dict):
        # 首次运行：水位设为"现在"，避免把历史活动全部推一遍
        st = {"last_dispatch": now().strftime("%Y-%m-%d %H:%M:%S"), "token": None,
              "token_exp": 0}
    # 兼容旧 state 文件：没有 last_activity_id 时按空串处理，
    # 等价于"只用时间水位"的老语义（首次升级不会漏也不会重扫）。
    st.setdefault("last_activity_id", "")
    st.setdefault("idle_rounds", 0)
    return st


def save_state(st):
    """写状态文件。里面含 access_token，必须 600，且要用原子替换。

    dry-run 期间一律不写：否则一次"只读"验证就会把水位推到本批末尾，
    真实批次被永久越过、学生永久收不到（审计 B · P0-1）。
    """
    if DRY["on"]:
        log("  [dry] 不写状态文件（水位保持 %s / %s）"
            % (st.get("last_dispatch"), st.get("last_activity_id") or "-"))
        return
    tmp = STATE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, STATE)


def conn():
    c = pymysql.connect(**DB)
    c.autocommit(False)
    return c


# ---------------------------------------------------------------- 企业微信
def get_token(st, conf, force=False):
    if not force and st.get("token") and st.get("token_exp", 0) > time.time() + 300:
        return st["token"]
    url = "%s/gettoken?corpid=%s&corpsecret=%s" % (
        API, urllib.parse.quote(conf["corp_id"]), urllib.parse.quote(conf["secret"]))
    with urllib.request.urlopen(url, timeout=20) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("errcode") != 0:
        raise RuntimeError("gettoken 失败: %s" % d)
    st["token"] = d["access_token"]
    st["token_exp"] = time.time() + int(d.get("expires_in", 7200))
    save_state(st)
    return st["token"]


def wecom_send(token, agent_id, touser, content, markdown=False):
    """返回 (ok, errcode, errmsg)

    三态语义（2026-10-23 修复 A5）：
      · ok=True                      → 企业微信明确受理（errcode=0），可以写 sent
      · ok=False, errcode=UNKNOWN(-1) → 超时/连接重置/HTTP 5xx/响应不可解析，
                                       **消息可能已经送达**。调用方必须写
                                       send_status='unknown' 并且**不自动重发**，
                                       否则学生会收到两条同样的消息。
      · ok=False, errcode=其它整数    → 企业微信明确拒收（errcode!=0），可以重试

    注意：markdown 消息在【微信插件】（普通微信里那个对话框）中不支持，
    会显示成「暂不支持此消息类型，请在企业微信中查看」。
    只有 text 类型能同时在企业微信 App 和普通微信里正常显示，
    所以默认用 text，markdown 仅在企业微信 App 场景下才开。
    """
    payload = {
        "touser": touser,
        "msgtype": "markdown" if markdown else "text",
        "agentid": agent_id,
        "safe": 0,
    }
    if markdown:
        payload["markdown"] = {"content": content}
    else:
        payload["text"] = {"content": content}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "%s/message/send?access_token=%s" % (API, token),
        data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        # 网关 5xx / 限流 429：企业微信是否已受理未知
        return False, UNKNOWN, "HTTP %s（结果未知，不自动重试）" % e.code
    except Exception as e:
        # 超时 / 连接被重置 / DNS：请求可能已经到达企业微信
        return False, UNKNOWN, "%s: %s（结果未知，不自动重试）" % (type(e).__name__, e)
    try:
        d = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return False, UNKNOWN, "响应不可解析（结果未知，不自动重试）: %r" % (e,)
    ok = (d.get("errcode") == 0)
    return ok, d.get("errcode"), d.get("errmsg") or ""


def api_get(path, token, **params):
    q = {"access_token": token}
    q.update({k: v for k, v in params.items() if v is not None})
    url = "%s/%s?%s" % (API, path, urllib.parse.urlencode(q))
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def sync_contacts(c, token, verbose=True, st=None):
    """从企业微信通讯录同步成员到 t_subscriber。

    - 名单以通讯录为准（新增/离职自动跟随）
    - 只更新 nickname / real_name / status，**不覆盖**用户自己设的
      keywords / min_credit / only_school / quiet_hours
    - 通讯录里没有的本地订阅者会被置为停用（status='1'），不删除，
      保留历史投递记录
    - 通讯录里**有**的人一律写回 status='0'（2026-10-23 修复 A3）：
      旧代码只写昵称不写 status，一旦某人被停用（含名单残缺导致的批量误停用），
      没有任何代码路径能把他改回启用 —— 学生永久失联，而管理后台显示
      「已停用」，看起来像本人退订。
      注意：这里有意识地用 status='0' 覆盖，语义是「t_subscriber.status 完全由
      通讯录同步托管」；如需人工暂停某人，正确做法是移出企业微信应用可见范围
      （或后续新增 manual_pause 列），不要靠改 status。
    """
    deps = api_get("department/list", token)
    if deps.get("errcode") != 0:
        log("  !! 拉部门失败 %s" % deps.get("errmsg"))
        return 0

    staff = {}          # userid -> 明细
    failed_deps = 0     # 拉取失败的部门数
    for d in deps.get("department") or []:
        r = api_get("user/list", token, department_id=d["id"], fetch_child=1)
        if r.get("errcode") != 0:
            failed_deps += 1
            continue
        for u in r.get("userlist") or []:
            if u.get("userid"):
                staff[u["userid"]] = u

    if not staff:
        log("  !! 通讯录为空，跳过同步")
        return 0

    added = updated = 0
    with c.cursor(pymysql.cursors.DictCursor) as cur:
        for userid, u in staff.items():
            name = (u.get("name") or userid)[:100]
            # 只要出现在通讯录里，就视为可用 —— 不再看 status。
            # 原因：user/simplelist 平时不返回 status，但新成员「未激活」时
            # 偶尔会带上 status=4，而 4 只表示没登录过企业微信 App，
            # 完全不影响他用微信插件（普通微信）收消息。
            # 之前依 status 判断，导致新加入的人一进来就被判成停用。
            wx_ok = True
            cur.execute("""SELECT subscriber_id FROM t_subscriber
                           WHERE channel='wecom' AND external_id=%s""", (userid,))
            if cur.fetchone():
                # 修复 A3：status 也归通讯录托管（写回 '0'），否则停用者永不复活。
                cur.execute("""UPDATE t_subscriber
                               SET nickname=%s, real_name=%s, status='0',
                                   update_time=NOW()
                               WHERE channel='wecom' AND external_id=%s""",
                            (name, name, userid))
                updated += 1
            else:
                cur.execute("""INSERT INTO t_subscriber
                    (channel, external_id, nickname, real_name, status,
                     create_by, create_time, remark)
                    VALUES ('wecom', %s, %s, %s, %s, 'sync', NOW(), '通讯录自动同步')""",
                    (userid, name, name, '0' if wx_ok else '1'))
                added += 1

        # 通讯录里已经没有的，置停用（不删，保留投递历史）。
        # 但如果本轮有部门拉取失败，staff 是不完整的 —— 此时执行「不在名单就停用」
        # 会把那些部门的人全部误停用。宁可不做，等下一轮名单完整时再说。
        #
        # 修复 A4（加固）：errcode=0 但 userlist 残缺（限流降级、应用可见范围被
        # 临时缩小、管理员正在调部门）时 failed_deps 是 0，旧代码会照样批量误停用。
        # 这里再补一道人数下限：本轮人数比上轮掉超过 40% 视为名单异常，跳过停用判定；
        # 连续 CONTACT_LOW_ROUNDS 轮都异常才接受新基线（防止真的有人陆续退企业）。
        ids = list(staff.keys())
        prev = 0
        if st is not None:
            try:
                prev = int(st.get("contact_count") or 0)
            except (TypeError, ValueError):
                prev = 0
        low_rounds = 0
        if st is not None:
            try:
                low_rounds = int(st.get("contact_low_rounds") or 0)
            except (TypeError, ValueError):
                low_rounds = 0
        low = bool(prev and len(staff) < prev * 0.6 and low_rounds < CONTACT_LOW_ROUNDS)

        if failed_deps:
            gone = 0
            if verbose:
                log("  !! %d 个部门拉取失败，本轮跳过「停用」判定（防止误停用）" % failed_deps)
        elif low:
            gone = 0
            if verbose:
                log("  !! 通讯录人数从 %d 骤降到 %d（<60%%），本轮跳过「停用」判定（防止误停用）"
                    % (prev, len(staff)))
        elif ids:
            ph = ",".join(["%s"] * len(ids))
            cur.execute("""UPDATE t_subscriber SET status='1', update_time=NOW()
                           WHERE channel='wecom' AND external_id NOT IN (%s)
                             AND status='0'""" % ph, tuple(ids))
            gone = cur.rowcount
        else:
            gone = 0

        if st is not None and not failed_deps:
            if low:
                st["contact_low_rounds"] = low_rounds + 1
            else:
                st["contact_low_rounds"] = 0
                st["contact_count"] = len(staff)
    c.commit()
    if verbose:
        log("通讯录同步：新增 %d，更新 %d，停用 %d（通讯录共 %d 人）"
            % (added, updated, gone, len(staff)))
    return added


# ---------------------------------------------------------------- 规则
def in_quiet_hours(spec, t=None):
    """'23:00-07:00' 支持跨零点"""
    if not spec or "-" not in spec:
        return False
    t = t or now()
    try:
        a, b = [x.strip() for x in spec.split("-", 1)]
        ha, ma = [int(x) for x in a.split(":")]
        hb, mb = [int(x) for x in b.split(":")]
    except Exception:
        return False
    cur = t.hour * 60 + t.minute
    start, end = ha * 60 + ma, hb * 60 + mb
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end      # 跨零点


def max_credit(act):
    """活动最高可获学分。

    credit_total 是 jmu_2ke_api 里对各档 credit 求和得到的（例如档位 2/3/1/4
    求和 = 10），没有实际含义；真正能拿到的是某一档，所以取 credit_detail 的最大值。
    """
    detail = act.get("credit_detail")
    if detail:
        try:
            arr = json.loads(detail) if isinstance(detail, str) else detail
            vals = []
            for x in arr or []:
                try:
                    if x.get("credit") is not None:
                        vals.append(float(x["credit"]))
                except (TypeError, ValueError):
                    pass
            if vals:
                return max(vals)
        except Exception:
            pass
    t = act.get("credit_total")
    try:
        return float(t) if t is not None else None
    except (TypeError, ValueError):
        return None


def match(sub, act):
    """返回 (命中?, 原因)"""
    if sub["status"] != "0":
        return False, "订阅已停用"
    kw = (sub.get("keywords") or "").strip()
    if kw:
        title = act.get("title") or ""
        words = [w.strip() for w in kw.replace("，", ",").split(",") if w.strip()]
        if words and not any(w in title for w in words):
            return False, "关键词不匹配"


    if (sub.get("only_school") or "0") == "1":
        if act.get("activity_type") != "school":
            return False, "仅校级"
    # 学分门槛：一律按档位最高值判断
    mc = sub.get("min_credit")
    if mc is not None:
        try:
            mc = float(mc)
        except (TypeError, ValueError):
            mc = 0.0
        if mc > 0:
            top = max_credit(act)
            if top is None or top < mc:
                return False, "学分低于门槛 %g" % mc
    return True, "ok"


# ---------------------------------------------------------------- 消息体
def short_credit_type(name):
    """把 2ke 的长学分类别名缩写。
    「参加思想政治、形势政策、理想信念主题教育报告会、讲座、交流会等」→「思政讲座」
    """
    if not name:
        return None
    mapping = [
        ("志愿", "志愿公益"),
        ("文化、艺术", "文化艺术"),
        ("人文素养", "人文心理"),
        ("心理健康", "人文心理"),
        ("思想政治", "思政讲座"),
        ("形势政策", "思政讲座"),
        ("运动会", "体育"),
        ("体育", "体育"),
        ("创新创业", "创新创业"),
        ("文艺排练", "文艺演出"),
        ("美术展览", "文艺演出"),
    ]
    for kw, short in mapping:
        if kw in name:
            return short
    return name if len(name) <= 10 else name[:10] + "…"


def parse_credit(act):
    """解析学分。
    2ke 的 credit_total 是【最高可获学分】，实际按岗位分档：
      credit_detail = [{"credit":"2","number":"10"}, {"credit":"1","number":"70"}]
      → 干 70 人那份给 1 分，10 人那份给 2 分
    所以要显示区间，不能直接报 credit_total。
    返回 (显示文本, 是否分档)
    """
    detail = act.get("credit_detail")
    if detail:
        try:
            arr = json.loads(detail) if isinstance(detail, str) else detail
            vals = []
            for x in arr or []:
                try:
                    vals.append(float(x.get("credit")))
                except (TypeError, ValueError):
                    pass
            if vals:
                lo, hi = min(vals), max(vals)
                if lo != hi:
                    return "%g~%g 学分（按排名分档）" % (lo, hi), True
                return "最高 %g 学分" % hi, False
        except Exception:
            pass
    total = act.get("credit_total")
    if total is not None:
        try:
            return "最高 %g 学分" % float(total), False
        except (TypeError, ValueError):
            pass
    return "学分见平台", False


def _fmt_dt(d, with_time=True, with_week=False):
    if not d:
        return ""
    out = d.strftime("%m-%d")
    if with_week:
        out += " 周" + "一二三四五六日"[d.weekday()]
    if with_time:
        out += " " + d.strftime("%H:%M")
    return out


def _signup_hint(end):
    """报名截止的紧迫度提示"""
    if not end:
        return ""
    now = datetime.now(CST).replace(tzinfo=None)
    hours = (end - now).total_seconds() / 3600.0
    if hours < 0:
        return "❌ 已截止"
    if hours < 24:
        return "⚠️ 今天截止"
    days = int(hours / 24)
    if days <= 2:
        return "⚠️ 只剩 %d 天" % days
    return "还有 %d 天" % days


def render(act):
    """生成推送给学生的纯文本正文。

    格式对齐「第二课堂：有新活动!」模板：
        第二课堂：有新活动!
        【活动标题】
        学分 / 时间 / 报名 / 地点 / 名额+级别 / 主办 / 类别 / 活动ID
        👉 打开链接

    保留两处数据防御：
      · credit_detail 有分档时显示区间，不直接报 credit_total（那个是最高值）
      · 报名时间晚于活动结束时给出异常提示，不原样展示
    """
    title = act.get("title") or "（无标题）"
    lv = "校级活动" if act.get("activity_type") == "school" else "院级活动"
    credit, tiered = parse_credit(act)
    ctype = act.get("credit_type_name") or ""

    lines = ["第二课堂：有新活动!", "", "【%s】" % title, ""]

    # 学分
    lines.append("学分：%s" % credit)

    # 活动时间（完整年月日）
    s, e = act.get("start_at"), act.get("end_at")
    if s:
        if e:
            lines.append("时间：%s ~ %s" % (s.strftime("%Y-%m-%d %H:%M"), e.strftime("%Y-%m-%d %H:%M")))
        else:
            lines.append("时间：%s" % s.strftime("%Y-%m-%d %H:%M"))

    # 报名窗口（带异常防御和紧迫提示）
    ss, se = act.get("signin_start"), act.get("signin_end")
    if ss or se:
        abnormal = bool(e and ss and ss > e)
        if abnormal:
            lines.append("报名：平台数据异常（晚于活动结束），以 2ke 为准")
        else:
            a = ss.strftime("%Y-%m-%d %H:%M") if ss else "未定"
            b = se.strftime("%Y-%m-%d %H:%M") if se else "未定"
            hint = _signup_hint(se)
            lines.append("报名：%s ~ %s%s" % (a, b, ("（%s）" % hint.strip("⚠️❌ ")) if hint else ""))

    # 地点
    if act.get("address"):
        lines.append("地点：%s" % act["address"])

    # 名额
    q = act.get("quota")
    quota_txt = ("%d 人" % int(q)) if q else "不限"
    lines.append("名额：%s" % quota_txt)

    # 级别（校级 / 院级，学生判断能不能报的关键信息，单独一行）
    lines.append("级别：%s" % lv)

    # 主办
    if act.get("dept_label"):
        lines.append("主办：%s" % act["dept_label"])

    # 类别（短的原样，长的缩写）
    if ctype:
        short = ctype if len(ctype) <= 12 else short_credit_type(ctype)
        lines.append("类别：%s" % short)

    # 活动ID（便于人工排查）
    if act.get("activity_id"):
        lines.append("活动ID：%s" % act["activity_id"])

    lines.append("")
    lines.append("👉 打开：https://2ke.jmu.edu.cn/dashboard")

    text = "\n".join(lines)
    raw = text.encode("utf-8")
    if len(raw) > 2000:                       # 企业微信上限 2048
        text = raw[:1960].decode("utf-8", "ignore") + "\n…"
    return text


# ---------------------------------------------------------------- 巡检
ALERT_COOLDOWN = 3600       # 同类告警 1 小时内不重复
STALE_MINUTES = 40          # 采集器 40 分钟没更新数据就认为它死了


def health_check(c, token, conf, st, dry=False):
    """巡检采集器是否还在工作。

    判据：t_activity.last_seen 的最大值。采集器每轮都会刷新所有活动的
    last_seen，所以只要它在正常跑，这个值就不会落后超过一个采集间隔（8 分钟）。
    超过 STALE_MINUTES 没更新 = Cookie 失效 / 网络断 / 进程死了。

    告警发给 conf.admin_userid，ALERT_COOLDOWN 内不重复。
    """
    if not token:
        return
    admin = conf.get("admin_userid")
    if not admin:
        return

    # ② pending 死行检查（issue B-建议）：
    #    正常 pending 只存在几秒（插入 → 发送 → 更新），超过 30 分钟还挂着，
    #    说明进程崩在发送中途。消息可能已送达，所以只告警、不自动重发。
    try:
        with c.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""SELECT COUNT(*) AS n, MIN(create_time) AS oldest
                            FROM t_delivery
                            WHERE send_status='pending'
                              AND create_time < DATE_SUB(NOW(), INTERVAL 30 MINUTE)""")
            p = cur.fetchone() or {}
        n_pending = p.get("n") or 0
        if n_pending > 0 and time.time() - st.get("last_pending_alert_at", 0) >= ALERT_COOLDOWN:
            pmsg = ("【2ke 投递卡住】\n\n"
                    "有 %d 条投递停在 pending 超过 30 分钟（最早 %s）。\n"
                    "可能是发送途中进程退出。消息可能已经送达，先别急着重发。\n\n"
                    "查看：journalctl -u 2ke-dispatcher -n 50\n"
                    "处理：后台 → 第二课堂 → 通知投递记录"
                    % (n_pending, p.get("oldest")))
            if dry:
                log("  [dry] 会发告警：%d 条 pending 卡住" % n_pending)
            else:
                ok_p, code_p, err_p = wecom_send(token, conf["agent_id"], admin, pmsg)
                if ok_p:
                    log("  [告警] pending 卡住 %d 条已通知" % n_pending)
                    st["last_pending_alert_at"] = time.time()
                    save_state(st)
                else:
                    log("  !! pending 告警发送失败 errcode=%s %s" % (code_p, err_p))
    except Exception as e:
        log("  !! pending 检查失败：%r" % (e,))

    with c.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT MAX(last_seen) AS last, COUNT(*) AS n FROM t_activity")
        r = cur.fetchone()
    last = r.get("last")
    if not last:
        return

    now_naive = datetime.now(CST).replace(tzinfo=None)
    idle = (now_naive - last).total_seconds() / 60.0

    if idle <= STALE_MINUTES:
        if st.get("last_alert_at"):
            st.pop("last_alert_at", None)
            save_state(st)
        return

    if time.time() - st.get("last_alert_at", 0) < ALERT_COOLDOWN:
        return

    msg = ("【2ke 采集异常】\n\n"
           "已 %d 分钟没有采集到数据（阈值 %d 分钟）。\n"
           "最后成功：%s\n\n"
           "可能原因：\n"
           "1. 登录 Cookie 过期\n"
           "2. 2ke 站点改版或反爬\n"
           "3. 采集进程异常\n\n"
           "排查：journalctl -u 2ke-hub-mysql -n 30\n"
           "续期：后台 → 系统运维 → 第二课堂登录凭据 → 更新（粘贴整行 Cookie）"
           % (int(idle), STALE_MINUTES, last.strftime("%m-%d %H:%M")))

    if dry:
        log("  [dry] 会发告警：采集已停 %d 分钟" % int(idle))
        return

    ok, code, err = wecom_send(token, conf["agent_id"], admin, msg)
    if ok:
        log("  [告警] 采集异常已通知（停 %d 分钟）" % int(idle))
        st["last_alert_at"] = time.time()
        save_state(st)
    else:
        log("  !! 告警发送失败 errcode=%s %s" % (code, err))


def retry_failed(c, token, conf, max_attempt=3, hours=6, dry=False):
    """重投失败的消息：最多 max_attempt 次，只重试 hours 小时内的。

    注意（修复 A5）：这里**只捞 send_status='failed'**，也就是企业微信明确
    拒收（errcode!=0）的行。'unknown'（超时/连接异常/5xx，消息可能已经送达）
    不会被自动重试 —— 重试就等于让学生收两遍同样的消息。unknown 需要人工
    确认后在后台处理。
    """
    if not token:
        return 0

    with c.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("""SELECT d.delivery_id, d.activity_id, d.subscriber_name,
                              d.attempt,
                              a.activity_id, a.title, a.activity_type, a.credit_total,
                              a.credit_detail, a.credit_type_name,
                              a.start_at, a.end_at, a.signin_start, a.signin_end,
                              a.dept_label, a.address, a.quota,
                              s.external_id, s.status AS sub_status
                       FROM t_delivery d
                       JOIN t_activity a ON a.activity_id = d.activity_id
                       JOIN t_subscriber s ON s.subscriber_id = d.subscriber_id
                       WHERE d.send_status='failed'
                         AND d.attempt < %s
                         AND d.create_time > DATE_SUB(NOW(), INTERVAL %s HOUR)
                       ORDER BY d.delivery_id LIMIT 20""", (max_attempt, hours))
        rows = cur.fetchall()

    if not rows:
        return 0

    redone = 0
    for r in rows:
        if r.get("sub_status") != "0":
            continue
        content = render(r)
        if dry:
            log("  [dry] 会重试 #%s -> %s" % (r["delivery_id"], r["subscriber_name"]))
            continue
        ok, code, err = wecom_send(token, conf["agent_id"], r["external_id"], content)
        with c.cursor() as cur:
            if ok:
                cur.execute("""UPDATE t_delivery SET send_status='sent',
                               attempt=attempt+1, sent_time=NOW(), last_error=''
                               WHERE delivery_id=%s""", (r["delivery_id"],))
                redone += 1
                log("  [重试成功] #%s -> %s" % (r["delivery_id"], r["subscriber_name"]))
            elif code == UNKNOWN:
                # 结果未知：可能已经送达。写 unknown 退出重试队列，避免重复推送。
                cur.execute("""UPDATE t_delivery SET send_status='unknown',
                               attempt=attempt+1, last_error=%s
                               WHERE delivery_id=%s""",
                            (("重试结果未知 %s" % err)[:480], r["delivery_id"]))
                log("  [重试未知] #%s %s —— 已标 unknown，不再自动重试，请人工核对"
                    % (r["delivery_id"], err))
            else:
                cur.execute("""UPDATE t_delivery SET attempt=attempt+1, last_error=%s
                               WHERE delivery_id=%s""",
                            (("重试 errcode=%s %s" % (code, err))[:480], r["delivery_id"]))
                log("  [重试失败] #%s errcode=%s" % (r["delivery_id"], code))
        c.commit()
    return redone


# ---------------------------------------------------------------- 主流程
def _safe_rollback(c):
    """回滚一笔可能残留的事务；连接已经断了也不许把异常抛出去。"""
    try:
        c.rollback()
    except Exception:
        pass


def run_once(c, st, conf, dry=False, skip_sync=False):
    """一轮分发。dry=True 时整轮只读；skip_sync=True 时跳过通讯录同步
    （同步已由主循环按 SYNC_INTERVAL 独立触发，避免一轮里同步两次）。"""
    if dry:
        DRY["on"] = True
    try:
        return _run_once(c, st, conf, dry, skip_sync)
    finally:
        if dry:
            DRY["on"] = False


def _run_once(c, st, conf, dry=False, skip_sync=False):
    conf = conf or load_conf()

    # 结束上一轮可能残留的事务。
    # 这个连接是长期复用的，且 autocommit=False；MySQL 默认 REPEATABLE-READ，
    # 只要有一轮没 commit，后面所有 SELECT 都会读那个旧快照 ——
    # 表现为「采集器明明写入了新活动，Dispatcher 却查不到」，然后水位推进到 now()，
    # 把真实的新活动永久越过去。每轮开头先 rollback 拿到新快照。
    _safe_rollback(c)

    since = st.get("last_dispatch") or now().strftime("%Y-%m-%d %H:%M:%S")
    since_id = st.get("last_activity_id") or ""      # 兼容旧 state：缺失按空串
    catching_up = bool(st.get("rewind_round"))

    # ① 读水位之后的（活动）—— 元组游标 (first_seen, activity_id)
    with c.cursor(pymysql.cursors.DictCursor) as cur:
        # 注意：credit_detail / credit_type_name / signin_end 必须一起取出，
        # 否则 render() 会缺类别、报名截止显示"未定"、学分退化成 credit_total（各档之和）
        # first_seen + activity_id 必须一起取出：末尾用它们推水位。
        #
        # 修复 A1：旧查询是 `first_seen > %s`，而采集器"一轮采集里所有新活动共享
        # 同一个 first_seen 秒值"。单轮新增 >=200 条时，被 LIMIT 200 切掉的余数与
        # 已处理的尾部同秒，`first_seen > 该秒值` 恒为假 → 余数永久漏推。
        # 现在同秒内再用 activity_id 做第二级游标。
        cur.execute("""SELECT activity_id, title, activity_type, credit_total,
                              credit_detail, credit_type_name,
                              start_at, end_at, signin_start, signin_end,
                              dept_label, address, quota, first_seen
                       FROM t_activity
                       WHERE (first_seen > %s
                              OR (first_seen = %s AND activity_id > %s))
                         AND act_state = 'open'
                       ORDER BY first_seen, activity_id LIMIT 200""",
                    (since, since, since_id))
        acts = cur.fetchall()

    # ② 拿 token 并同步通讯录（每轮都同步，名单永远跟企业微信一致）
    token = None
    try:
        token = get_token(st, conf)
        if dry:
            # dry 是只读的：不做通讯录同步（sync_contacts 会 UPDATE/INSERT t_subscriber）
            log("  [dry] 跳过通讯录同步（不写 t_subscriber）")
        elif skip_sync:
            pass    # 主循环已按 SYNC_INTERVAL 单独同步过
        else:
            sync_contacts(c, token, st=st)
    except Exception as e:
        log("  !! 通讯录同步失败（退回本地名单）：%r" % (e,))

    # ③ 同步之后才读订阅者，否则拿到的是旧名单
    with c.cursor(pymysql.cursors.DictCursor) as cur:
        # create_time 用于"补扫轮"判断订阅者是否在活动发现之后才订阅
        cur.execute("""SELECT subscriber_id, channel, external_id, nickname,
                              keywords, min_credit, only_school, quiet_hours,
                              status, create_time
                       FROM t_subscriber WHERE status='0'""")
        subs = cur.fetchall()

    # 巡检 + 失败重投：与「有没有新活动」无关，每轮都要做
    if token:
        try:
            redone = retry_failed(c, token, conf, dry=dry)
            if redone:
                log("失败重投成功 %d 条" % redone)
        except Exception as e:
            log("!! 重投异常：%r" % (e,))
        try:
            health_check(c, token, conf, st, dry=dry)
        except Exception as e:
            log("!! 巡检异常：%r" % (e,))

    if not acts:
        log("新活动 0 条，活跃订阅者 %d 人（水位 %s / %s）—— 本轮无推送"
            % (len(subs), since, since_id or "-"))
        if dry:
            log("  [dry] 不改水位、不写状态")
            _safe_rollback(c)
            return 0
        # 修复 A2：空转**不推进水位**。旧代码把水位设成 now()，而采集器写
        # first_seen 也用 NOW()，两者同为秒级：若采集器在「本轮 SELECT 已执行完」
        # 与「save_state 落盘」之间提交（窗口 ≈ 一次通讯录同步的耗时），那一批活动
        # 的 first_seen 恰好等于新水位 → first_seen > since 为假 → 永久漏推。
        # 水位语义从此只由「已处理到的最后一条活动」推动。
        idle = int(st.get("idle_rounds") or 0) + 1
        st["idle_rounds"] = idle
        # 兜底：防止水位因历史原因（旧代码每轮推 now()）永久停在过高的位置。
        # 连续 IDLE_REWIND_ROUNDS 轮空转、且库里最早 open 活动比水位还早时，
        # 把水位回退到 MIN(first_seen)-1s 重扫一遍；重复投递由
        # UNIQUE(activity_id, subscriber_id) 兜住，已发过的行只会走 skipped。
        if (idle >= IDLE_REWIND_ROUNDS
                and time.time() - float(st.get("last_rewind_at") or 0) > REWIND_COOLDOWN):
            mn = None
            try:
                with c.cursor() as cur:
                    cur.execute("SELECT MIN(first_seen) FROM t_activity WHERE act_state='open'")
                    row = cur.fetchone()
                mn = row[0] if row else None
            except Exception as e:
                log("  !! 查 MIN(first_seen) 失败：%r" % (e,))
            if mn is not None and mn.strftime("%Y-%m-%d %H:%M:%S") < since:
                target = (mn - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
                log("  !! 连续 %d 轮空转且 MIN(first_seen)=%s 早于水位 %s，"
                    "回退水位到 %s 补扫一轮（幂等兜底，已投递过的不会重发）"
                    % (idle, mn.strftime("%Y-%m-%d %H:%M:%S"), since, target))
                st["last_dispatch"] = target
                st["last_activity_id"] = ""
                st["idle_rounds"] = 0
                st["last_rewind_at"] = time.time()
                st["rewind_round"] = True
        save_state(st)
        _safe_rollback(c)      # 释放事务，别让快照卡住下一轮
        return 0

    if not subs:
        # 有活动但一个活跃订阅者都没有（全部被停用/删光）。
        # 这里绝不能推进水位 —— 否则这批活动的 first_seen 会落在水位之下，
        # 等有人重新订阅时也永远查不到，等于永久丢失。
        log("新活动 %d 条，但活跃订阅者为 0 —— 水位保持不动，等有人订阅后补推" % len(acts))
        _safe_rollback(c)
        return 0

    log("新活动 %d 条，活跃订阅者 %d 人（水位 %s / %s）%s"
        % (len(acts), len(subs), since, since_id or "-",
           "  [补扫轮]" if catching_up else ""))
    sent = skipped = failed = unknown = planned = 0

    # dry 用：本批活动的已有投递对（纯 SELECT）+ 批内去重，完全不写 t_delivery。
    existing_pairs = set()
    planned_pairs_seen = set()
    if dry:
        ids = [a["activity_id"] for a in acts]
        if ids:
            ph = ",".join(["%s"] * len(ids))
            with c.cursor() as cur:
                cur.execute("SELECT activity_id, subscriber_id FROM t_delivery "
                            "WHERE activity_id IN (%s)" % ph, tuple(ids))
                existing_pairs = set((r[0], r[1]) for r in cur.fetchall())
        log("  [dry] 本批已有投递记录 %d 对，只做推演、不写库" % len(existing_pairs))

    for act in acts:
        # 修复 A6：render 可能有脏数据（quota 类型异常、日期是字符串等）。
        # 单条渲染失败只跳过这条活动，不能把整批炸掉、更不能让水位原地不动
        # 导致每轮都在同一批上崩（旧代码就是这个死循环）。
        try:
            content = render(act)
        except Exception as e:
            log("  !! 活动 %s 渲染失败，跳过（不影响其余活动）：%r"
                % (act.get("activity_id"), e))
            continue

        for sub in subs:
            pair = (act["activity_id"], sub["subscriber_id"])
            try:
                hit, why = match(sub, act)
                if not hit:
                    skipped += 1
                    continue

                # 补扫轮（水位兜底回退）专用护栏：只补发给"活动发现时已经在订阅"的人。
                # 否则水位一旦回退，刚加入的新订阅者会一次性收到几十条老活动 —— 那才是
                # 真正的"多余消息"。老订阅者缺记录才是要救的漏推。
                if catching_up:
                    ct, fs = sub.get("create_time"), act.get("first_seen")
                    if ct and fs and ct > fs:
                        skipped += 1
                        log("  [补扫] 跳过 %s（订阅时间晚于该活动发现时间）"
                            % (sub.get("nickname"),))
                        continue

                if dry:
                    if pair in existing_pairs or pair in planned_pairs_seen:
                        skipped += 1
                        continue
                    planned_pairs_seen.add(pair)
                    planned += 1
                    log("  [dry] 会发给 %s：%s"
                        % (sub.get("nickname"), act.get("title")))
                    continue

                # 幂等：只有首次插入成功才发送
                with c.cursor() as cur:
                    try:
                        n = cur.execute("""INSERT INTO t_delivery
                            (activity_id, activity_title, subscriber_name, subscriber_id,
                             channel, send_status, attempt, create_by, create_time)
                            VALUES (%s,%s,%s,%s,%s,'pending',0,'dispatcher',NOW())""",
                            (act["activity_id"], (act["title"] or "")[:500],
                             (sub.get("nickname") or "")[:100], sub["subscriber_id"],
                             sub["channel"]))
                    except pymysql.err.IntegrityError:
                        n = 0
                    except Exception as e:
                        log("  !! 插入投递失败 %r" % (e,))
                        n = 0
                if n != 1:
                    skipped += 1
                    continue

                if token is None:
                    try:
                        token = get_token(st, conf)
                    except Exception as e:
                        log("  !! 拿 token 失败：%r" % (e,))
                        with c.cursor() as cur:
                            cur.execute("""UPDATE t_delivery SET send_status='failed',
                                           attempt=attempt+1, last_error=%s
                                           WHERE activity_id=%s AND subscriber_id=%s""",
                                        (str(e)[:480], act["activity_id"], sub["subscriber_id"]))
                        c.commit()
                        failed += 1
                        continue

                ok, code, msg = wecom_send(token, conf["agent_id"], sub["external_id"], content)
                if not ok and code in (42001, 40014, 40001):     # token 失效，重试一次
                    token = get_token(st, conf, force=True)
                    ok, code, msg = wecom_send(token, conf["agent_id"], sub["external_id"], content)

                with c.cursor() as cur:
                    if ok:
                        cur.execute("""UPDATE t_delivery SET send_status='sent',
                                       attempt=attempt+1, sent_time=NOW(), last_error=''
                                       WHERE activity_id=%s AND subscriber_id=%s""",
                                    (act["activity_id"], sub["subscriber_id"]))
                        sent += 1
                        log("  ✅ %s ← %s" % (sub.get("nickname"), (act.get("title") or "")[:28]))
                    elif code == UNKNOWN:
                        # 修复 A5：超时/连接异常/5xx 一律记 unknown —— 消息可能已经
                        # 送达，绝不能判 failed，否则 retry_failed 会重发、学生收两遍。
                        # attempt 直接顶到上限，彻底移出任何自动重试路径。
                        cur.execute("""UPDATE t_delivery SET send_status='unknown',
                                       attempt=99, last_error=%s
                                       WHERE activity_id=%s AND subscriber_id=%s""",
                                    (("结果未知 %s" % msg)[:480],
                                     act["activity_id"], sub["subscriber_id"]))
                        unknown += 1
                        log("  ⚠️ %s 结果未知（已标 unknown，不重发）：%s"
                            % (sub.get("nickname"), msg))
                    else:
                        cur.execute("""UPDATE t_delivery SET send_status='failed',
                                       attempt=attempt+1, last_error=%s
                                       WHERE activity_id=%s AND subscriber_id=%s""",
                                    (("errcode=%s %s" % (code, msg))[:480],
                                     act["activity_id"], sub["subscriber_id"]))
                        failed += 1
                        log("  ❌ %s 失败 errcode=%s %s" % (sub.get("nickname"), code, msg))
                c.commit()

            except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as e:
                # 连接级错误（MySQL 断了）：整批作废 —— 不能推进水位，否则这一批
                # 既没发出去、又再也不会被查到。抛给 main() 重连，下一轮幂等重来。
                log("  !! 数据库连接异常，本轮整批作废、不推进水位：%r" % (e,))
                raise
            except Exception as e:
                # 修复 A6：单条 (活动 × 订阅者) 的任何异常都不许拖垮整批。
                # 必须先 rollback 再继续，否则连接带着坏事务，后面每条都失败。
                log("  !! 单条投递异常 %s × %s：%r（继续下一条）"
                    % (act.get("activity_id"), sub.get("nickname"), e))
                _safe_rollback(c)
                failed += 1
                continue

    if dry:
        log("  [dry] 本轮未发送、未写库、未推进水位：会发 %d 条，跳过 %d 条"
            % (planned, skipped))
        _safe_rollback(c)
        return planned

    # 水位推进到本批最后一条活动的 (first_seen, activity_id)，而不是 now()。
    # 否则一旦积压超过单批上限，多出来的活动会被水位越过去、永远推不出去。
    last = acts[-1]
    st["last_dispatch"] = last["first_seen"].strftime("%Y-%m-%d %H:%M:%S")
    st["last_activity_id"] = last["activity_id"] or ""
    st["idle_rounds"] = 0
    st["rewind_round"] = False
    if len(acts) >= 200:
        log("  !! 本批达到上限 200 条，剩余活动下一轮继续（水位 %s / %s）"
            % (st["last_dispatch"], st["last_activity_id"]))
    save_state(st)

    log("本轮完成：发送 %d，跳过 %d，失败 %d，结果未知 %d（水位推进到 %s / %s）"
        % (sent, skipped, failed, unknown, st["last_dispatch"], st["last_activity_id"]))
    return sent


def print_stats(c):
    with c.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("""SELECT send_status, COUNT(*) n FROM t_delivery GROUP BY send_status""")
        rows = cur.fetchall()
        print("\n=== 投递统计 ===")
        for r in rows:
            print("  %-8s %d" % (r["send_status"], r["n"]))
        cur.execute("""SELECT d.delivery_id, d.activity_title, d.subscriber_name,
                              d.send_status, d.attempt, d.last_error, d.sent_time
                       FROM t_delivery d ORDER BY d.delivery_id DESC LIMIT 10""")
        print("\n=== 最近 10 条 ===")
        for r in cur.fetchall():
            print("  #%s %-6s %-10s %s | %s" % (
                r["delivery_id"], r["send_status"], r["subscriber_name"] or "-",
                (r["activity_title"] or "")[:26], r["last_error"] or ""))
        cur.execute("SELECT COUNT(*) n FROM t_activity WHERE act_state='open'")
        print("\n开放活动数: %d" % cur.fetchone()["n"])
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--interval", type=int, default=INTERVAL)
    args = ap.parse_args()

    c = conn()
    st = load_state()

    if args.stats:
        print_stats(c)
        return

    if args.once or args.dry_run:
        if args.dry_run:
            # 修复 P0-7：dry-run 必须完全只读。
            # 三重保险：① 传状态副本，即使内部改了也落不了盘；
            #           ② save_state() 在 DRY 开关下直接 return；
            #           ③ 主循环 dry 分支连 INSERT/DELETE 都不发（只做局部 set 去重）。
            log("== dry-run：只读试跑，不发送 / 不写库 / 不写状态 / 不推进水位 ==")
            run_once(c, dict(st), None, dry=True)
        else:
            run_once(c, st, None)
            print_stats(c)
        return

    stopping = {"v": False}
    signal.signal(signal.SIGTERM, lambda *a: stopping.update(v=True))
    signal.signal(signal.SIGINT, lambda *a: stopping.update(v=True))
    log("推送器启动，间隔 %ds（水位 %s）" % (args.interval, st.get("last_dispatch")))

    # 两个独立节奏：
    #   · 通讯录同步 SYNC_INTERVAL(60s) —— 成员增删/停用更快反映
    #   · 活动分发 INTERVAL(120s)+jitter —— 扫描新活动并推送
    last_sync = 0.0
    last_dispatch = 0.0
    while not stopping["v"]:
        nowt = time.time()
        try:
            c.ping(reconnect=True)

            if nowt - last_sync >= SYNC_INTERVAL:
                try:
                    conf_s = load_conf()
                    tok_s = get_token(st, conf_s)
                    sync_contacts(c, tok_s, st=st)
                except Exception as e:
                    log("!! 通讯录同步失败：%r" % (e,))
                last_sync = time.time()

            if nowt - last_dispatch >= (args.interval + random.randint(0, JITTER)):
                run_once(c, st, None, skip_sync=True)
                last_dispatch = time.time()
        except Exception as e:
            log("!! 本轮异常：%r" % (e,))
            try:
                c.close()          # 先关旧连接，别每轮泄漏一个 MySQL 会话
            except Exception:
                pass
            try:
                c = conn()
            except Exception:
                pass
            last_sync = time.time()
            last_dispatch = time.time()
        # 小步 sleep，保证 Ctrl-C / systemd stop 能及时退出
        slept = 0.0
        while slept < CHECK_TICK and not stopping["v"]:
            time.sleep(1)
            slept += 1
    c.close()
    log("已停止。")


if __name__ == "__main__":
    main()
