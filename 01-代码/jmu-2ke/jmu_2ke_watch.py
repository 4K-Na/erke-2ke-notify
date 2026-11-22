"""
集美大学「第二课堂」新活动监控 / 通知
=====================================

原理：轮询 GET https://2ke.jmu.edu.cn/dashboard (Header: RSC: 1)
     解析 RSC flight 载荷里的 "primary" 数组（= 可报名与进行中）
     与本地已见 ID 集合比对，出现新活动即通知。

用法：
    python jmu_2ke_watch.py --seed      # 首次：把当前活动记为“已知”，不发通知
    python jmu_2ke_watch.py             # 守护运行，默认每 300 秒查一次
    python jmu_2ke_watch.py --once      # 只查一次并打印当前列表
    python jmu_2ke_watch.py --interval 120

通知渠道（优先读同目录的 2ke_watch_config.json，其次环境变量）：
    wxpusher_spt     WxPusher 极简推送令牌 SPT_xxx（推荐：鸿蒙/iOS/Android 原生客户端）
    wxpusher_app_token + wxpusher_uids   标准推送（appToken + UID 列表）
    ntfy_url         自建 ntfy 主题地址，如 http://127.0.0.1:8080/jmu
    ntfy_token       自建 ntfy 若开了鉴权，填访问令牌
    wechat_webhook   企业微信群机器人 webhook
    serverchan_key   Server酱 SendKey
    bark_url         Bark 推送地址（如 https://api.day.app/xxxx）
    desktop_toast    true/false，弹 Windows 通知气泡（默认开）
    interval         轮询间隔秒数（默认 300）
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from jmu_2ke_api import Client, COOKIE_FILE, HERE, SessionExpired

# 重定向到文件时 stdout 默认走系统编码（中文 Windows 是 GBK），强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CST = timezone(timedelta(hours=8))
STATE_FILE = os.path.join(HERE, "2ke_state.json")
LOCK_FILE = os.path.join(HERE, "2ke_watch.lock")
LOG_FILE = os.path.join(HERE, "2ke_events.jsonl")

CONFIG = {
    "interval": 300,          # 轮询间隔（秒）
    "jitter": 30,             # 随机抖动，避免整点打服务器
    "wechat_webhook": os.environ.get("WECHAT_WEBHOOK", ""),
    "serverchan_key": os.environ.get("SERVERCHAN_KEY", ""),
    "bark_url": os.environ.get("BARK_URL", ""),
    # WxPusher —— 鸿蒙/iOS/Android 都有原生客户端，推荐作为手机推送通道
    "wxpusher_spt": os.environ.get("WXPUSHER_SPT", ""),          # SPT_xxx（极简，扫码即得）
    "wxpusher_app_token": os.environ.get("WXPUSHER_APP_TOKEN", ""),  # AT_xxx（标准推送）
    "wxpusher_uids": [u for u in os.environ.get("WXPUSHER_UIDS", "").split(",") if u],
    "ntfy_url": os.environ.get("NTFY_URL", ""),                  # 自建 ntfy，如 http://127.0.0.1:8080/jmu
    "ntfy_token": os.environ.get("NTFY_TOKEN", ""),
    "desktop_toast": os.environ.get("DESKTOP_TOAST", "1") == "1",
    # 只关心这些级别的活动；空 = 全部。可选 yard(院级) / school(校级)
    "only_ranges": [],
    # 只关心标题含这些关键词的活动；空 = 全部
    "keywords": [],
    # 通知里的跳转链接（详情页对学生没有可用深链，所以指到首页）
    "landing_url": os.environ.get("JMU_LANDING_URL",
                                  "https://2ke.jmu.edu.cn/dashboard"),
}

# 从 2ke_watch_config.json 覆盖配置（存在则生效，便于不不改代码就换通道）
CONFIG_FILE = os.path.join(HERE, "2ke_watch_config.json")
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            _user = json.load(f)
        for k, v in _user.items():
            if k in CONFIG and isinstance(v, str) and not v.strip():
                continue          # 空字符串不覆盖默认值
            CONFIG[k] = v
    except Exception as e:
        print("[warn] %s 读取失败：%r" % (CONFIG_FILE, e))


# --------------------------------------------------------------------------
# 通知
# --------------------------------------------------------------------------
def toast(title, body):
    """Windows 通知气泡（不依赖第三方库）。非 Windows 环境直接跳过。"""
    if not CONFIG["desktop_toast"] or os.name != "nt":
        return
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$n=New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon=[System.Drawing.SystemIcons]::Information;"
        "$n.BalloonTipTitle=%s;$n.BalloonTipText=%s;$n.Visible=$true;"
        "$n.ShowBalloonTip(15000);Start-Sleep -Seconds 16;$n.Dispose()"
    )
    def q(s):
        return "'" + str(s).replace("'", "''")[:250] + "'"
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                          "-Command", ps % (q(title), q(body))],
                         creationflags=0x08000000)
    except Exception as e:
        print("  [toast failed] %s" % e)


def notify(title, body, url=None):
    if url:
        body = "%s\n\n👉 打开：%s" % (body, url)

    print("\n" + "=" * 70)
    print("  %s" % title)
    print(body)
    print("=" * 70)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(CST).isoformat(),
                            "title": title, "body": body, "url": url},
                           ensure_ascii=False) + "\n")

    if CONFIG["wechat_webhook"]:
        try:
            requests.post(CONFIG["wechat_webhook"],
                          json={"msgtype": "text",
                                "text": {"content": "%s\n%s" % (title, body)}},
                          timeout=15)
        except Exception as e:
            print("  [wechat failed] %s" % e)

    if CONFIG["serverchan_key"]:
        try:
            requests.post("https://sctapi.ftqq.com/%s.send" % CONFIG["serverchan_key"],
                          data={"title": title, "desp": body}, timeout=15)
        except Exception as e:
            print("  [serverchan failed] %s" % e)

    if CONFIG["bark_url"]:
        try:
            requests.get("%s/%s/%s" % (CONFIG["bark_url"].rstrip("/"),
                                       requests.utils.quote(title),
                                       requests.utils.quote(body)), timeout=15)
        except Exception as e:
            print("  [bark failed] %s" % e)

    # ---- WxPusher：鸿蒙 / iOS / Android 原生客户端 ----
    text = "%s\n%s" % (title, body)
    if CONFIG["wxpusher_spt"]:
        try:
            payload = {"content": text, "summary": title[:100],
                       "contentType": 1, "spt": CONFIG["wxpusher_spt"]}
            if url:
                payload["url"] = url          # 客户端里点通知直接跳转
            r = requests.post(
                "https://wxpusher.zjiecode.com/api/send/message/simple-push",
                json=payload, timeout=20).json()
            print("  [wxpusher/SPT] code=%s msg=%s"
                  % (r.get("code"), r.get("msg")))
        except Exception as e:
            print("  [wxpusher/SPT failed] %s" % e)

    if CONFIG["wxpusher_app_token"] and CONFIG["wxpusher_uids"]:
        try:
            payload = {"appToken": CONFIG["wxpusher_app_token"],
                       "content": text, "summary": title[:100], "contentType": 1,
                       "uids": CONFIG["wxpusher_uids"]}
            if url:
                payload["url"] = url
            r = requests.post(
                "https://wxpusher.zjiecode.com/api/send/message",
                json=payload, timeout=20).json()
            print("  [wxpusher/app] code=%s msg=%s" % (r.get("code"), r.get("msg")))
        except Exception as e:
            print("  [wxpusher/app failed] %s" % e)

    # ---- 自建 ntfy（管理界面 / 历史归档）----
    if CONFIG["ntfy_url"]:
        try:
            h = {"Title": title.encode("utf-8").decode("latin-1", "ignore"),
                 "Priority": "high", "Tags": "school"}
            if CONFIG["ntfy_token"]:
                h["Authorization"] = "Bearer " + CONFIG["ntfy_token"]
            requests.post(CONFIG["ntfy_url"], data=body.encode("utf-8"),
                          headers=h, timeout=15)
        except Exception as e:
            print("  [ntfy failed] %s" % e)

    toast(title, body)


# --------------------------------------------------------------------------
# 状态
# --------------------------------------------------------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"seen": {}, "last_check": None}


def save_state(st):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)          # 原子替换，避免写一半掉电损坏


def acquire_single_instance():
    """防止 systemd/cron 手滑叠加成多个实例。Linux 用 flock；其他平台跳过。"""
    try:
        import fcntl
    except ImportError:
        return None
    fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("已有实例在运行，本次退出。")
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


# --------------------------------------------------------------------------
# 主逻辑
# --------------------------------------------------------------------------
def fmt(a):
    lines = ["【%s】" % a["title"]]
    if a.get("credit_total") is not None:
        detail = ", ".join("%s 学分 / %s 人" % (c.get("credit"), c.get("number"))
                           for c in a["credit"] if isinstance(c, dict))
        lines.append("  学分：%s" % (detail or a["credit_total"]))
    lines.append("  时间：%s ~ %s" % (a.get("start_local"), a.get("end_local") or "?"))
    lines.append("  地点：%s" % (a.get("address") or "?"))
    lines.append("  名额：%s    级别：%s" % (a.get("quota"), a.get("activity_type_label")))
    lines.append("  主办：%s" % (a.get("creator_college") or a.get("dept_label") or "?"))
    if a.get("credit_type_name"):
        lines.append("  类别：%s" % a["credit_type_name"])
    lines.append("  活动ID：%s" % a.get("id"))
    return "\n".join(lines)


def wanted(a):
    if CONFIG["only_ranges"] and a.get("activity_type_code") not in CONFIG["only_ranges"]:
        return False
    if CONFIG["keywords"]:
        return any(k in (a.get("title") or "") for k in CONFIG["keywords"])
    return True


def check_once(client, state, announce_all=False, quiet=False):
    snap = client.snapshot()
    open_list = [a for a in snap["open"] if wanted(a)]
    seen = state.setdefault("seen", {})

    new = [a for a in open_list if a["id"] not in seen]
    for a in open_list:
        if a["id"] not in seen:
            seen[a["id"]] = {"title": a["title"],
                             "first_seen": datetime.now(CST).isoformat()}
    state["last_check"] = datetime.now(CST).isoformat()
    state["open_count"] = len(open_list)

    # 按需写盘：有新增就写；否则每 8 轮写一次心跳，尽量少碰磁盘 I/O
    state["_checks"] = state.get("_checks", 0) + 1
    if new or state["_checks"] % 8 == 0:
        save_state(state)
        state["_checks"] = 0

    if quiet:                       # --seed：只登记，不推送
        print("[seed] 已登记 %d 场活动（当前开放 %d 场，已结束 %d 场）"
              % (len(open_list), len(open_list), len(snap["ended"])))
        return new

    if announce_all:
        url = CONFIG.get("landing_url") or None
        for a in open_list:
            notify("第二课堂活动（当前）", fmt(a), url=url)
        return new

    if new:
        url = CONFIG.get("landing_url") or None
        if len(new) == 1:
            notify("第二课堂：有新活动！", fmt(new[0]), url=url)
        else:
            notify("第二课堂：新增 %d 个活动！" % len(new),
                   "\n\n".join(fmt(a) for a in new), url=url)
    else:
        print("[%s] 无新活动（当前开放 %d 场，已结束 %d 场）"
              % (datetime.now(CST).strftime("%m-%d %H:%M"),
                 len(open_list), len(snap["ended"])))
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="把当前活动记为已知，不通知")
    ap.add_argument("--once", action="store_true", help="只跑一次")
    ap.add_argument("--all", action="store_true", help="打印当前全部活动")
    ap.add_argument("--test", action="store_true", help="只发一条测试通知，验证推送通道")
    ap.add_argument("--interval", type=int, default=CONFIG["interval"])
    args = ap.parse_args()

    CONFIG["interval"] = args.interval

    if args.test:                      # 推送自检：不需要 cookie
        chans = [k for k in ("wxpusher_spt", "wxpusher_app_token", "ntfy_url",
                             "wechat_webhook", "serverchan_key", "bark_url")
                 if CONFIG.get(k)]
        if not chans:
            print("没有配置任何推送通道，去 2ke_watch_config.json 里填一个。")
            return
        print("将要使用的通道：%s" % ", ".join(chans))
        notify("第二课堂监控 · 测试推送",
               "如果你看到这条消息，说明推送通道已经打通。\n"
               "时间：%s" % datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
               url=CONFIG.get("landing_url") or None)
        return

    if not os.path.exists(COOKIE_FILE):
        sys.exit("缺少 %s，请先运行: python jmu_2ke_api.py --refresh-cookie" % COOKIE_FILE)

    client = Client.from_cookie_file()
    exp = client.session_expiry()
    print("会话到期时间：%s" % exp)

    state = load_state()
    if args.seed:
        check_once(client, state, quiet=True)
        print("已把当前 %d 场活动记为已知。" % state.get("open_count", 0))
        return
    if args.once or args.all:
        check_once(client, state, announce_all=args.all)
        return

    print("开始监控，每 %d 秒检查一次（Ctrl+C 退出）" % CONFIG["interval"])
    _lock = acquire_single_instance()
    fail = 0
    sess_alerted = False
    while True:
        try:
            check_once(client, state)
            fail = 0
            sess_alerted = False
            delay = CONFIG["interval"] + random.randint(0, CONFIG["jitter"])
        except SessionExpired as e:
            if not sess_alerted:
                notify("第二课堂监控暂停：登录已失效",
                       "Cookie 过期，已停止取数。重新登录后更新服务器上的 "
                       "2ke_cookie.json 即可恢复。\n\n%r" % e)
                sess_alerted = True
            print("会话失效：%r" % e)
            delay = 1800                       # 半小时后再试，别反复打站点
        except Exception as e:
            fail += 1
            print("检查失败（第 %d 次）：%r" % (fail, e))
            if fail in (5, 20):
                notify("第二课堂监控异常", "已连续失败 %d 次：%r" % (fail, e))
            delay = min(CONFIG["interval"] * min(fail, 6), 3600)   # 指数退避，上限 1 小时
        time.sleep(delay)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止。")
