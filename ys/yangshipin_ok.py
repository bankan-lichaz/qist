# -*- coding: utf-8 -*-
"""OK影视/PySpider-compatible Yangshipin live plugin.

The FongMi implementation remains in yangshipin.py. This adapter emits legacy
M3U and resolves each selected channel through the public player API via
localProxy, avoiding third-party Python packages beyond requests.
"""
import base64
import hashlib
import json
import os
import random
import re
import secrets
import struct
import time
import uuid
from urllib.parse import quote, urlencode

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getProxyUrl(self, local=True):
            return "http://127.0.0.1:9978/proxy?do=py"

APP_LIVE_URL = "https://bkliveinfo.ysp.cctv.cn/"
APP_LIVE_PLATFORM = 4330403
APP_LIVE_VERSION = "V8.22.1035.3031"
USER_AGENT = "qqlive"
CHANNEL_SNAPSHOT_URL = "https://raw.githubusercontent.com/bankan-lichaz/qist/main/ys/yangshipin.json"

# Common channels are available even if the snapshot URL cannot be reached.
FALLBACK_CHANNELS = [
    {"name": "CCTV1", "pid": "600001859", "cnlid": "2024078201", "type": "yangshi"},
    {"name": "CCTV2", "pid": "600001800", "cnlid": "2024075401", "type": "yangshi"},
    {"name": "CCTV3", "pid": "600001801", "cnlid": "2024068501", "type": "yangshi"},
    {"name": "CCTV4", "pid": "600001814", "cnlid": "2029797101", "type": "yangshi"},
    {"name": "CCTV5", "pid": "600001818", "cnlid": "2024078401", "type": "yangshi"},
    {"name": "CCTV5+", "pid": "600001817", "cnlid": "2024078001", "type": "yangshi"},
    {"name": "CCTV6", "pid": "600108442", "cnlid": "2013693901", "type": "yangshi"},
    {"name": "CCTV7", "pid": "600004092", "cnlid": "2024072001", "type": "yangshi"},
    {"name": "CCTV8", "pid": "600001803", "cnlid": "2029793001", "type": "yangshi"},
    {"name": "CCTV9", "pid": "600004078", "cnlid": "2024078601", "type": "yangshi"},
    {"name": "CCTV10", "pid": "600001805", "cnlid": "2024078701", "type": "yangshi"},
    {"name": "CCTV11", "pid": "600001806", "cnlid": "2027248701", "type": "yangshi"},
    {"name": "CCTV12", "pid": "600001807", "cnlid": "2027248801", "type": "yangshi"},
    {"name": "CCTV13", "pid": "600001811", "cnlid": "2029797201", "type": "yangshi"},
    {"name": "CCTV14", "pid": "600001809", "cnlid": "2027248901", "type": "yangshi"},
    {"name": "CCTV15", "pid": "600001815", "cnlid": "2027249001", "type": "yangshi"},
    {"name": "CCTV16-HD", "pid": "600098637", "cnlid": "2027249101", "type": "yangshi"},
    {"name": "CCTV17", "pid": "600001810", "cnlid": "2027249401", "type": "yangshi"},
    {"name": "CCTV4K", "pid": "600002264", "cnlid": "2029810301", "type": "yangshi"},
    {"name": "CCTV8K", "pid": "600156816", "cnlid": "2026774101", "type": "yangshi"},
    {"name": "CGTN", "pid": "600014550", "cnlid": "2024181701", "type": "yangshi"},
    {"name": "北京卫视", "pid": "600002309", "cnlid": "2024052703", "type": "weishi"},
    {"name": "江苏卫视", "pid": "600002521", "cnlid": "2024171103", "type": "weishi"},
    {"name": "东方卫视", "pid": "600002483", "cnlid": "2024054503", "type": "weishi"},
    {"name": "浙江卫视", "pid": "600002520", "cnlid": "2024054703", "type": "weishi"},
    {"name": "湖南卫视", "pid": "600002475", "cnlid": "2024054803", "type": "weishi"},
]


def _u32(value):
    return value & 0xFFFFFFFF


def _tea_block(block, key):
    left, right = struct.unpack(">2I", block)
    keys = struct.unpack(">4I", key)
    total = 0
    for _ in range(16):
        total = _u32(total + 0x9E3779B9)
        left = _u32(left + (((right << 4) + keys[0]) ^ (right + total) ^ ((right >> 5) + keys[1])))
        right = _u32(right + (((left << 4) + keys[2]) ^ (left + total) ^ ((left >> 5) + keys[3])))
    return struct.pack(">2I", left, right)


def _tea_packet(data, key):
    pad_len = (8 - ((len(data) + 10) % 8)) % 8
    plain = bytes([(secrets.token_bytes(1)[0] & 0xF8) | pad_len]) + secrets.token_bytes(pad_len + 2) + data + bytes(7)
    output, previous_plain, previous_cipher = bytearray(), bytes(8), bytes(8)
    for offset in range(0, len(plain), 8):
        mixed = bytes(a ^ b for a, b in zip(plain[offset:offset + 8], previous_cipher))
        encrypted = _tea_block(mixed, key)
        cipher = bytes(a ^ b for a, b in zip(encrypted, previous_plain))
        output.extend(cipher)
        previous_plain, previous_cipher = mixed, cipher
    return bytes(output)


def _lp(value):
    data = value.encode("utf-8") if isinstance(value, str) else value
    return struct.pack(">H", len(data)) + data


def _checksum(data):
    value = 0
    for byte in data:
        value = (131 * value + byte) & 0x7FFFFFFF
    return value


def _ckey(cnlid):
    timestamp = int(time.time())
    guid = secrets.token_bytes(16).hex()
    guard_body = struct.pack(">I", timestamp) + _lp(guid[-5:]) + _lp("") + _lp("") + _lp("-1")
    guard_plain = _lp(guard_body)
    guard = _tea_packet(guard_plain, bytes.fromhex("110dbec10c23e7d2e56a1cad6914ef1b")) + struct.pack(">I", _checksum(guard_plain))
    guard_mask = bytes.fromhex("b3c953a06913ad4d")
    guard = bytes(value ^ guard_mask[i % 8] for i, value in enumerate(guard)).hex().upper()
    body = bytes.fromhex("0000004200000004000004d2") + struct.pack(">3I", APP_LIVE_PLATFORM, 0, timestamp)
    for value in ("dcgh", "_zj1A5Gh6QYcxWjIUGos2w==", APP_LIVE_VERSION, cnlid, guid):
        body += _lp(value)
    body += struct.pack(">2I", 1, 1)
    for value in (secrets.token_bytes(4).hex().upper(), "nil", "57eab0c4-2c58-44c6-8ae9-dd2757525dc5",
                  "nil", "v0.1.000", "com.cctv.yangshipin.app.iphone", str(APP_LIVE_PLATFORM),
                  "ex_json_bus", "ex_json_vs", guard):
        body += _lp(value)
    packet = bytearray(_lp(body))
    packet[18:22] = struct.pack(">I", _checksum(packet))
    encrypted = _tea_packet(bytes(packet), bytes.fromhex("59b2f7cf725ef43c34fdd7c123411ed3"))
    encrypted += struct.pack(">I", _checksum(packet))
    mask = bytes.fromhex("842eed08f066e6ea48b4caa991ed6ff3")
    encrypted = bytes(value ^ mask[i % len(mask)] for i, value in enumerate(encrypted))
    token = base64.b64encode(encrypted).decode("ascii").replace("+", "_").replace("/", "-").rstrip("=")
    return {"cKey": "--01" + token, "guid": guid, "fntick": str(timestamp),
            "flowid": uuid.uuid4().hex.upper() + "_" + str(APP_LIVE_PLATFORM)}


def _play_params(channel, definition="fhd"):
    params = {
        "atime": "120", "livepid": str(channel["pid"]), "cnlid": str(channel["cnlid"]),
        "appVer": APP_LIVE_VERSION, "app_version": "300090", "caplv": "1", "cmd": "2",
        "defn": definition, "device": "iPhone", "encryptVer": "4.2", "getpreviewinfo": "0",
        "hevclv": "0", "lang": "zh-Hans_CN", "livequeue": "0", "logintype": "1",
        "nettype": "1", "newnettype": "1", "newplatform": str(APP_LIVE_PLATFORM),
        "platform": str(APP_LIVE_PLATFORM), "sdtfrom": "v3021", "spacode": "23", "spaudio": "1",
        "spdemuxer": "6", "spdrm": "2", "spdynamicrange": "1", "spflv": "1",
        "spflvaudio": "1", "sphdrfps": "60", "sphttps": "1",
        "spvcode": base64.b64encode(b"H(30:1080,60:1080|30:1080,60:1080)").decode("ascii"),
        "spvideo": "4", "stream": "1", "system": "1", "sysver": "ios18.2.1",
        "uhd_flag": "0", "playbacktime": "0",
    }
    params.update(_ckey(str(channel["cnlid"])))
    return params


class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.session = requests.Session()
        self.channels = []

    def init(self, extend=""):
        self.extend = extend or ""
        self.channels = self._load_snapshot(self.extend)

    def getName(self):
        return "央视频直播"

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        return {"class": [{"type_id": "all", "type_name": "央视频道"}], "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    def detailContent(self, ids):
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        return {"parse": 0, "playUrl": "", "url": str(id or ""), "header": {"User-Agent": USER_AGENT}}

    def _load_snapshot(self, source):
        for candidate in (source, CHANNEL_SNAPSHOT_URL):
            if not candidate:
                continue
            try:
                if str(candidate).startswith(("http://", "https://")):
                    response = self.session.get(candidate, timeout=12, headers={"User-Agent": USER_AGENT})
                    response.raise_for_status()
                    data = response.json()
                else:
                    path = str(candidate)
                    if path.startswith("file://"):
                        path = path[7:]
                    if not os.path.isfile(path):
                        continue
                    with open(path, "r", encoding="utf-8") as stream:
                        data = json.load(stream)
                channels = data.get("channels") if isinstance(data, dict) else None
                valid = [item for item in channels or [] if isinstance(item, dict)
                         and str(item.get("pid", "")).isdigit() and str(item.get("cnlid", "")).isdigit()
                         and item.get("name")]
                if valid:
                    return valid
            except Exception as error:
                print("Yangshipin snapshot fallback: %s" % error)
        return list(FALLBACK_CHANNELS)

    def _proxy_base(self):
        try:
            base = self.getProxyUrl()
        except TypeError:
            base = self.getProxyUrl(True)
        return str(base).rstrip("&") + "&"

    def liveContent(self, url=""):
        channels = self.channels or self._load_snapshot(self.extend)
        groups = {}
        for channel in channels:
            kind = channel.get("type", "yangshi")
            group = "卫视频道" if kind == "weishi" else "央视频道"
            groups.setdefault(group, []).append(channel)
        lines = []
        proxy = self._proxy_base()
        for group, items in groups.items():
            lines.append(group + ",#genre#")
            for channel in items:
                query = urlencode({"fun": "yangshipin", "pid": str(channel["pid"]),
                                  "cnlid": str(channel["cnlid"]), "defn": "shd" if channel.get("vip") else "fhd"})
                lines.append("%s,%s%s" % (channel["name"], proxy, query))
        return "\n".join(lines) + "\n"

    def localProxy(self, params):
        params = params or {}
        if params.get("fun") not in ("yangshipin", "ysp"):
            return [404, "text/plain; charset=utf-8", "Unknown Yangshipin proxy"]
        pid, cnlid = str(params.get("pid", "")), str(params.get("cnlid", ""))
        if not pid.isdigit() or not cnlid.isdigit():
            return [400, "text/plain; charset=utf-8", "Invalid channel id"]
        channel = next((item for item in self.channels if str(item.get("pid")) == pid
                        and str(item.get("cnlid")) == cnlid), None)
        if channel is None:
            channel = {"pid": pid, "cnlid": cnlid, "name": pid}
        definition = params.get("defn", "fhd")
        if definition not in ("fhd", "shd"):
            definition = "fhd"
        try:
            response = self.session.get(APP_LIVE_URL, params=_play_params(channel, definition),
                                        headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=18)
            response.raise_for_status()
            data = response.json()
            if str(data.get("iretcode", "-1")) != "0":
                raise ValueError("play API iretcode=" + str(data.get("iretcode")))
            location = data.get("playurl")
            backups = data.get("backurl_list") or data.get("backurlList") or []
            candidates = [location]
            if isinstance(backups, list):
                candidates.extend(item.get("url") or item.get("playurl") if isinstance(item, dict) else item for item in backups)
            if not any(isinstance(item, str) and item.startswith(("http://", "https://")) for item in candidates):
                raise ValueError("play API returned no HLS URL")
            location = next(item for item in candidates if isinstance(item, str) and item.startswith(("http://", "https://")))
            extension = data.get("extended_param") or ""
            if extension:
                location += extension if "?" in location else "?" + str(extension).lstrip("&?")
            return [302, "application/vnd.apple.mpegurl", "", {"Location": location, "Cache-Control": "no-store"}]
        except Exception as error:
            return [502, "text/plain; charset=utf-8", "Yangshipin: " + str(error)]

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass
        return None
