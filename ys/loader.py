# -*- coding: utf-8 -*-
from base.spider import Spider
import json as _j

_q = ["a974149b", "963d21dd", "a4164bcd", "aebd5d8ce362dcb1", "fc434aad", "d1d378a2", "4b4b288c", "ac9c8a6d", "a81b5ebe24d9556d", "d3b56c4af64119e6", "f7d43198"]
_w = [76, 146, 205, 255, 154, 233, 13, 118, 20, 48, 105]
_m = [4, 7, 1, -1, 0, 5, 3, 2, -1, -1, 6]
_f = [0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0]
_v = ".py"


def _g():
    """Return the built-in AES key used by the original loader config."""
    r = [None] * 8
    for a, b, c, d in zip(_q, _w, _m, _f):
        if c < 0:
            continue
        if d:
            r[c] = bytes((int(a[i:i + 2], 16) - b) & 0xFF for i in range(0, len(a), 2))
        else:
            r[c] = bytes(int(a[i:i + 2], 16) ^ b for i in range(0, len(a), 2))
    return b"".join(r)


def _h():
    s = 0
    for a, b, c, d in zip(_q, _w, _m, _f):
        if c >= 0:
            continue
        if d:
            s = (s + sum((int(a[i:i + 2], 16) - b) & 0xFF for i in range(0, len(a), 2))) & 0xFFFF
        else:
            s = (s + sum(int(a[i:i + 2], 16) ^ b for i in range(0, len(a), 2))) & 0xFFFF
    return s


def _key_bytes(value, key_format="hex"):
    """Parse an AES key supplied in sites[].ext; defaults to raw hex bytes."""
    if isinstance(value, bytes):
        key = value
    else:
        text = str(value or "").strip()
        mode = str(key_format or "hex").strip().lower()
        if mode in ("hex", "hexadecimal"):
            text = "".join(text.split())
            if len(text) not in (32, 48, 64) or any(ch not in "0123456789abcdefABCDEF" for ch in text):
                raise ValueError("AES hex key must be 32, 48, or 64 hexadecimal characters")
            key = bytes.fromhex(text)
        elif mode in ("text", "utf8", "utf-8"):
            key = text.encode("utf-8")
        else:
            raise ValueError("key_format must be 'hex' or 'text'")
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16, 24, or 32 bytes")
    return key


class Spider(Spider):
    def init(self, extend=""):
        if isinstance(extend, dict):
            c = extend
        elif extend:
            c = _j.loads(extend)
        else:
            c = {}
        if not isinstance(c, dict):
            raise ValueError("loader ext must be a JSON object")
        self._site = str(c.get("site", "")).strip().strip("/")
        self._base = str(c.get("base", "")).rstrip("/")
        self._name = str(c.get("name", ""))
        # If omitted, remain backward compatible with existing encrypted sites.
        self._key = _key_bytes(c.get("key", _g()), c.get("key_format", "hex"))
        self._tag = _h()
        self._real = None

    def _load(self):
        if self._real is not None:
            return self._real
        if not self._base or not self._site:
            raise ValueError("loader ext requires 'base' and 'site'")
        import base64
        import requests
        from Crypto.Cipher import AES

        s = requests.Session()
        s.headers.update({"User-Agent": "okhttp/3.12.0"})
        r = s.get(self._base + "/" + self._site + _v, timeout=20)
        r.raise_for_status()
        d = base64.b64decode(r.content.strip(), validate=True)
        if len(d) < 32 or (len(d) - 16) % AES.block_size:
            raise ValueError("encrypted module has invalid IV/ciphertext length")
        iv, ct = d[:16], d[16:]
        p = AES.new(self._key, AES.MODE_CBC, iv).decrypt(ct)
        pad = p[-1]
        if pad < 1 or pad > AES.block_size or p[-pad:] != bytes([pad]) * pad:
            raise ValueError("module decryption failed: wrong key or invalid PKCS#7 padding")
        code = p[:-pad].decode("utf-8")
        # Encrypted Python is executable code. Only load modules from a trusted source.
        ns = {}
        exec(compile(code, "<s>", "exec"), ns)
        real = ns["Spider"]()
        real.init("")
        self._real = real
        return real

    def getName(self):
        return self._name or self._load().getName()

    def destroy(self):
        if self._real is not None:
            try:
                self._real.destroy()
            except Exception:
                pass

    def homeContent(self, filter):
        return self._load().homeContent(filter)

    def homeVideoContent(self):
        return self._load().homeVideoContent()

    def categoryContent(self, tid, pg, filter, extend):
        return self._load().categoryContent(tid, pg, filter, extend)

    def detailContent(self, ids):
        return self._load().detailContent(ids)

    def searchContent(self, key, quick, pg="1"):
        return self._load().searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        return self._load().playerContent(flag, id, vipFlags)

    def isVideoFormat(self, url):
        try:
            return self._load().isVideoFormat(url)
        except Exception:
            return False

    def manualVideoCheck(self):
        try:
            return self._load().manualVideoCheck()
        except Exception:
            return False

    def localProxy(self, param):
        try:
            return self._load().localProxy(param)
        except Exception:
            return None
