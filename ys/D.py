import base64
import re

import requests
from Crypto.Cipher import AES

from base.spider import Spider as BaseSpider

DEFAULT_KEY_HEX = "66d9d037d7497e00362614f746462581e53858d7383a914b9ebd58f104ab8f4b"


class Spider(BaseSpider):
    def init(self, extend=""):
        raw = (extend or "").strip()
        config = {}
        if raw.startswith("{"):
            import json
            try:
                config = json.loads(raw)
            except (TypeError, ValueError) as error:
                raise ValueError("extend JSON 配置无效: " + str(error))
            if not isinstance(config, dict):
                raise ValueError("extend 必须是 JSON 对象")

        self.url = str(config.get("url") or "").strip()
        self.key = str(config.get("key") or (raw if raw and not config else DEFAULT_KEY_HEX)).strip()
        self.key_format = str(config.get("key_format") or config.get("keyFormat") or "auto").strip().lower()

        if self.key.startswith("hex:"):
            self.key = self.key[4:].strip()
            self.key_format = "hex"
        elif self.key.startswith("text:"):
            self.key = self.key[5:]
            self.key_format = "text"

    def getName(self):
        return "Decrypt"

    def liveContent(self, url=""):
        target = str(url or self.url or "").strip()
        if not target:
            raise ValueError("missing cipher url")
        text = self._read_text(target)
        return self._try_decrypt(text, True, self.key, self.key_format)

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                url = param.get("url") or param.get("u") or param.get("src") or self.url
                key = param.get("key") or param.get("ext") or self.key
                key_format = param.get("key_format") or param.get("keyFormat") or self.key_format
            elif isinstance(param, str):
                url, key, key_format = param, self.key, self.key_format
            else:
                url, key, key_format = self.url, self.key, self.key_format

            if not url:
                return [400, "text/plain; charset=utf-8", "decrypt: missing url"]
            if not key:
                return [400, "text/plain; charset=utf-8", "decrypt: missing key"]

            content = self._try_decrypt(self._read_text(url), True, key, key_format)
            return [200, "text/plain; charset=utf-8", content]
        except Exception as error:
            return [502, "text/plain; charset=utf-8", "decrypt: " + str(error)]

    @staticmethod
    def _read_text(url):
        if not url:
            raise ValueError("missing url")
        url = str(url).strip()
        if re.match(r"^https?://", url, re.IGNORECASE):
            response = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            return response.content.decode("utf-8-sig", errors="strict")
        return url

    @staticmethod
    def _key_bytes(key, key_format="auto"):
        key = str(key or "").strip()
        mode = str(key_format or "auto").strip().lower()
        if mode == "auto":
            mode = "hex" if re.fullmatch(r"(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{48}|[0-9a-fA-F]{64})", key) else "text"
        if mode in ("hex", "hexadecimal"):
            compact = re.sub(r"\s+", "", key)
            if not re.fullmatch(r"(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{48}|[0-9a-fA-F]{64})", compact):
                raise ValueError("hex key must contain 32, 48, or 64 hexadecimal characters")
            key_bytes = bytes.fromhex(compact)
        elif mode in ("text", "utf8", "utf-8"):
            key_bytes = key.encode("utf-8")
        else:
            raise ValueError("key_format must be 'hex', 'text', or 'auto'")

        if len(key_bytes) not in (16, 24, 32):
            raise ValueError("AES key must be 16, 24, or 32 bytes")
        return key_bytes

    @staticmethod
    def _try_decrypt(text, decrypt=True, key=None, key_format="auto"):
        original = str(text or "")
        if not decrypt or not key:
            return original

        compact = re.sub(r"\s+", "", original).strip()
        if not compact or not re.fullmatch(r"[A-Za-z0-9+/=_-]+", compact):
            return original

        normalized = compact.replace("-", "+").replace("_", "/")
        normalized = normalized.rstrip("=")
        if len(normalized) % 4 == 1:
            raise ValueError("invalid Base64 ciphertext length")
        normalized += "=" * ((4 - len(normalized) % 4) % 4)
        try:
            payload = base64.b64decode(normalized, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise ValueError("invalid Base64 ciphertext") from error

        if len(payload) < 32 or (len(payload) - 16) % AES.block_size:
            return original

        iv, ciphertext = payload[:16], payload[16:]
        cipher = AES.new(Spider._key_bytes(key, key_format), AES.MODE_CBC, iv)
        padded = cipher.decrypt(ciphertext)
        pad_len = padded[-1]
        if pad_len < 1 or pad_len > AES.block_size or padded[-pad_len:] != bytes([pad_len]) * pad_len:
            raise ValueError("解密失败：密钥错误或 PKCS#7 填充无效")
        try:
            return padded[:-pad_len].decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError("解密结果不是有效的 UTF-8 文本") from error
