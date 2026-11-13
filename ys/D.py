# -*- coding: utf-8 -*-
"""Decrypt an AES-CBC encrypted TXT/M3U list for OK影视."""

import base64
import json
import re

import requests
from Crypto.Cipher import AES

from base.spider import Spider as BaseSpider

# Exact 32-byte AES key derived from ys/loader.py's _g().
DEFAULT_KEY_HEX = "66d9d037d7657e00362614f704ab8f4be53858d7383a914b9ebd58f13e3e1b7f"


class Spider(BaseSpider):
    def init(self, extend=""):
        if isinstance(extend, dict):
            config = extend
        else:
            raw = str(extend or "").strip()
            try:
                config = json.loads(raw) if raw.startswith("{") else {}
            except (TypeError, ValueError) as error:
                raise ValueError("extend JSON 配置无效: " + str(error))
            if not isinstance(config, dict):
                raise ValueError("extend 必须是 JSON 对象")
            if raw and not config:
                config = {"key": raw}

        self.url = str(config.get("url") or "").strip()
        self.key = str(config.get("key") or DEFAULT_KEY_HEX).strip()
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
            raise ValueError("missing encrypted live-list URL")
        return self._try_decrypt(self._read_text(target), self.key, self.key_format)

    @staticmethod
    def _read_text(url):
        if not url:
            raise ValueError("missing URL")
        url = str(url).strip()
        if re.match(r"^https?://", url, re.IGNORECASE):
            response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
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
            result = bytes.fromhex(compact)
        elif mode in ("text", "utf8", "utf-8"):
            result = key.encode("utf-8")
        else:
            raise ValueError("key_format must be 'hex', 'text', or 'auto'")
        if len(result) not in (16, 24, 32):
            raise ValueError("AES key must be 16, 24, or 32 bytes")
        return result

    @staticmethod
    def _try_decrypt(text, key, key_format="auto"):
        original = str(text or "")
        compact = re.sub(r"\s+", "", original).strip()
        if not compact or not re.fullmatch(r"[A-Za-z0-9+/=_-]+", compact):
            raise ValueError("downloaded content is not a Base64 ciphertext; check the URL response")
        normalized = compact.replace("-", "+").replace("_", "/").rstrip("=")
        if len(normalized) % 4 == 1:
            raise ValueError("invalid Base64 ciphertext length")
        normalized += "=" * ((4 - len(normalized) % 4) % 4)
        try:
            payload = base64.b64decode(normalized, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise ValueError("invalid Base64 ciphertext") from error
        if len(payload) < 32 or (len(payload) - 16) % AES.block_size:
            raise ValueError("ciphertext must be Base64(16-byte IV + AES-CBC ciphertext)")
        iv, ciphertext = payload[:16], payload[16:]
        padded = AES.new(Spider._key_bytes(key, key_format), AES.MODE_CBC, iv).decrypt(ciphertext)
        padding = padded[-1]
        if padding < 1 or padding > AES.block_size or padded[-padding:] != bytes([padding]) * padding:
            raise ValueError("decryption failed: wrong key or invalid PKCS#7 padding")
        try:
            return padded[:-padding].decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError("decrypted content is not valid UTF-8") from error
