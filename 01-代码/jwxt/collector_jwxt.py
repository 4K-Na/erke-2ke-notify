#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集美大学教务（jwxt）讲座采集器
================================
数据源：EAMS 教务系统的两个 JSON 接口（都要登录 cookie）
  GET /student/for-std/lecture-enroll/un-enroll-search   → 讲座列表（本文件主用）
  GET /student/for-std/lecture-enroll/search             → 我的报名记录（补 act_state）

登录态：/opt/jwxt/cookie.txt（一行 Cookie 头，600 权限）
  __pstsid__ 约 2 天过期、SESSION 是会话级 → 失效时接口会 302/返回 HTML，
  本脚本检测到就写状态文件并退出，不假装成功。

用法：
  python3 collector_jwxt.py            # 跑一次
  python3 collector_jwxt.py --verbose  # 打印每条
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

import pymysql

def _load_db_config():
    """数据库连接参数从 db.json 读（600 权限），不硬编码在源码里。"""
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.json")
    with open(_p, "r", encoding="utf-8") as _f:
        return json.load(_f)


DB = dict(_load_db_config(), cursorclass=pymysql.cursors.DictCursor)
COOKIE_FILE = "/opt/jwxt/cookie.txt"
TGC_FILE = "/opt/jwxt/tgc.txt"
CAS = "https://cas.paas.jmu.edu.cn/cas/login?service="
SSO_SVC = "https://jwxt.jmu.edu.cn/student/sso/login"
PUSH_CONF = "/opt/jwxt/push.json"
WECOM_CONF = "/opt/2ke-hub/wecom.json"
PORTAL = "https://i.jmu.edu.cn"
STATE_FILE = "/opt/jwxt/state.json"
LOG_FILE = "/opt/jwxt/collector.log"
BASE = "https://jwxt.jmu.edu.cn/student/for-std/lecture-enroll"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
VERBOSE = "--verbose" in sys.argv


def log(msg):
    line = "[%s] %s" % (time.strftime("%F %T"), msg)
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state():
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)
    os.chmod(STATE_FILE, 0o600)


def read_cookie():
    if not os.path.exists(COOKIE_FILE):
        return None
    s = open(COOKIE_FILE, encoding="utf-8").read().strip()
    return s or None


def fetch(path, cookie, timeout=30):
    """返回 (json或None, 状态说明)"""
    url = BASE + path
    req = urllib.request.Request(url, headers={
        "Cookie": cookie,
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://jwxt.jmu.edu.cn/student/for-std/lecture-enroll/index/unEnroll/",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
            ctype = r.headers.get("Content-Type", "")
            status = r.getcode()
    except urllib.error.HTTPError as e:
        return None, "HTTP %s" % e.code
    except Exception as e:
        return None, "ERR %r" % (e,)

    if "json" not in ctype.lower() or not body.strip().startswith("{"):
        return None, "非 JSON（大概率登录失效，HTTP %s, %dB）" % (status, len(body))
    try:
        return json.loads(body), "ok"
    except Exception as e:
        return None, "JSON 解析失败 %r" % (e,)


ALERT_COOLDOWN = 3600          # 同类告警 1 小时内只发一次


def send_alert(text, st):
    """给管理员发企业微信；冷却期内不重复。"""
    if time.time() - st.get("last_alert_at", 0) < ALERT_COOLDOWN:
        log("  （告警冷却中，跳过）")
        return False
    try:
        conf = json.load(open("/opt/2ke-hub/wecom.json", encoding="utf-8"))
        url = ("https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s"
               % (conf["corp_id"], conf["secret"]))
        tok = json.load(urllib.request.urlopen(url, timeout=15)).get("access_token")
        if not tok:
            log("  !! 告警失败：拿不到企业微信 token")
            return False
        body = json.dumps({
            "touser": conf.get("admin_userid", "LvZhiYi"),
            "msgtype": "text",
            "agentid": conf["agent_id"],
            "text": {"content": text},
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + tok,
            data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        r = json.load(urllib.request.urlopen(req, timeout=15))
        if r.get("errcode") == 0:
            st["last_alert_at"] = time.time()
            save_state(st)
            log("  已给管理员发告警")
            return True
        log("  !! 告警失败 errcode=%s %s" % (r.get("errcode"), r.get("errmsg")))
    except Exception as e:
        log("  !! 告警异常 %r" % (e,))
    return False


def refresh_session_from_tgc():
    """用 TGC 走一遍 CAS SSO，换出新的 jwxt 会话。

    流程（实测可行）：
      GET cas/login?service=<jwxt sso>   带 Cookie: TGC=…
        → 302 Location: https://jwxt.jmu.edu.cn/student/sso/login?ticket=ST-…
      GET 该 Location（跟随 302）
        → 302 设 __pstsid__ + SESSION → 再 302 到 /student/home
    返回 "…__pstsid__=…; SESSION=…" 或 None。
    """
    if not os.path.exists(TGC_FILE):
        return None
    tgc = open(TGC_FILE, encoding="utf-8").read().strip()
    if not tgc:
        return None

    import http.cookiejar
    import urllib.parse

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", UA)]

    # 手动把 TGC 塞进 jar
    c = http.cookiejar.Cookie(
        version=0, name="TGC", value=tgc, port=None, port_specified=False,
        domain="cas.paas.jmu.edu.cn", domain_specified=True, domain_initial_dot=False,
        path="/cas/", path_specified=True, secure=True, expires=None,
        discard=True, comment=None, comment_url=None, rest={}, rfc2109=False)
    cj.set_cookie(c)

    q = CAS + urllib.parse.quote(SSO_SVC, safe="")
    try:
        with opener.open(q, timeout=30) as r:
            body = r.read()
            final = r.geturl()
    except urllib.error.HTTPError as e:
        # 302 被 opener 自动跟随；若最终回到登录表单说明 TGC 失效
        return None
    except Exception as e:
        log("  TGC 续期异常 %r" % (e,))
        return None

    # 跟随完成后再请求一次目标页，确保 SESSION 落地
    try:
        with opener.open("https://jwxt.jmu.edu.cn/student/home", timeout=30) as r:
            r.read()
    except Exception:
        pass

    pst = sess = None
    for ck in cj:
        if ck.name == "__pstsid__" and (ck.path == "/student" or ck.path == "/"):
            pst = ck.value
        if ck.name == "SESSION" and ck.path.startswith("/student"):
            sess = ck.value
    if not (pst and sess):
        log("  TGC 续期：没拿到 __pstsid__/SESSION（TGC 可能已失效）")
        return None
    return "__pstsid__=%s; SESSION=%s" % (pst, sess)


def strip_html(s):
    """把 jwxt 的富文本介绍洗成纯文本（保留段落换行）。"""
    if not s:
        return None
    import html as _h
    import re as _re
    t = _re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=_re.S | _re.I)
    t = _re.sub(r"<br\s*/?>|</p>|</div>|</tr>|</h[1-6]>", "\n", t, flags=_re.I)
    t = _re.sub(r"<[^>]+>", " ", t)
    t = _h.unescape(t).replace("\u00a0", " ")
    t = _re.sub(r"[ \t\r\f\v]+", " ", t)
    t = _re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip() or None


def auto_cas_login(st=None):
    """TGC 失效时调用 CAS 自动登录（纯 HTTP，无需短信）。成功返回 True。

    st 传进来是为了把统计写回同一个状态对象，避免被后续 save_state 覆盖。
    """
    import subprocess
    script = "/opt/jwxt/cas_auto_login.py"
    if not os.path.exists(script):
        return False
    try:
        r = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        for line in (r.stdout or "").splitlines():
            if line.strip():
                log("  " + line.strip())
        if r.returncode == 0:
            if st is None:
                st = load_state()
            st["auto_login_at"] = time.strftime("%F %T")
            st["auto_login_count"] = st.get("auto_login_count", 0) + 1
            save_state(st)
            return True
    except Exception as e:
        log("  自动登录异常 %r" % (e,))
    return False


def fetch_with_recovery(cookie, st):
    """取讲座列表；失败了就自动登录 + 重建会话 + 重试一次。

    判据是"接口能不能拿到 JSON"，而不是"TGC 续期有没有返回 cookie"——
    后者会假成功（CAS 签了 ticket 但 jwxt 拒绝，返回 403）。
    """
    data, err = fetch("/un-enroll-search", cookie)
    if data is not None:
        return data, cookie, err

    log("  接口失败（%s）→ 尝试自动登录修复" % err)
    if not auto_cas_login(st):
        return None, cookie, err

    fresh = refresh_session_from_tgc()
    if not fresh:
        log("  !! 自动登录成功但重建会话失败")
        return None, cookie, err

    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(fresh + "\n")
        os.chmod(COOKIE_FILE, 0o600)
    except Exception as e:
        log("  !! 回写 cookie 失败 %r" % (e,))

    data, err2 = fetch("/un-enroll-search", fresh)
    if data is not None:
        log("  自愈成功：自动登录后已能取数")
        st["tgc_ok"] = True
        st.pop("tgc_dead_at", None)
        save_state(st)
        return data, fresh, "ok"

    log("  !! 自愈后仍然失败：%s" % err2)
    return None, fresh, err2


def dt(v):
    if not v:
        return None
    s = str(v).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except Exception:
            continue
    return None


def pick(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def upsert(c, row):
    sql = """
    INSERT INTO t_lecture
      (lecture_id, title, lecturer, lecture_type, department, place,
       open_start, open_end, enroll_start, enroll_end, upper_limit, enroll_count,
       report_count, biz_type, semester, lecture_content, teacher_content,
       content_text, teacher_text, raw_json,
       act_state, first_seen, last_seen)
    VALUES
      (%(lecture_id)s,%(title)s,%(lecturer)s,%(lecture_type)s,%(department)s,%(place)s,
       %(open_start)s,%(open_end)s,%(enroll_start)s,%(enroll_end)s,%(upper_limit)s,%(enroll_count)s,
       %(report_count)s,%(biz_type)s,%(semester)s,%(lecture_content)s,%(teacher_content)s,
       %(content_text)s,%(teacher_text)s,%(raw_json)s,
       %(act_state)s,NOW(),NOW())
    ON DUPLICATE KEY UPDATE
      title=VALUES(title), lecturer=VALUES(lecturer), lecture_type=VALUES(lecture_type),
      department=VALUES(department), place=VALUES(place),
      open_start=VALUES(open_start), open_end=VALUES(open_end),
      enroll_start=VALUES(enroll_start), enroll_end=VALUES(enroll_end),
      upper_limit=VALUES(upper_limit), enroll_count=VALUES(enroll_count),
      report_count=VALUES(report_count), biz_type=VALUES(biz_type), semester=VALUES(semester),
      lecture_content=VALUES(lecture_content), teacher_content=VALUES(teacher_content),
      content_text=VALUES(content_text), teacher_text=VALUES(teacher_text),
      raw_json=VALUES(raw_json), act_state=VALUES(act_state), last_seen=NOW()
    """
    with c.cursor() as cur:
        cur.execute(sql, row)
        # 1 = 新插入, 2 = 更新
        return cur.rowcount



# ============================ 推送 ============================

def load_push_conf():
    try:
        return json.load(open(PUSH_CONF, encoding="utf-8"))
    except Exception:
        return {"enabled": False}


def wecom_token():
    conf = json.load(open(WECOM_CONF, encoding="utf-8"))
    url = ("https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s"
           % (conf["corp_id"], conf["secret"]))
    tok = json.load(urllib.request.urlopen(url, timeout=15)).get("access_token")
    return tok, conf


def wecom_send_text(tok, agent_id, touser, content):
    body = json.dumps({
        "touser": touser, "msgtype": "text", "agentid": agent_id,
        "text": {"content": content}, "safe": 0,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + tok,
        data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=20))
        return r.get("errcode") == 0, r.get("errmsg", "")
    except Exception as e:
        return False, repr(e)


def render_lecture_rich(r):
    """单条讲座的推送文案（风格对齐二课：拿到就够用，不啰嗦）。"""
    def dtf(x):
        return str(x)[:16] if x else "—"

    lines = ["讲座：有新讲座", "", "【%s】" % (r.get("code") or "未命名讲座")]
    lines.append("主讲：%s" % ((r.get("lecturer") or "—")))
    dept = (r.get("department") or {}).get("nameZh")
    if dept:
        lines.append("主办：%s" % dept)
    _s = str(r.get("openStartDateTime") or "")
    _e = str(r.get("openEndDateTime") or "")
    _e_show = _e[11:16] if (_e and _s and _e[:10] == _s[:10]) else dtf(_e)
    lines.append("时间：%s ~ %s" % (dtf(_s), _e_show))
    if r.get("lecturePlace"):
        lines.append("地点：%s" % r["lecturePlace"])
    up, ec = r.get("upperLimit"), r.get("enrollCount")
    if up is not None:
        left = (up - (ec or 0))
        lines.append("名额：%s 人（已报 %s，剩 %s）" % (up, ec or 0, max(left, 0)))
    if r.get("enrollOpenStartDateTime"):
        lines.append("报名：%s ~ %s" % (dtf(r.get("enrollOpenStartDateTime")),
                                     dtf(r.get("enrollOpenEndDateTime"))))
    lt = (r.get("lectureType") or {}).get("nameZh")
    if lt:
        lines.append("类型：%s" % lt)
    lines.append("讲座ID：%s" % r.get("id"))
    lines.append("")
    lines.append("👉 打开：%s" % PORTAL)
    return "\n".join(lines)


def push_new_lectures(c, st, new_rows):
    """给所有启用订阅者推送新讲座，幂等写 t_lecture_delivery。"""
    conf = load_push_conf()
    if not conf.get("enabled"):
        log("  推送开关未开，新讲座不推（后台可开）")
        return 0

    if not st.get("baseline_done"):
        # 首次建库：只登记不推送，避免一口气刷 3 条
        for r in new_rows:
            _record_delivery(c, r["id"], r.get("code") or "", None, None, None, "skipped", "基线，不推送")
        st["baseline_done"] = True
        save_state(st)
        log("  baseline：登记 %d 条新讲座但不推送（首次建库）" % len(new_rows))
        return 0

    try:
        tok, wconf = wecom_token()
    except Exception as e:
        log("  !! 推送跳过：拿不到企业微信 token %r" % (e,))
        return 0
    if not tok:
        log("  !! 推送跳过：token 为空")
        return 0
    agent = wconf["agent_id"]

    with c.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("""SELECT subscriber_id, external_id, nickname, real_name
                       FROM t_subscriber WHERE status='0' AND channel='wecom'""")
        subs = cur.fetchall()

    sent = 0
    for r in new_rows:
        content = render_lecture_rich(r)
        for sb in subs:
            name = sb.get("real_name") or sb.get("nickname") or ""
            ext = sb.get("external_id")
            if not ext:
                continue
            ok, err = wecom_send_text(tok, agent, ext, content)
            _record_delivery(c, r["id"], r.get("code") or "", sb.get("subscriber_id"), name, ext,
                             "sent" if ok else "failed", "" if ok else err)
            if ok:
                sent += 1
        log("  推送 [%s] %s → %d 人" % (r["id"], (r.get("code") or "")[:24], len(subs)))
    c.commit()
    return sent


def _record_delivery(c, lecture_id, title, subscriber_id, name, ext, status, err):
    with c.cursor() as cur:
        cur.execute("""INSERT INTO t_lecture_delivery
            (lecture_id, lecture_title, subscriber_id, subscriber_name, external_id,
             channel, send_status, attempt, last_error, sent_time)
            VALUES (%s,%s,%s,%s,%s,'wecom',%s,1,%s,%s)
            ON DUPLICATE KEY UPDATE
              send_status=VALUES(send_status), attempt=attempt+1,
              last_error=VALUES(last_error),
              sent_time=IF(VALUES(send_status)='sent', NOW(), sent_time)""",
                    (lecture_id, title[:255], subscriber_id, (name or "")[:64], ext,
                     status, (err or "")[:500], datetime.now() if status == "sent" else None))


def retry_failed_lectures(c):
    """重发失败的讲座推送。口径与二课的 retry_failed 一致：
    只重试 send_status='failed'、attempt<3、6 小时内的；'unknown' 类不重发（可能已送达）。
    """
    conf = load_push_conf()
    if not conf.get("enabled"):
        return 0

    with c.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("""SELECT delivery_id, lecture_id, lecture_title, external_id, attempt
                       FROM t_lecture_delivery
                       WHERE send_status='failed' AND attempt < 3 AND external_id IS NOT NULL
                         AND create_time > DATE_SUB(NOW(), INTERVAL 6 HOUR)
                       ORDER BY delivery_id LIMIT 100""")
        rows = cur.fetchall()
    if not rows:
        return 0

    # 按讲座分组，一次渲染多次复用
    need = sorted({r["lecture_id"] for r in rows})
    texts = {}
    with c.cursor(pymysql.cursors.DictCursor) as cur:
        fmt = ",".join(["%s"] * len(need))
        cur.execute("SELECT lecture_id, raw_json FROM t_lecture WHERE lecture_id IN (" + fmt + ")", need)
        for r in cur.fetchall():
            try:
                texts[r["lecture_id"]] = render_lecture_rich(json.loads(r["raw_json"]))
            except Exception:
                pass

    try:
        tok, wconf = wecom_token()
    except Exception as e:
        log("  !! 重试跳过：拿不到 token %r" % (e,))
        return 0
    if not tok:
        return 0
    agent = wconf["agent_id"]

    ok = 0
    for r in rows:
        txt = texts.get(r["lecture_id"])
        if not txt:
            continue
        good, err = wecom_send_text(tok, agent, r["external_id"], txt)
        with c.cursor() as cur:
            cur.execute("""UPDATE t_lecture_delivery
                           SET attempt = attempt + 1,
                               send_status = %s,
                               last_error = %s,
                               sent_time = IF(%s='sent', NOW(), sent_time)
                           WHERE delivery_id = %s""",
                        ("sent" if good else "failed",
                         ("" if good else err)[:500],
                         "sent" if good else "failed",
                         r["delivery_id"]))
        if good:
            ok += 1
    c.commit()
    log("  重试：%d 条失败记录，成功补发 %d 条" % (len(rows), ok))
    return ok


def main():
    st = load_state()

    # 先用 TGC 自动续一个新会话（有 TGC 就永远不需要人工换 cookie）
    cookie = None
    if os.path.exists(TGC_FILE):
        fresh = refresh_session_from_tgc()
        if fresh:
            cookie = fresh
            try:
                with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                    f.write(fresh + "\n")
                os.chmod(COOKIE_FILE, 0o600)
            except Exception as e:
                log("  !! 回写 cookie 失败 %r" % (e,))
            log("  TGC 续期成功，已用新会话")
            st["tgc_ok"] = True
            st.pop("tgc_dead_at", None)
        else:
            if not st.get("tgc_dead_at"):
                st["tgc_dead_at"] = time.strftime("%F %T")
            st["tgc_ok"] = False
            log("  TGC 已失效，尝试自动登录（CAS 账号密码）…")
            if auto_cas_login(st):
                fresh = refresh_session_from_tgc()
                if fresh:
                    cookie = fresh
                    try:
                        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                            f.write(fresh + "\n")
                        os.chmod(COOKIE_FILE, 0o600)
                    except Exception:
                        pass
                    log("  自动登录后重建会话成功")
                    st["tgc_ok"] = True
                    st.pop("tgc_dead_at", None)
                else:
                    log("  !! 自动登录成功但建不出会话")
            else:
                log("  !! 自动登录失败，退回用 cookie.txt")

    if not cookie:
        cookie = read_cookie()
    if not cookie:
        log("!! 既没有可用 TGC，也没有 cookie 文件 %s" % COOKIE_FILE)
        st.update(ok=False, last_error="无 TGC 也无 cookie", last_try=time.strftime("%F %T"))
        save_state(st)
        return 2

    data, cookie, st1 = fetch_with_recovery(cookie, st)
    if data is None:
        log("!! 讲座列表接口失败：%s" % st1)
        st.update(ok=False, last_error=st1, last_try=time.strftime("%F %T"))
        save_state(st)
        # 登录态失效 → 通知管理员换 cookie
        hint = ("自动登录也失败了（账号密码在 /opt/jwxt/cas-auth.json）。\n"
                "可手动登录后更新 TGC：后台 → 讲座管理 → 更新登录态"
                if "403" in str(st1) or "非 JSON" in str(st1) or "HTTP" in str(st1)
                else "可能是教务系统故障或网络问题，稍后会自动重试")
        msg = ("【集大教务·讲座采集】取数失败\n\n"
               "原因：%s\n\n"
               "%s" % (st1, hint))
        send_alert(msg, st)
        return 3

    rows = data.get("data") or []
    page = data.get("_page_") or {}
    log("接口返回 %d 条（totalRows=%s）" % (len(rows), page.get("totalRows")))

    now = datetime.now()
    ins = upd = 0
    new_list = []          # 本轮新入库的讲座（用于推送）
    pushed = 0
    c = pymysql.connect(**DB)
    try:
        for r in rows:
            lid = r.get("id")
            if not lid:
                continue
            lect_type = (r.get("lectureType") or {})
            dept = (r.get("department") or {})
            biz = (r.get("bizType") or {})
            sem = (r.get("semester") or {})
            open_end = dt(r.get("openEndDateTime"))
            row = dict(
                lecture_id=int(lid),
                title=(r.get("code") or "")[:255],
                lecturer=(r.get("lecturer") or "")[:120],
                lecture_type=(lect_type.get("nameZh") or "")[:60],
                department=(dept.get("nameZh") or "")[:120],
                place=(r.get("lecturePlace") or "")[:160],
                open_start=dt(r.get("openStartDateTime")),
                open_end=open_end,
                enroll_start=dt(r.get("enrollOpenStartDateTime")),
                enroll_end=dt(r.get("enrollOpenEndDateTime")),
                upper_limit=r.get("upperLimit"),
                enroll_count=r.get("enrollCount"),
                report_count=r.get("reportCount"),
                biz_type=(biz.get("nameZh") or "")[:40],
                semester=(sem.get("nameZh") or "")[:40],
                lecture_content=r.get("lectureContent"),
                teacher_content=r.get("teacherContent"),
                content_text=strip_html(r.get("lectureContent")),
                teacher_text=strip_html(r.get("teacherContent")),
                raw_json=json.dumps(r, ensure_ascii=False),
                act_state=("ended" if (open_end and open_end < now) else "open"),
            )
            n = upsert(c, row)
            if n == 1:
                ins += 1
                new_list.append(r)
                if VERBOSE:
                    log("  NEW  [%s] %s | %s | %s" % (lid, row["title"], row["open_start"], row["place"]))
            else:
                upd += 1
        # ---- 状态同步：本轮官网没返回的讲座 → gone（报名截止/已下架）----
        # ⚠️ 必须先确认"拿全了"：接口默认 rowsPerPage=20，没拿全就标 gone 会把
        #    第 21 条起全部误标（P0，审计 A 发现）。拿不全 → 跳过标记并告警。
        _page = data.get("_page_") or {}
        _total = _page.get("totalRows")
        _got = len(rows)
        _complete = (_total is None) or (int(_total) <= _got)

        live_ids = [int(r["id"]) for r in rows if r.get("id")]
        if not _complete:
            log("  !! 分页未拿全（%d/%d 条），本轮跳过 gone 标记（避免误标）" % (_got, int(_total)))
            st["partial"] = True
        elif live_ids:
            fmt = ",".join(["%s"] * len(live_ids))
            with c.cursor() as cur2:
                # 官网已下架但库里还是 open 的
                cur2.execute("UPDATE t_lecture SET act_state='gone'"
                             " WHERE act_state='open' AND lecture_id NOT IN (" + fmt + ")", live_ids)
                gone_n = cur2.rowcount
                # 已结束的（open_end 早于现在）
                cur2.execute("UPDATE t_lecture SET act_state='ended'"
                             " WHERE act_state IN ('open','gone') AND open_end IS NOT NULL AND open_end < NOW()")
                ended_n = cur2.rowcount
            if gone_n or ended_n:
                log("  状态同步：%d 条标为 gone，%d 条标为 ended" % (gone_n, ended_n))

        c.commit()

        # 新讲座 → 推送（幂等写 t_lecture_delivery）
        if new_list:
            try:
                pushed = push_new_lectures(c, st, new_list)
            except Exception as e:
                log("  !! 推送异常 %r" % (e,))

        # 补发历史失败
        try:
            retry_failed_lectures(c)
        except Exception as e:
            log("  !! 重试异常 %r" % (e,))
    except Exception as e:
        c.rollback()
        log("!! 写库失败 %r" % (e,))
        return 4
    finally:
        c.close()

    st.update(
        ok=True, last_error="", last_ok=time.strftime("%F %T"),
        total_rows=len(rows), new=ins, updated=upd,
        pushed=pushed,
    )
    save_state(st)
    log("完成：新增 %d，更新 %d，推送 %d" % (ins, upd, pushed))
    return 0


# ─────────────────────────────────────────────────────────────
# 授权校验：没有有效授权文件就不运行
# ─────────────────────────────────────────────────────────────
_LICENSE_FILE = "/opt/erke-license"
_LICENSE_HASH = "a11c699d562ed20b628f99f81320b329d6f1f7de0469a5af51ff1eec44df4137"


def _require_license():
    """启动前校验授权。校验不过直接退出，不产生任何副作用。"""
    import hashlib as _hl
    if not os.path.exists(_LICENSE_FILE):
        sys.stderr.write(
            "\n[授权] 未找到授权文件 " + _LICENSE_FILE + "\n"
            "       本程序未授权运行，请联系维护者获取授权码。\n\n")
        sys.exit(107)
    try:
        with open(_LICENSE_FILE, "r", encoding="utf-8") as _f:
            _key = _f.read().strip()
    except Exception:
        sys.stderr.write("\n[授权] 授权文件无法读取\n\n")
        sys.exit(107)
    if not _key:
        sys.stderr.write("\n[授权] 授权文件为空\n\n")
        sys.exit(107)
    if _hl.sha256(_key.encode("utf-8")).hexdigest() != _LICENSE_HASH:
        sys.stderr.write(
            "\n[授权] 授权码无效\n"
            "       请联系维护者获取正确的授权码。\n\n")
        sys.exit(107)


_require_license()
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.exit(main())
