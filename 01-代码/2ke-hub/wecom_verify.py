#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信回调验证服务
====================
极轻量：单文件、无 web 框架、只依赖 cryptography（系统已装）。
内存占用 ~25MB，纯事件驱动，不做任何轮询。

用途：
  1. GET  /wecom/callback  企业微信「设置接收消息服务器URL」的验证握手
  2. POST /wecom/callback  接收企业微信推送的消息/事件（记录后返回 success）

配置：/opt/2ke-hub/wecom.json
"""
import base64
import hashlib
import json
import os
import struct
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "wecom.json")
LOG = os.path.join(HERE, "wecom_received.log")
PORT = int(os.environ.get("WECOM_PORT", "18090"))

MAX_BODY = 64 * 1024          # 单次回调最大 64KB，超出直接拒绝
LOG_MAX = 2 * 1024 * 1024     # 日志超过 2MB 轮转一次


def load_conf():
    with open(CONF, encoding="utf-8") as f:
        return json.load(f)


def pkcs7_unpad(data):
    if not data:
        return data
    pad = data[-1]
    if pad < 1 or pad > 32 or pad > len(data):
        return data
    return data[:-pad]


class WeComCrypto:
    """企业微信消息加解密（WXBizMsgCrypt 的 AES 部分）"""

    def __init__(self, token, aes_key, corp_id):
        self.token = token
        self.corp_id = corp_id
        key = base64.b64decode(aes_key + "=")
        if len(key) != 32:
            raise ValueError("EncodingAESKey 解码后不是 32 字节，实际 %d" % len(key))
        self.key = key
        self.iv = key[:16]

    def signature(self, timestamp, nonce, encrypt):
        items = sorted([self.token, str(timestamp), str(nonce), encrypt])
        return hashlib.sha1("".join(items).encode("utf-8")).hexdigest()

    def decrypt(self, b64_msg):
        raw = base64.b64decode(b64_msg)
        if len(raw) % 16:
            raise ValueError("密文长度不是 16 的倍数：%d" % len(raw))
        dec = Cipher(algorithms.AES(self.key), modes.CBC(self.iv)).decryptor()
        plain = pkcs7_unpad(dec.update(raw) + dec.finalize())
        if len(plain) < 20:
            raise ValueError("明文太短：%d" % len(plain))
        msg_len = struct.unpack("!I", plain[16:20])[0]
        msg = plain[20:20 + msg_len]
        from_corp = plain[20 + msg_len:]
        return msg.decode("utf-8", "replace"), from_corp.decode("utf-8", "replace")

    def encrypt(self, text, random16=None):
        """仅用于自测：把明文加密成 echostr 格式"""
        rnd = random16 or os.urandom(16)
        body = text.encode("utf-8")
        full = rnd + struct.pack("!I", len(body)) + body + self.corp_id.encode("utf-8")
        pad = 32 - (len(full) % 32)
        full += bytes([pad]) * pad
        enc = Cipher(algorithms.AES(self.key), modes.CBC(self.iv)).encryptor()
        return base64.b64encode(enc.update(full) + enc.finalize()).decode()


class Handler(BaseHTTPRequestHandler):
    server_version = "2ke-wecom/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stdout.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))
        sys.stdout.flush()

    def _reply(self, code, body, ctype="text/plain; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if not u.path.rstrip("/").endswith("/wecom/callback"):
            return self._reply(404, "not found")
        q = parse_qs(u.query)
        sig = (q.get("msg_signature") or [""])[0]
        ts = (q.get("timestamp") or [""])[0]
        nonce = (q.get("nonce") or [""])[0]
        echostr = (q.get("echostr") or [""])[0]

        print("[GET] sig=%s ts=%s nonce=%s echostr=%s..."
              % (sig[:12], ts, nonce, echostr[:24]), flush=True)

        if not echostr:
            return self._reply(400, "missing echostr")

        try:
            conf = load_conf()
            wx = WeComCrypto(conf["token"], conf["aes_key"], conf["corp_id"])
            expect = wx.signature(ts, nonce, echostr)
            if expect != sig:
                print("  !! 签名不匹配  expect=%s got=%s" % (expect, sig), flush=True)
                return self._reply(403, "signature mismatch")
            msg, from_corp = wx.decrypt(echostr)
            print("  OK 解密成功 msg=%r corp=%r" % (msg[:40], from_corp), flush=True)
            return self._reply(200, msg)
        except Exception as e:
            print("  !! 异常 %r" % (e,), flush=True)
            return self._reply(500, "error: %s" % e)

    def do_POST(self):
        u = urlparse(self.path)
        if not u.path.rstrip("/").endswith("/wecom/callback"):
            return self._reply(404, "not found")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if n < 0:
            n = 0
        # 这个端点不做签名校验（企业微信不需要回执），任何人都能 POST。
        # 不限制长度的话，一个超大 Content-Length 就能占满内存。
        if n > MAX_BODY:
            print("[POST] 拒绝：Content-Length=%d 超过 %d" % (n, MAX_BODY), flush=True)
            return self._reply(413, "payload too large")
        try:
            body = self.rfile.read(n).decode("utf-8", "replace")
        except Exception:
            body = ""

        rec = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "path": self.path,
               "body_head": body[:2000]}
        try:
            # 日志轮转：超过 2MB 就换一个文件，避免被无限灌满磁盘
            if os.path.exists(LOG) and os.path.getsize(LOG) > LOG_MAX:
                try:
                    os.replace(LOG, LOG + ".1")
                except Exception:
                    pass
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        print("[POST] %s bytes，已记录" % len(body), flush=True)
        return self._reply(200, "success")


if __name__ == "__main__":
    print("企业微信回调服务启动 127.0.0.1:%d" % PORT, flush=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
