# -*- coding: utf-8 -*-
"""OK影视/PySpider-compatible CCTV live plugin.

This legacy adapter is kept separate from cctv.py so the FongMi implementation
and its newer proxy API remain unchanged. It emits M3U and uses localProxy.
"""
import base64
import datetime
import hashlib
import html.parser
import json
import re
import secrets
import time
from urllib.parse import quote, urlencode, urljoin

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getProxyUrl(self, local=True):
            return "http://127.0.0.1:9978/proxy?do=py"


HOST = "https://tv.cctv.com"
CATALOG_URL = HOST + "/live/"
PLAY_URL = "https://vdnx.live.cntv.cn/api/v3/vdn/live"
PLAY_SECRET = "a4220a71b31746908fa3e7fdd7a6852a"
EPG_URL = "https://api.cntv.cn/epg/getEpgInfoByChannelNew"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
CHANNEL_RE = re.compile(r"^https?://tv\.cctv\.com/live/(cctv(?:\d+|5plus|jilu|child|europe|america))/", re.I)
CHANNEL_ID_RE = re.compile(r"^cctv(?:\d+|5plus|jilu|child|europe|america)$", re.I)

# Snapshot fallback mirrors ys/cctv.json; the catalogue is tried first.
FALLBACK_CHANNELS = [
    ("cctv1", "CCTV-1 综合"), ("cctv2", "CCTV-2 财经"), ("cctv3", "CCTV-3 综艺"),
    ("cctv4", "CCTV-4 中文国际（亚）"), ("cctv5", "CCTV-5 体育"),
    ("cctv5plus", "CCTV-5+ 体育赛事"), ("cctv6", "CCTV-6 电影"),
    ("cctv7", "CCTV-7 国防军事"), ("cctv8", "CCTV-8 电视剧"),
    ("cctvjilu", "CCTV-9 纪录"), ("cctv10", "CCTV-10 科教"),
    ("cctv11", "CCTV-11 戏曲"), ("cctv12", "CCTV-12 社会与法"),
    ("cctv13", "CCTV-13 新闻"), ("cctvchild", "CCTV-14 少儿"),
    ("cctv15", "CCTV-15 音乐"), ("cctv16", "CCTV-16 奥林匹克"),
    ("cctv17", "CCTV-17 农业农村"), ("cctveurope", "CCTV-4 中文国际（欧）"),
    ("cctvamerica", "CCTV-4 中文国际（美）"),
]


class _LinkParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href is not None:
            self.links.append((self.href, " ".join("".join(self.text).split())))
            self.href = None
            self.text = []


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.uid = ""
        self.session = requests.Session()

    def init(self, extend=""):
        self.extend = extend or ""
        self.uid = base64.b64encode(secrets.token_bytes(18)).decode("ascii")

    def getName(self):
        return "央视官网直播"

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {"class": [{"type_id": "live", "type_name": "央视频道"}], "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    def detailContent(self, ids):
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        return {"parse": 0, "playUrl": "", "url": str(id or ""), "header": {"User-Agent": UA}}

    def _channels(self, url):
        target = url or CATALOG_URL
        try:
            response = self.session.get(target, headers={"Referer": HOST + "/", "User-Agent": UA}, timeout=12)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            parser = _LinkParser()
            parser.feed(response.text)
            channels, seen = [], set()
            for href, name in parser.links:
                match = CHANNEL_RE.match(urljoin(target, href or ""))
                if match and name:
                    channel_id = match.group(1).lower()
                    if channel_id not in seen:
                        seen.add(channel_id)
                        channels.append({"id": channel_id, "name": name})
            if len(channels) >= 10:
                return channels
        except Exception as error:
            print("CCTV catalog fallback: %s" % error)
        return [{"id": cid, "name": name} for cid, name in FALLBACK_CHANNELS]

    def _proxy_base(self):
        try:
            base = self.getProxyUrl()
        except TypeError:
            base = self.getProxyUrl(True)
        return str(base).rstrip("&") + "&"

    def liveContent(self, url=""):
        lines = []
        proxy = self._proxy_base()
        lines.append("央视,#genre#")
        for channel in self._channels(url):
            cid, name = channel["id"], channel["name"]
            lines.append("%s,%sfun=cctv&id=%s" % (name, proxy, quote(cid)))
        return "\ufeff" + "\n".join(lines) + "\n"

    def localProxy(self, params):
        params = params or {}
        if params.get("fun") == "epg":
            return self._epg(params.get("id", ""), params.get("date", ""))
        if params.get("fun") not in ("cctv", "cctv_live"):
            return [404, "text/plain; charset=utf-8", "Unknown CCTV proxy"]
        channel_id = str(params.get("id", "")).lower()
        if not CHANNEL_ID_RE.fullmatch(channel_id):
            return [400, "text/plain; charset=utf-8", "Invalid CCTV channel id"]
        try:
            location = self._resolve(channel_id)
            return [302, "text/plain", "", {"Location": location, "Cache-Control": "no-store"}]
        except Exception as error:
            return [502, "text/plain; charset=utf-8", "CCTV: " + str(error)]

    def _resolve(self, channel_id):
        ts = int(time.time() * 1000)
        nonce = secrets.randbelow(901) + 100
        digest = hashlib.md5(("%s%d%d%s" % (channel_id, ts, nonce, PLAY_SECRET)).encode("utf-8")).hexdigest()
        auth_key = "%d-%d-%s" % (ts, nonce, digest)
        response = self.session.get(PLAY_URL, params={
            "channel": channel_id, "vn": "1", "pdrm": "1", "uid": self.uid, "hbss": str(ts),
        }, headers={
            "auth-key": auth_key, "Origin": HOST, "Referer": HOST + "/",
            "User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
        }, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("ack") != "yes":
            raise ValueError("CCTV play API rejected channel")
        manifest = data.get("manifest") or {}
        backup = data.get("backup") or {}
        location = manifest.get("hls_cdrm") or backup.get("hls_cdrm")
        if not isinstance(location, str) or not location.startswith(("http://", "https://")):
            raise ValueError("CCTV API returned no HLS URL")
        return location

    def _epg(self, channel_id, date):
        if not CHANNEL_ID_RE.fullmatch(str(channel_id)) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
            return [400, "text/plain; charset=utf-8", "Invalid EPG request"]
        try:
            response = self.session.get(EPG_URL, params={
                "c": channel_id, "serviceId": "tvcctv", "d": date.replace("-", ""),
            }, headers={"Referer": HOST + "/", "User-Agent": UA}, timeout=10)
            response.raise_for_status()
            return [200, "application/json", json.dumps(response.json(), ensure_ascii=False)]
        except Exception as error:
            return [502, "text/plain; charset=utf-8", str(error)]

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass
        self.uid = ""
        return None
