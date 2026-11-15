import base64
import json
import re
import time
from urllib.parse import urlparse

import requests
from base.spider import Spider as BaseSpider


def _safe_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        for enc in ("utf-8-sig", "gbk", "latin1"):
            try:
                return value.decode(enc)
            except Exception:
                pass
        return value.decode("utf-8", "ignore")
    return str(value)


def _strip_comments(text):
    lines = []
    for line in str(text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines)


def _looks_like_base64(text):
    s = "".join(ch for ch in text if ch not in "\r\n\t ")
    if not s:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=]+", s)) and len(s) % 4 == 0


def _xor_decode_charwise(text, key):
    if not key:
        raise ValueError("missing key")
    key_chars = list(key)
    out = []
    for i, ch in enumerate(text):
        out.append(chr(ord(ch) ^ ord(key_chars[i % len(key_chars)])))
    return "".join(out)


def _decrypt_cipher(cipher_text, key):
    if not key:
        return cipher_text

    cleaned = _strip_comments(cipher_text).strip()
    if not cleaned:
        return ""

    compact = "".join(ch for ch in cleaned if ch not in "\r\n\t ")
    if _looks_like_base64(compact):
        try:
            decoded = base64.b64decode(compact, validate=False)
            plain = ""
            for ch in decoded.decode("latin1", errors="ignore"):
                plain += chr(ord(ch) ^ ord(key[len(plain) % len(key)]))
            return plain
        except Exception:
            pass

    # 兼容：先把文本按 Base64 取出，再做 char-wise XOR
    try:
        raw = base64.b64decode(cleaned, validate=False)
        text = raw.decode("latin1", errors="ignore")
        return _xor_decode_charwise(text, key)
    except Exception:
        pass

    return cleaned


def _regex_from_expr(expr):
    expr = (expr or "").strip()
    if not expr:
        return None
    m = re.match(r"^/(.*?)/([a-zA-Z]*)$", expr)
    if not m:
        return None
    pattern = m.group(1)
    flags = m.group(2)
    fl = 0
    if "i" in flags:
        fl |= re.IGNORECASE
    return re.compile(pattern, fl)


def _regex_or(lines, expr):
    if not expr:
        return lines
    pats = []
    for item in str(expr).split(";"):
        item = item.strip()
        if not item:
            continue
        pat = _regex_from_expr(item)
        if pat:
            pats.append(pat)
    if not pats:
        return lines
    result = []
    for line in lines:
        if any(p.search(line) for p in pats):
            result.append(line)
    return result


def _regex_replace(lines, expr):
    if not expr:
        return lines
    result = list(lines)
    for item in str(expr).split(";"):
        item = item.strip()
        if not item:
            continue
        m = re.match(r"^/(.*?)/(.+?)/$", item)
        if not m:
            continue
        pattern = re.compile(m.group(1))
        replacement = m.group(2)
        result = [pattern.sub(replacement, line) for line in result]
    return result


def _cut_lines(lines, expr):
    if not expr:
        return lines
    result = []
    exprs = [s.strip() for s in str(expr).split(";") if s.strip()]
    for seg in exprs:
        m = re.match(r"^/(.*?)/(.+?)/$", seg)
        if not m:
            continue
        start_re = re.compile(m.group(1))
        end_re = re.compile(m.group(2))
        start_index = None
        end_index = None
        for idx, line in enumerate(lines):
            if start_index is None and start_re.search(line):
                start_index = idx
            if start_index is not None and end_index is None and end_re.search(line):
                end_index = idx
                break
        if start_index is not None and end_index is not None and end_index >= start_index:
            result.extend(lines[start_index : end_index + 1])
    return result if result else []


def _m3u_to_txt(text):
    text = (text or "").replace("\r", "").strip()
    if not text:
        return []
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    groups = {}
    last_group = "未分组"
    last_name = None
    for line in lines:
        if line.startswith("#EXTINF"):
            group_match = re.search(r'group-title="([^"]+)"', line, re.I)
            name_match = re.search(r",(.*)$", line)
            last_group = group_match.group(1).strip() if group_match else "未分组"
            last_name = name_match.group(1).strip() if name_match else "未知频道"
            if last_group not in groups:
                groups[last_group] = []
        elif re.match(r"^https?://", line, re.I):
            if last_name:
                groups.setdefault(last_group, []).append(f"{last_name},{line}")
                last_name = None
    out = []
    for group, items in groups.items():
        out.append(f"{group},#genre#")
        for item in items:
            out.append(item)
        out.append("")
    return out


def _split_top_level_commas(raw):
    # 兼容 work.js 的 merge 语法：
    # "url1|key=xx,url2|key=yy"
    # 这里用一个非常保守的分割：只按逗号切，适合 TVBox 的多源字符串
    # 如果正则里出现逗号，通常不会作为分隔源
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def _parse_source_spec(spec):
    # 例如：
    # "url1|decrypt=1|key=key1|multiurl|normalize"
    # "url2|decrypt=1|key=key2|cut=/央视/ys/|include=bbc"
    text = str(spec or "").strip()
    if not text:
        return {"url": "", "params": {}}
    if "|" in text:
        url, rest = text.split("|", 1)
        url = url.strip()
    else:
        url = text
        rest = ""
    params = {}
    if rest:
        for part in rest.split("|"):
            item = part.strip()
            if not item:
                continue
            if "=" in item:
                k, v = item.split("=", 1)
                k = k.strip().lower()
                v = v.strip()
                params[k] = v
            else:
                params[item.lower()] = "1"
    return {"url": url, "params": params}


def _normalize_channel_name(line):
    if "," not in line:
        return line
    name, tail = line.split(",", 1)
    clean = name.strip()
    # 直接按 work.js 那一套思路做一组核心归一化
    rules = [
        (re.compile(r"^CCTV[-\s]*少儿$", re.I), "CCTV14少儿"),
        (re.compile(r"^CCTV[-\s]*新闻$", re.I), "CCTV13新闻"),
        (re.compile(r"^CCTV[-\s]*NEWS$", re.I), "CCTV13新闻"),
        (re.compile(r"^CCTV[- ]?5\+.*$", re.I), "CCTV5+体育赛事"),
        (re.compile(r"^CCTV[- ]?4K.*$", re.I), "CCTV4K"),
        (re.compile(r"^CCTV[- ]?8K.*$", re.I), "CCTV8K"),
        (re.compile(r"^CCTV[- ]?10.*$", re.I), "CCTV10科教"),
        (re.compile(r"^CCTV[- ]?11.*$", re.I), "CCTV11戏曲"),
        (re.compile(r"^CCTV[- ]?12.*$", re.I), "CCTV12社会与法"),
        (re.compile(r"^CCTV[- ]?13.*$", re.I), "CCTV13新闻"),
        (re.compile(r"^CCTV[- ]?14.*$", re.I), "CCTV14少儿"),
        (re.compile(r"^CCTV[- ]?15.*$", re.I), "CCTV15音乐"),
        (re.compile(r"^CCTV[- ]?16.*$", re.I), "CCTV16奥林匹克"),
        (re.compile(r"^CCTV[- ]?17.*$", re.I), "CCTV17农业农村"),
        (re.compile(r"^CCTV[- ]?1(?![\dA-Za-z]).*$", re.I), "CCTV1综合"),
        (re.compile(r"^CCTV[- ]?2(?![\dA-Za-z]).*$", re.I), "CCTV2财经"),
        (re.compile(r"^CCTV[- ]?3(?![\dA-Za-z]).*$", re.I), "CCTV3综艺"),
        (re.compile(r"^CCTV[- ]?4(?![\dA-Za-z]).*$", re.I), "CCTV4中文国际"),
        (re.compile(r"^CCTV[- ]?5(?![\dA-Za-z]).*$", re.I), "CCTV5体育"),
        (re.compile(r"^CCTV[- ]?6(?![\dA-Za-z]).*$", re.I), "CCTV6电影"),
        (re.compile(r"^CCTV[- ]?7(?![\dA-Za-z]).*$", re.I), "CCTV7国防军事"),
        (re.compile(r"^CCTV[- ]?8(?![\dA-Za-z]).*$", re.I), "CCTV8电视剧"),
        (re.compile(r"^CCTV[- ]?9(?![\dA-Za-z]).*$", re.I), "CCTV9纪录"),
        (re.compile(r"北京卫视", re.I), "北京卫视"),
        (re.compile(r"东方卫视", re.I), "东方卫视"),
        (re.compile(r"湖南卫视", re.I), "湖南卫视"),
        (re.compile(r"浙江卫视", re.I), "浙江卫视"),
        (re.compile(r"江苏卫视", re.I), "江苏卫视"),
        (re.compile(r"广东卫视", re.I), "广东卫视"),
        (re.compile(r"山东卫视", re.I), "山东卫视"),
        (re.compile(r"深圳卫视", re.I), "深圳卫视"),
        (re.compile(r"安徽卫视", re.I), "安徽卫视"),
        (re.compile(r"四川卫视", re.I), "四川卫视"),
        (re.compile(r"重庆卫视", re.I), "重庆卫视"),
        (re.compile(r"天津卫视", re.I), "天津卫视"),
        (re.compile(r"湖北卫视", re.I), "湖北卫视"),
        (re.compile(r"河北卫视", re.I), "河北卫视"),
        (re.compile(r"河南卫视", re.I), "河南卫视"),
        (re.compile(r"海南卫视", re.I), "海南卫视"),
        (re.compile(r"山西卫视", re.I), "山西卫视"),
        (re.compile(r"江西卫视", re.I), "江西卫视"),
        (re.compile(r"广西卫视", re.I), "广西卫视"),
        (re.compile(r"陕西卫视", re.I), "陕西卫视"),
        (re.compile(r"吉林卫视", re.I), "吉林卫视"),
        (re.compile(r"黑龙江卫视", re.I), "黑龙江卫视"),
        (re.compile(r"辽宁卫视", re.I), "辽宁卫视"),
        (re.compile(r"青海卫视", re.I), "青海卫视"),
        (re.compile(r"宁夏卫视", re.I), "宁夏卫视"),
        (re.compile(r"甘肃卫视", re.I), "甘肃卫视"),
    ]
    for rule_re, normalized in rules:
        if rule_re.search(clean):
            clean = normalized
            break
    return f"{clean},{tail}"


def _fetch_url_text(url):
    if not url:
        raise ValueError("missing url")
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("invalid url")
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text


def _process_single(text, params):
    options = dict(params or {})

    if str(options.get("decrypt", "0")).strip() == "1":
        key = str(options.get("key") or "").strip()
        text = _decrypt_cipher(text, key)

    if str(options.get("m3u", "0")).strip() == "1" or "#EXTM3U" in str(text or "").upper() or "#EXTINF" in str(text or "").upper():
        converted = _m3u_to_txt(text)
        if converted:
            text = "\n".join(converted)

    lines = [line.rstrip() for line in str(text or "").splitlines()]

    if "include" in options:
        vals = [v.strip() for v in str(options["include"]).split(";") if v.strip()]
        if vals:
            lines = [line for line in lines if any(v in line for v in vals)]

    if "exclude" in options:
        vals = [v.strip() for v in str(options["exclude"]).split(";") if v.strip()]
        if vals:
            lines = [line for line in lines if not any(v in line for v in vals)]

    if "group" in options:
        g = str(options["group"]).strip()
        if g:
            lines = [line for line in lines if g in line]

    if "cut" in options:
        lines = _cut_lines(lines, options["cut"])

    if "regex" in options:
        lines = _regex_or(lines, options["regex"])

    if "regex_replace" in options:
        lines = _regex_replace(lines, options["regex_replace"])

    if str(options.get("strip", "0")).strip() == "1":
        lines = [line.split("$", 1)[0] if "$" in line else line for line in lines]

    if str(options.get("dedupe", "0")).strip() == "1":
        seen = set()
        uniq = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                uniq.append(line)
        lines = uniq

    if "add" in options:
        add_text = str(options["add"]).strip()
        if add_text:
            lines.insert(0, f"{add_text},#genre#")

    if "start" in options:
        try:
            start_i = int(str(options["start"]).strip())
            if start_i > 0:
                lines = lines[max(0, start_i - 1):]
        except Exception:
            pass

    if "end" in options:
        try:
            end_i = int(str(options["end"]).strip())
            if end_i >= 0:
                lines = lines[:end_i]
        except Exception:
            pass

    lines = [line for line in lines if line.strip()]

    if str(options.get("normalize", "0")).strip() == "1":
        lines = [_normalize_channel_name(line) for line in lines]

    return "\n".join(lines)


def _process_multiurl_text(raw_text, params):
    # 兼容 work.js 的 multiurl 语义:
    # 源文本类似：
    #   0,https://xxx/1.txt
    #   1,https://xxx/2.txt
    #   0,xxx.com/templ|...
    # 这里只处理最常见的模板替换：
    #   "key,rep1,rep2"
    #   "mg000" 会被替换成每个 rep
    lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
    out = []
    for line in lines:
        if not line or "," not in line:
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            continue
        key = parts[0]
        reps = parts[1:]
        if key == "0":
            template = "mg000,#genre#"
            for rep in reps:
                s = template.replace("mg000", rep)
                out.extend(s.splitlines())
            continue

        target_url = key
        if not target_url.startswith(("http://", "https://")):
            continue

        try:
            template_text = _fetch_url_text(target_url)
        except Exception:
            continue

        for rep in reps:
            out.extend(template_text.replace("mg000", rep).splitlines())
    return _process_single("\n".join(out), params)


class Spider(BaseSpider):
    def init(self, extend=""):
        self.extend = str(extend or "").strip()

    def liveContent(self, url):
        # 优先支持：
        # 1) 正常单 url + ext
        # 2) 多源 ext 列表
        # 3) 直接 ext 作为 url 列表
        base_url = str(url or "").strip()
        ext = self.extend

        if not ext:
            return ""

        ext_sources = _split_top_level_commas(ext)

        if len(ext_sources) > 1:
            merged = []
            for spec in ext_sources:
                parsed = _parse_source_spec(spec)
                s_url = parsed["url"]
                params = parsed["params"]

                # 这里是你贴出来的多源语法
                if str(params.get("multiurl", "0")).strip() == "1":
                    try:
                        raw = _fetch_url_text(s_url)
                    except Exception:
                        continue
                    merged.append(_process_multiurl_text(raw, params))
                else:
                    try:
                        raw = _fetch_url_text(s_url)
                    except Exception:
                        continue
                    merged.append(_process_single(raw, params))
            return "\n".join([x for x in merged if x.strip()])

        # 单个配置
        parsed = _parse_source_spec(ext)
        s_url = parsed["url"]
        params = parsed["params"]

        if not s_url and base_url:
            s_url = base_url

        if not s_url:
            return ""

        if str(params.get("multiurl", "0")).strip() == "1":
            try:
                raw = _fetch_url_text(s_url)
                return _process_multiurl_text(raw, params)
            except Exception as e:
                return "decrypt error: %s" % e

        try:
            raw = _fetch_url_text(s_url)
            return _process_single(raw, params)
        except Exception as e:
            return "decrypt error: %s" % e

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                query = dict(param)
            else:
                query = {}
            # 兼容 url 直接传值
            target = query.get("url") or query.get("u") or ""
            if not target:
                return [400, "text/plain; charset=utf-8", "missing url"]
            if target.startswith(("http://", "https://")):
                raw = _fetch_url_text(target)
                # 直接按 ext 的配置进行处理
                ext = self.extend
                parsed = _parse_source_spec(ext)
                params = parsed["params"]
                plain = _process_single(raw, params)
                return [200, "text/plain; charset=utf-8", plain]
            return [400, "text/plain; charset=utf-8", "missing url"]
        except Exception as e:
            return [502, "text/plain; charset=utf-8", "decrypt error: %s" % e]
