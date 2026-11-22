#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAS 自动登录（纯 HTTP）—— 拿到 TGC 后写 /opt/jwxt/tgc.txt

流程（实测可行，无需短信验证码）：
  1. GET  cas/login?service=<jwxt sso>     → 抓 execution / fpVisitorId / cookies
  2. GET  cas/jwt/publicKey                → RSA 公钥
  3. POST cas/mfa/detect                   → username + __RSA__<pwd> + fpVisitorId → mfaState
  4. POST cas/login?service=...            → 完整表单 → 302 + Set-Cookie: TGC

只依赖标准库 + cryptography（服务器已装）。
"""
import base64
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

CAS = "https://cas.paas.jmu.edu.cn"
SVC = "https://jwxt.jmu.edu.cn/student/sso/login"
AUTH_FILE = "/opt/jwxt/cas-auth.json"
TGC_FILE = "/opt/jwxt/tgc.txt"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def log(m):
    print("[cas] %s" % m, flush=True)


def rsa_encrypt(pubkey_b64: str, plain: str) -> str:
    """复现前端 JSEncrypt：公钥 base64(DER/X.509) → PKCS#1 v1.5 → base64"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    if "BEGIN PUBLIC KEY" in pubkey_b64:
        pem = pubkey_b64.strip() + "\n"
    else:
        pem = ("-----BEGIN PUBLIC KEY-----\n"
               + "\n".join(pubkey_b64[i:i + 64] for i in range(0, len(pubkey_b64), 64))
               + "\n-----END PUBLIC KEY-----\n")
    key = serialization.load_pem_public_key(pem.encode())
    ct = key.encrypt(plain.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(ct).decode()


def opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA), ("Accept-Language", "zh-CN,zh;q=0.9")]
    return op, cj


def main():
    if not os.path.exists(AUTH_FILE):
        log("没有 %s" % AUTH_FILE)
        return 2
    auth = json.load(open(AUTH_FILE, encoding="utf-8"))
    user, pwd = auth.get("username"), auth.get("password")
    if not user or not pwd:
        log("cas-auth.json 缺 username/password")
        return 2

    op, cj = opener()
    login_url = "%s/cas/login?service=%s" % (CAS, urllib.parse.quote(SVC, safe=""))

    # ---------- 1. 登录页 ----------
    try:
        with op.open(login_url, timeout=30) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        log("打开登录页失败 %r" % (e,))
        return 3

    def hidden(name):
        m = re.search(r'name=["\']%s["\'][^>]*value=["\']([^"\']*)' % name, html)
        if not m:
            m = re.search(r'value=["\']([^"\']*)["\'][^>]*name=["\']%s["\']' % name, html)
        return m.group(1) if m else ""

    execution = hidden("execution")
    fp = hidden("fpVisitorId") or auth.get("fpVisitorId") or "d3ff404f4f04674af813874b49a2bf1e"
    if not execution:
        log("没抓到 execution（页面结构可能变了）")
        return 3
    log("execution=%s  fpVisitorId=%s" % (execution, fp or "(空)"))

    # ---------- 2. 公钥 ----------
    try:
        with op.open(CAS + "/cas/jwt/publicKey", timeout=20) as r:
            pub = r.read().decode("utf-8", "ignore").strip().strip('"')
    except Exception as e:
        log("取公钥失败 %r" % (e,))
        return 3
    log("公钥 %d 字符" % len(pub))

    # ---------- 3. 加密 ----------
    try:
        enc_pwd = "__RSA__" + rsa_encrypt(pub, pwd)
    except Exception as e:
        log("RSA 加密失败 %r" % (e,))
        return 3
    log("密码已加密（%d 字符）" % len(enc_pwd))

    # ---------- 4. mfa/detect ----------
    body = urllib.parse.urlencode({
        "username": user, "password": enc_pwd, "fpVisitorId": fp,
    }).encode()
    req = urllib.request.Request(CAS + "/cas/mfa/detect", data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest", "Referer": login_url,
    })
    try:
        with op.open(req, timeout=30) as r:
            det = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        log("mfa/detect HTTP %s" % e.code)
        return 3
    log("mfa/detect → %s" % det[:160])

    # mfaState 藏在响应里（可能是 json 字段，也可能是纯文本）
    mfa_state = ""
    try:
        j = json.loads(det)
        for k in ("mfaState", "state", "token"):
            if j.get(k):
                mfa_state = str(j[k])
                break
        if not mfa_state and isinstance(j.get("data"), dict):
            mfa_state = str(j["data"].get("mfaState") or j["data"].get("state") or "")
    except Exception:
        m = re.search(r"[A-Za-z0-9]{6}", det)
        mfa_state = m.group(0) if m else ""

    # ---------- 5. 正式登录 ----------
    form = {
        "username": user,
        "password": enc_pwd,
        "captcha": "",
        "currentMenu": "1",
        "failN": "-1",
        "mfaState": mfa_state,
        "execution": execution,
        "_eventId": "submit",
        "geolocation": "",
        "fpVisitorId": fp,
        "trustAgent": "",
        "submit1": "Login1",
    }
    body2 = urllib.parse.urlencode(form).encode()
    req2 = urllib.request.Request(login_url, data=body2, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": login_url, "Origin": CAS,
    })

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    op2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), NoRedirect)
    op2.addheaders = [("User-Agent", UA)]
    try:
        with op2.open(req2, timeout=30) as r:
            loc = r.headers.get("Location", "")
            status = r.getcode()
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
        status = e.code

    log("登录响应 HTTP %s  Location=%s" % (status, loc[:110]))

    # ---------- 6. 取 TGC ----------
    tgc = None
    for c in cj:
        if c.name == "TGC":
            tgc = c.value
    if not tgc:
        # 有时 TGC 在 Set-Cookie 里但 jar 没接住
        log("cookie jar 里没有 TGC，登录可能失败")
        return 4

    log("拿到 TGC: %s…（%d 字符）" % (tgc[:26], len(tgc)))
    old = ""
    if os.path.exists(TGC_FILE):
        old = open(TGC_FILE, encoding="utf-8").read().strip()
    if old == tgc:
        log("TGC 与现有相同，无需更新")
    else:
        tmp = TGC_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(tgc)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, TGC_FILE)
        log("TGC 已更新 → %s" % TGC_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
