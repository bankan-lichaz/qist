import base64
import re

import requests
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def init(self, extend=""):
        self.key = (extend or "").strip()

    def getName(self):
        return "Decrypt"

    def liveContent(self, url):
        if not url:
            raise ValueError("missing cipher url")
        cipher = self._read_text(url)
        return self._decrypt(cipher, self.key)

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                query = dict(param)
                url = query.get("url") or query.get("u") or query.get("src")
                key = (query.get("key") or query.get("ext") or self.key).strip()
            elif isinstance(param, str):
                url = param
                key = self.key
            else:
                url = None
                key = self.key
            if not url:
                return [400, "text/plain; charset=utf-8", "decrypt: missing url"]
            if not key:
                return [400, "text/plain; charset=utf-8", "decrypt: missing key"]
            content = self._decrypt(self._read_text(url), key)
            return [200, "text/plain; charset=utf-8", content]
        except Exception as error:
            return [502, "text/plain; charset=utf-8", "decrypt: " + str(error)]

    @staticmethod
    def _read_text(url):
        if not url:
            raise ValueError("missing url")
        if re.match(r"^https?://", str(url), re.IGNORECASE):
            response = requests.get(
                str(url),
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            return response.text
        return str(url)

    @staticmethod
    def _xor_bytes(data, key):
        if not key:
            raise ValueError("missing key")
        key_bytes = key.encode("utf-8")
        if not key_bytes:
            raise ValueError("invalid key")
        return bytes(byte ^ key_bytes[index % len(key_bytes)] for index, byte in enumerate(data))

    def _decrypt(self, cipher, key):
        key = (key or self.key).strip()
        if not key:
            raise ValueError("missing key")
        value = str(cipher or "").strip()
        if not value:
            raise ValueError("missing cipher")
        try:
            decoded = base64.b64decode(value, validate=True)
        except Exception:
            padded = value + "=" * ((4 - len(value) % 4) % 4)
            decoded = base64.b64decode(padded, validate=False)
        plain = self._xor_bytes(decoded, key)
        try:
            return plain.decode("utf-8")
        except UnicodeDecodeError:
            return plain.decode("utf-8", errors="replace")


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print("usage: decrypt.py <cipher-url> <key>")
        sys.exit(1)
    spider = Spider()
    spider.init(sys.argv[2])
    print(spider.liveContent(sys.argv[1]))
