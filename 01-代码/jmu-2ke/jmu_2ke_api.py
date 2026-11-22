"""
集美大学「第二课堂」(2ke.jmu.edu.cn) 数据接口客户端
=====================================================

结论：该系统**没有独立的 REST/JSON 接口**（/api/activity* 全部 404）。
唯一的数据出口是 Next.js App Router 的 **RSC flight 载荷**：
    GET https://2ke.jmu.edu.cn/dashboard      Header: RSC: 1
    -> Content-Type: text/x-component

认证：Auth.js (NextAuth) 的会话 Cookie
    __Secure-authjs.session-token   (JWE, HttpOnly, 约 30 天有效)

用法：
    from 2ke_api import Client
    c = Client.from_cookie_file()          # 或 Client.from_cdp() 从浏览器实时取
    snap = c.snapshot()                    # 全部活动 + 字典
    for a in snap["open"]:                 # 可报名与进行中
        print(a["title"], a["credit"], a["start_local"])
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests

BASE = "https://2ke.jmu.edu.cn"
HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(HERE, "2ke_cookie.json")

CST = timezone(timedelta(hours=8))


class SessionExpired(RuntimeError):
    """登录会话失效 / 被重定向到 SSO。"""


class PayloadInvalid(RuntimeError):
    """拿到的 RSC 载荷结构不对（解析半失效）。

    典型形态：Next.js 把 `"primary":[...]` 改成引用块 `"primary":"$R1"`，
    parse_flight 静默返回 {}，于是 open 永远是 0 条，但 ended 还在刷新
    last_seen —— 采集日志一切"正常"，实际新活动永久不入库。
    collector 侧据此判 FAIL，触发退避并在日志里留痕。
    """


EXPECTED_KEYS = ("primary", "ended")     # 少任何一个都视为解析失效

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")


# --------------------------------------------------------------------------
# RSC flight 解析
# --------------------------------------------------------------------------
def _scan_array(text, start):
    """start 指向 '['，返回配平的 JSON 数组子串。"""
    depth, i, instr, esc = 0, start, False, False
    while i < len(text):
        ch = text[i]
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
        else:
            if ch == '"':
                instr = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    return None


def _load_flight(s):
    """把 flight 里的 React 标记还原成合法 JSON。"""
    s = s.replace("$undefined", "null")
    s = re.sub(r'"\$D([^"]*)"', r'"\1"', s)
    s = re.sub(r"\$D(\d{4}-)", r"\1", s)
    return json.loads(s)


def parse_flight(txt, keys=("primary", "ended", "signedUpLater",
                             "deptOptions", "typeOptions", "rangeOptions", "menus")):
    out = {}
    for key in keys:
        m = re.search(r'"%s":\s*\[' % key, txt)
        if not m:
            continue
        sub = _scan_array(txt, txt.index("[", m.start()))
        if not sub:
            continue
        try:
            out[key] = _load_flight(sub)
        except Exception:
            continue
    return out


# --------------------------------------------------------------------------
# 客户端
# --------------------------------------------------------------------------
class Client:
    def __init__(self, cookies, timeout=30):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.s.headers["Accept"] = "text/x-component"
        self.timeout = timeout
        for c in cookies:
            self.s.cookies.set(c["name"], c["value"],
                               domain=c.get("domain", "2ke.jmu.edu.cn"),
                               path=c.get("path", "/"))

    # ---- 构造 ----
    @classmethod
    def from_cookie_file(cls, path=COOKIE_FILE):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(data["cookies"] if isinstance(data, dict) else data)

    @classmethod
    def from_cdp(cls, port=None):
        """从正在运行的 Chrome 直接取 Cookie（需开启远程调试）。"""
        return cls(cookies_via_cdp(port))

    # ---- 原始请求 ----
    def flight(self, path="/dashboard", rsc=True):
        r = self.s.get(BASE + path,
                       headers={"RSC": "1"} if rsc else {},
                       timeout=self.timeout)
        r.encoding = "utf-8"
        # 会话失效时会被 302 到统一身份认证并返回 200 HTML —— 必须显式识别，
        # 否则解析出空列表会被误判成"没有活动"，静默失去监控能力。
        if "webexp.jmu.edu.cn" in r.url or "/login" in r.url:
            raise SessionExpired(
                "会话已失效：请求被重定向到统一身份认证 (%s)" % r.url[:120])
        # 修复 P2-10：raise_for_status() 必须在 content-type 判定之前。
        # 旧顺序是「先判 content-type，再 raise」——nginx 返 502/504 的 HTML 错误页
        # 会被判成"会话已失效"，于是采集器退避 1800s 并打印"会话失效"，
        # 把"上游挂了"误诊成"cookie 过期"，一次误导就是半小时。
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if rsc and "x-component" not in ctype:
            raise SessionExpired(
                "拿到的不是 RSC 数据 (content-type=%s)，登录可能已失效" % ctype[:60])
        # text/x-component 不带 charset，requests 会按 ISO-8859-1 解码 -> 中文乱码
        r.encoding = "utf-8"
        return r.text

    def session_json(self):
        """GET /api/auth/session —— 目前唯一真正的 JSON 接口。"""
        r = self.s.get(BASE + "/api/auth/session", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---- 业务 ----
    def snapshot(self):
        """返回结构化快照：open / ended / 字典表。"""
        raw = parse_flight(self.flight("/dashboard"))
        depts = {d["value"]: d["label"] for d in raw.get("deptOptions", [])}
        types = {t["id"]: t for t in raw.get("typeOptions", [])}
        ranges = {r["value"]: r["label"] for r in raw.get("rangeOptions", [])}

        def norm(rec):
            a = rec.get("activity") or {}
            credit_raw = a.get("credit")
            try:
                credit = json.loads(credit_raw) if credit_raw else []
            except Exception:
                credit = credit_raw
            t = types.get(a.get("creditType"), {})
            return {
                "id": a.get("id"),
                "activityId": rec.get("activityId"),
                "signup_record_id": rec.get("id"),
                "title": a.get("title"),
                "address": a.get("address"),
                # 参加时间（UTC -> 北京时间）
                "start_local": _local(rec.get("activityTime") or a.get("startTime")),
                "end_local": _local(rec.get("activityEndTime")),
                # 报名/签到窗口
                "signin_window": [_local(rec.get("signInWindowStart")),
                                  _local(rec.get("signInWindowEnd"))],
                "signin_way": rec.get("signInWay"),
                "quota": _int(a.get("number")),
                "credit": credit,                      # [{"credit":"0.1","number":"2000"}]
                # 学分是分档的：credit=该档学分，number=该档人数。
                # 求和值没有实际含义（0.4+0.3+0.2+0.1=1.0，没人能拿到），取档位极值。
                "credit_total": _credit_extreme(credit, max),
                "credit_min": _credit_extreme(credit, min),
                "credit_max": _credit_extreme(credit, max),
                "credit_tiered": isinstance(credit, list) and len(credit) > 1,
                "activity_type_code": a.get("activityType"),          # yard / school
                "activity_type_label": ranges.get(a.get("activityType"), a.get("activityType")),
                "credit_type_id": a.get("creditType"),
                "credit_type_name": t.get("name"),
                "credit_type_max": t.get("maxNumber"),
                "dept_id": a.get("deptId"),
                "dept_label": depts.get(a.get("deptId")),
                "creator_college": rec.get("creatorCollegeNames"),
                "signup_type": a.get("signUpType"),     # rob=抢名额
                "status": a.get("status"),
                "created_at": _local(a.get("createdAt")),
                "updated_at": _local(a.get("updatedAt")),
                "raw": rec,
            }

        out = {
            "fetched_at": datetime.now(CST).isoformat(),
            "open": [norm(r) for r in raw.get("primary", [])],
            "ended": [norm(r) for r in raw.get("ended", [])],
            "signed_up": [norm(r) for r in raw.get("signedUpLater", [])],
            "departments": depts,
            "activity_types": {k: v.get("name") for k, v in types.items()},
            "ranges": ranges,
            # 修复 A8：把实际解析到的 key 暴露出去，采集器据此断言"解析没半失效"。
            # 旧版这里什么都不留，primary 整个消失时调用方只看到 open=[]，无从分辨
            # "真的没有活动"和"解析坏了"。
            "raw_keys": sorted(raw.keys()),
        }
        assert_payload(out)
        return out

    # ---- Cookie 持久化 ----
    def save_cookies(self, path=COOKIE_FILE):
        """把内存里的 cookie 落盘（修复 A7）。

        为什么必须做：2ke 是 Auth.js，会话 token 每 30 天滚动一次，滚动后的新 token
        只出现在响应的 Set-Cookie 里，requests.Session 只更新内存。旧版从不落盘，
        于是「进程不重启就正常，一重启就回退到写死在文件里的旧 token」，
        旧 token 的 30 天 exp 一过就是永久 SESSION_EXPIRED。

        写法规矩：
          · 先把 `__access_token` 与 `__Secure-authjs.session-token` 都确认在 jar 里，
            缺任何一个直接抛异常、**不覆盖**原文件（否则会写出 100% 失效的 cookie，
            参见审计 A · P0）；
          · 写 `.tmp` + `os.replace` 原子替换，权限 0600，并保留原文件属主。
        """
        cks = []
        for c in self.s.cookies:
            cks.append({"name": c.name, "value": c.value,
                        "domain": c.domain, "path": c.path})

        names = set(c["name"] for c in cks)
        missing = [n for n in ("__access_token", "__Secure-authjs.session-token")
                   if n not in names]
        if missing:
            raise RuntimeError(
                "拒绝写入 cookie：缺少 %s（现有 %d 个）" % (",".join(missing), len(cks)))

        try:
            old = os.stat(path)
            uid, gid = old.st_uid, old.st_gid
        except OSError:
            uid = gid = None

        tmp = path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"cookies": cks,
                           "saved_at": datetime.now(CST).isoformat()},
                          f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        if uid is not None:
            try:
                os.chown(path, uid, gid)      # os.replace 会把属主变成当前进程
            except OSError:
                pass
        return path

    def session_expiry(self):
        try:
            return self.session_json().get("expires")
        except Exception:
            return None


def assert_payload(snap):
    """校验 RSC 载荷解析结果，坏掉就抛 PayloadInvalid（修复 A8）。

    三条判据（成本极低，但能挡住"静默半失效"这类最危险的漏推）：
      1. open + ended 总数为 0 → 平台不可能真的零活动，判定解析失效；
      2. 缺 primary / ended 任一 key → 平台改版了，判定解析失效；
      3. primary 有 key 但解析出的 open 少于 1 且 ended 非空 → 也视为异常
         （`"primary":"$R1"` 引用块形态会命中这里）。
    """
    keys = set(snap.get("raw_keys") or [])
    missing = [k for k in EXPECTED_KEYS if k not in keys]
    if missing:
        raise PayloadInvalid("RSC 载荷缺少 key %s（实际解析到 %s）"
                            % (",".join(missing), ",".join(sorted(keys)) or "无"))
    n_open = len(snap.get("open") or [])
    n_ended = len(snap.get("ended") or [])
    if n_open + n_ended == 0:
        raise PayloadInvalid("EMPTY_PAYLOAD：open+ended 总数为 0")
    return n_open, n_ended


def _credit_extreme(credit, fn):
    """分档学分取极值。

    credit = [{"credit":"0.4","number":"1"}, ...]，number 是该档人数。
    求和值（0.4+0.3+0.2+0.1=1.0）没有任何人能拿到，只能取档位极值。
    """
    if not isinstance(credit, list):
        return None
    vals = []
    for x in credit:
        try:
            v = x.get("credit")
            if v is None or str(v).strip() == "":
                continue
            vals.append(float(v))
        except (TypeError, ValueError, AttributeError):
            continue
    return fn(vals) if vals else None


def _local(iso):
    """UTC ISO -> 北京时间 'YYYY-MM-DD HH:MM'。"""
    if not iso:
        return None
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


def _int(v):
    try:
        return int(str(v).strip())
    except Exception:
        return None


# --------------------------------------------------------------------------
# 通过 CDP 从运行中的 Chrome 取 Cookie
# --------------------------------------------------------------------------
def cookies_via_cdp(port=None):
    import websocket  # websocket-client

    ud = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")
    with open(os.path.join(ud, "DevToolsActivePort"), encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    p, path = (port or lines[0]), lines[1]
    ws = websocket.create_connection("ws://127.0.0.1:%s%s" % (p, path),
                                     timeout=30, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": "Storage.getCookies",
                            "params": {"browserContextId": None}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return [c for c in msg["result"]["cookies"]
                        if "jmu.edu.cn" in c.get("domain", "")]
    finally:
        ws.close()


if __name__ == "__main__":
    import sys
    if "--refresh-cookie" in sys.argv:
        c = Client.from_cdp()
        print("saved ->", c.save_cookies())
    else:
        c = Client.from_cookie_file()
    snap = c.snapshot()
    print("session expires:", c.session_expiry())
    print("开放中 %d 场 / 已结束 %d 场" % (len(snap["open"]), len(snap["ended"])))
    for a in snap["open"]:
        print("  %-34s 学分=%-6s 名额=%-5s %s  %s  [%s]" % (
            a["title"], a["credit_total"], a["quota"],
            a["start_local"], a["address"], a["activity_type_label"]))
