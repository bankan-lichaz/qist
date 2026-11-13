import base64
import re
import requests

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def init(self, extend=""):
        # extend = ext 里的值，例如 "key1"
        self.key = (extend or "").strip()

    def getName(self):
        return "Decrypt"

    def liveContent(self, url):
        if not url:
            raise ValueError("missing cipher url")
        text = self._read_text(url)
        return self._try_decrypt(text, True, self.key)

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                query = dict(param)
                url = query.get("url") or query.get("u") or query.get("src")
                key = query.get("key") or query.get("ext") or self.key
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

            content = self._try_decrypt(self._read_text(url), True, key)
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
            return response.text
        return url

    @staticmethod
    def _try_decrypt(text, decrypt, key):
        # JS:
        # if (!decrypt || !key) return text;
        if not decrypt or not key:
            return text

        key = str(key).strip()
        compact = str(text or "").strip()

        # JS:
        # const base64Regex = /^[0-9A-Za-z+/]+={0,2}$/;
        # if (!compact || compact.length < 8 || compact.includes("\n") ||
        #     !base64Regex.test(compact) || compact.length % 4 !== 0) {
        #   return text;
        # }
        if (
            not compact
            or len(compact) < 8
            or "\n" in compact
            or not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", compact)
            or len(compact) % 4 != 0
        ):
            return text

        try:
            # JS:
            # const binary = atob(compact);
            # const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
            # let decoded = new TextDecoder().decode(bytes);
            try:
                binary = base64.b64decode(compact, validate=True)
            except Exception:
                # 兼容缺少 padding 的情况
                padded = compact + "=" * ((4 - len(compact) % 4) % 4)
                binary = base64.b64decode(padded, validate=False)

            try:
                decoded = binary.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                decoded = binary.decode("utf-8", errors="replace")

            # JS:
            # for (let i = 0; i < decoded.length; i++) {
            #   output += String.fromCharCode(
            #     decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length)
            #   );
            # }
            out = []
            for i, ch in enumerate(decoded):
                out.append(chr(ord(ch) ^ ord(key[i % len(key)])))
            return "".join(out)

        except Exception:
            # JS: catch (e) { return text; }
            return text
