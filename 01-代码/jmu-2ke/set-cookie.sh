#!/bin/bash
# 第二课堂（2ke.jmu.edu.cn）Cookie 续期脚本  —— 2026-10-23 重写
#
# 为什么重写（审计 A · P0）：
#   旧版只写 __Secure-authjs.session-token 一个 cookie，用 printf 整体覆盖文件，
#   把 __access_token 一起删掉。而 2ke 的认证是双层的
#   （.jmu.edu.cn 的 __access_token = CAS 层 + 2ke.jmu.edu.cn 的
#   __Secure-authjs.session-token = 应用层），缺任何一个都会 302 到统一身份认证。
#   也就是说：按旧文档续期 = 采集永久停摆，而且现场看起来像"cookie 填错了"。
#
# 本版行为：
#   · 输入可以是「整行 Cookie 头」（推荐）或浏览器插件导出的 JSON，或存成文件传路径；
#   · 与现有文件**合并**：只更新你粘进来的同名 cookie，其余（含 __access_token）保留；
#   · 写前断言 __access_token 与 __Secure-authjs.session-token 都在、值够长、
#     且不是同一个值，否则 exit 1 并且**不动**原文件；
#   · 原子写（.tmp + mv）、权限 600、保留原属主，旧文件备份到 /root/；
#   · 写完 restart 采集器并回显采集日志，失败有明确提示。
#
# 用法：
#   /opt/jmu-2ke/set-cookie.sh '<整行 Cookie>'
#   /opt/jmu-2ke/set-cookie.sh '<JSON>'
#   /opt/jmu-2ke/set-cookie.sh /root/cookie.txt
#   /opt/jmu-2ke/set-cookie.sh --dry-run '<上面任意一种>'   # 只解析校验，不写不重启
set -u
umask 077

COOKIE_FILE="${COOKIE_FILE:-/opt/jmu-2ke/2ke_cookie.json}"
SVC="2ke-hub-mysql"
TS=$(date +%Y%m%d-%H%M%S)
DRY=0

usage() {
cat <<'EOF'
用法：
  set-cookie.sh '<整行 Cookie 头>'     # 推荐
  set-cookie.sh '<JSON>'               # 浏览器插件导出的完整 JSON
  set-cookie.sh /path/to/file          # 或把上面内容存文件传路径
  set-cookie.sh --dry-run '<...>'      # 只解析+校验，不写文件、不重启

取整行 Cookie 的地方：
  浏览器 F12 → Network → 刷新 https://2ke.jmu.edu.cn/dashboard
  → 点任意一条 2ke.jmu.edu.cn 的请求 → Request Headers → Cookie → 整行复制。
  这一行里必须能看到 __access_token 和 __Secure-authjs.session-token。

本脚本会与现有 cookie 文件合并（不覆盖），缺关键 cookie 时拒绝写入。
EOF
}

if [ $# -lt 1 ]; then usage; exit 1; fi
if [ "$1" = "--dry-run" ]; then DRY=1; shift; fi
if [ $# -lt 1 ]; then usage; exit 1; fi
INPUT="$*"
if [ -f "$INPUT" ]; then
    INPUT="$(cat "$INPUT")"
fi
if [ -z "${INPUT// /}" ]; then
    echo "!! 输入为空"; usage; exit 1
fi
command -v python3 >/dev/null 2>&1 || { echo "!! 找不到 python3"; exit 1; }

# ------------------------------------------------------------------ 解析 + 合并 + 校验
MERGED_JSON=$(INPUT="$INPUT" COOKIE_FILE="$COOKIE_FILE" python3 - <<'PY'
import datetime
import json
import os
import sys

raw  = os.environ.get("INPUT", "")
path = os.environ.get("COOKIE_FILE", "/opt/jmu-2ke/2ke_cookie.json")
KEY  = ("__access_token", "__Secure-authjs.session-token")


def die(msg):
    sys.stderr.write("!! %s\n" % msg)
    raise SystemExit(1)


def parse_json(txt):
    d = json.loads(txt)
    if isinstance(d, dict) and isinstance(d.get("cookies"), list):
        items = d["cookies"]
    elif isinstance(d, list):
        items = d
    elif isinstance(d, dict):
        items = [{"name": k, "value": v} for k, v in d.items()]
    else:
        die("JSON 结构不认识（既不是 {cookies:[...]} 也不是数组）")
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        n = it.get("name") or it.get("Name")
        v = it.get("value")
        if v is None:
            v = it.get("Value")
        if not n or v is None:
            continue
        out.append({
            "name": str(n), "value": str(v),
            "domain": it.get("domain") or it.get("Domain") or "",
            "path": it.get("path") or it.get("Path") or "/",
        })
    return out


def parse_header(txt):
    t = txt.strip()
    if t.lower().startswith("cookie:"):
        t = t.split(":", 1)[1]
    out = []
    for part in t.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        n, v = part.split("=", 1)
        n, v = n.strip(), v.strip().strip('"')
        if not n:
            continue
        out.append({"name": n, "value": v, "domain": "", "path": "/"})
    return out


try:
    items = parse_json(raw) if raw.lstrip()[:1] in ("{", "[") else parse_header(raw)
except SystemExit:
    raise
except Exception as e:
    die("解析失败：%r" % (e,))
if not items:
    die("没解析出任何 cookie（格式不对？整行 Cookie 头应形如 k1=v1; k2=v2; ...）")

# ---- 读旧文件（读不动就按空处理，但下面仍然会卡关键 cookie 断言）
old = []
if os.path.exists(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        old = (d.get("cookies") if isinstance(d, dict) else d) or []
    except Exception as e:
        sys.stderr.write("  !! 旧 cookie 文件读不动（%r），按空处理\n" % (e,))
        old = []

merged = {}
for c in old:
    if isinstance(c, dict) and c.get("name"):
        merged[c["name"]] = {
            "name": c["name"], "value": c.get("value", ""),
            "domain": c.get("domain") or "2ke.jmu.edu.cn",
            "path": c.get("path") or "/",
        }


def default_domain(n):
    if n in ("SESSION", "TGC", "CASTGC"):
        return "cas.paas.jmu.edu.cn"
    if n == "__access_token":
        return ".jmu.edu.cn"
    return "2ke.jmu.edu.cn"


changed, added = [], []
for it in items:
    n = it["name"]
    if n in merged:
        cur = dict(merged[n])
        if cur.get("value") != it["value"]:
            changed.append(n)
        cur["value"] = it["value"]
        if it.get("domain"):
            cur["domain"] = it["domain"]
        if it.get("path"):
            cur["path"] = it["path"]
        merged[n] = cur
    else:
        merged[n] = {"name": n, "value": it["value"],
                     "domain": it.get("domain") or default_domain(n),
                     "path": it.get("path") or "/"}
        added.append(n)

# ---- 关键断言：缺一个就不许写（否则写出来 100% 失效）
missing = [k for k in KEY if k not in merged]
if missing:
    die("合并后仍缺少 %s —— 拒绝写入，原文件保持不动。\n"
        "   取值方法：F12 → Network → 2ke.jmu.edu.cn 的请求 → Request Headers → "
        "Cookie 整行复制（必须能看到这两个名字）。\n"
        "   只粘 __Secure-authjs.session-token 一个值是**不够**的："
        "没有 __access_token 会立刻 302 到统一身份认证。"
        % ", ".join(missing))

for k in KEY:
    v = merged[k].get("value") or ""
    if len(v) < 50:
        die("%s 的值只有 %d 字节，看着不像完整 cookie —— 拒绝写入。" % (k, len(v)))
if merged[KEY[0]]["value"] == merged[KEY[1]]["value"]:
    die("两个关键 cookie 的值完全相同，几乎肯定是粘错了 —— 拒绝写入。")

sys.stderr.write("解析到 %d 个 cookie：更新 %d 个%s，新增 %d 个，合并后共 %d 个\n" % (
    len(items), len(changed),
    ("（%s）" % ",".join(changed[:6]) if changed else ""),
    len(added), len(merged)))
sys.stderr.write("关键 cookie：%s\n" % "、".join(
    "%s(%d 字节)" % (k, len(merged[k]["value"])) for k in KEY))

cst = datetime.timezone(datetime.timedelta(hours=8))
json.dump({"cookies": list(merged.values()),
           "saved_at": datetime.datetime.now(cst).isoformat()},
          sys.stdout, ensure_ascii=False, indent=2)
PY
) || { echo "!! 未写入任何内容"; exit 1; }

if [ "$DRY" = "1" ]; then
    echo "--dry-run：以上校验通过；未写文件、未重启 $SVC"
    exit 0
fi

# ------------------------------------------------------------------ 备份 + 原子写入
if [ -f "$COOKIE_FILE" ]; then
    BK="/root/2ke_cookie.json.bak-$TS"
    cp -a "$COOKIE_FILE" "$BK" || { echo "!! 备份失败，中止"; exit 1; }
    echo "旧 cookie 已备份：$BK"
fi

TMP="$COOKIE_FILE.tmp.$TS"
printf '%s\n' "$MERGED_JSON" > "$TMP" || { echo "!! 写临时文件失败"; rm -f "$TMP"; exit 1; }
chmod 600 "$TMP"
if id jmu2ke >/dev/null 2>&1; then chown jmu2ke:jmu2ke "$TMP" 2>/dev/null || true; fi

# 落盘前再自检一遍临时文件（防手抖/磁盘问题写出坏 JSON）
COOKIE_FILE="$TMP" python3 - <<'PY' || { echo "!! 临时文件自检失败，原文件未改动"; rm -f "$TMP"; exit 1; }
import json, os, sys
p = os.environ["COOKIE_FILE"]
d = json.load(open(p, encoding="utf-8"))
names = {c["name"] for c in d["cookies"]}
need = {"__access_token", "__Secure-authjs.session-token"}
if not need <= names:
    sys.stderr.write("!! 临时文件缺少 %s\n" % ",".join(sorted(need - names)))
    raise SystemExit(1)
print("临时文件自检通过：%d 个 cookie，关键 2 个都在，mode=%o"
      % (len(d["cookies"]), os.stat(p).st_mode & 0o777))
PY

mv -f "$TMP" "$COOKIE_FILE" || { echo "!! mv 失败"; rm -f "$TMP"; exit 1; }
chmod 600 "$COOKIE_FILE"
if id jmu2ke >/dev/null 2>&1; then chown jmu2ke:jmu2ke "$COOKIE_FILE" 2>/dev/null || true; fi
echo "cookie 已写入：$COOKIE_FILE（$(stat -c '%s 字节 %U:%G %a' "$COOKIE_FILE")）"

# ------------------------------------------------------------------ 重启 + 校验
echo "重启采集器 $SVC ..."
systemctl restart "$SVC"
sleep 12
ST=$(systemctl is-active "$SVC")
echo "采集器状态：$ST"
if [ "$ST" != "active" ]; then
    echo "!! 采集器没起来，看日志：journalctl -u $SVC -n 40 --no-pager"
    exit 1
fi
echo "最近采集日志："
journalctl -u "$SVC" -n 8 --no-pager -o cat | tail -6 | sed 's/^/  /'
if journalctl -u "$SVC" -n 8 --no-pager -o cat | grep -q "SESSION_EXPIRED"; then
    echo "!! 采集器报会话失效：cookie 大概还是不对（检查是否漏了 __access_token，"
    echo "   或者浏览器里那份已经过期）。回滚：cp -a /root/2ke_cookie.json.bak-$TS $COOKIE_FILE && systemctl restart $SVC"
    exit 1
fi
echo "完成。"
