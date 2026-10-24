import base64
import json
import re
import requests

from base.spider import Spider as BaseSpider


# ============================================================
# JS 对应逻辑：
# const binary = atob(compact)
# let decoded = new TextDecoder().decode(bytes)
# output += String.fromCharCode(
#   decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length)
# )
#
# Python 等价：
# raw = base64.b64decode(compact)
# decoded = raw.decode("utf-8", errors="replace")
# out.append(chr(ord(ch) ^ ord(key[i % len(key)])))
# ============================================================

def _strip_comment_lines(text):
    out = []
    for line in str(text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        out.append(s)
    return "\n".join(out)


def _compact_base64(text):
    s = _strip_comment_lines(text).strip()
    if not s:
        return ""
    return "".join(ch for ch in s if ch not in "\r\n\t ")


def _looks_like_base64(s):
    if not s:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=]+", s)) and len(s) % 4 == 0


def _xor_charwise_decode(cipher_text, key):
    key = str(key or "").strip()
    if not key:
        raise ValueError("missing key")

    compact = _compact_base64(cipher_text)
    if not compact:
        raise ValueError("empty cipher")

    if not _looks_like_base64(compact):
        raise ValueError("not base64")

    if len(compact) % 4 != 0:
        compact += "=" * ((4 - len(compact) % 4) % 4)

    raw = base64.b64decode(compact, validate=False)
    decoded = raw.decode("utf-8", errors="replace")

    out = []
    for i, ch in enumerate(decoded):
        out.append(chr(ord(ch) ^ ord(key[i % len(key)])))
    return "".join(out)


def _regex_expr(expr):
    expr = (expr or "").strip()
    if not expr:
        return None
    m = re.match(r"^/(.*?)/([a-zA-Z]*)$", expr)
    if not m:
        return None
    pattern, flags = m.group(1), m.group(2)
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
        pat = _regex_expr(item)
        if pat:
            pats.append(pat)
    if not pats:
        return lines
    return [line for line in lines if any(p.search(line) for p in pats)]


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
    for seg in str(expr).split(";"):
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"^/(.*?)/(.+?)/$", seg)
        if not m:
            continue
        start_re = re.compile(m.group(1))
        end_re = re.compile(m.group(2))
        start_index = None
        end_index = None
        for i, line in enumerate(lines):
            if start_index is None and start_re.search(line):
                start_index = i
            if start_index is not None and end_index is None and end_re.search(line):
                end_index = i
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
    for group_name, items in groups.items():
        out.append(f"{group_name},#genre#")
        for item in items:
            out.append(item)
        out.append("")
    return out


def _normalize_channel_name(line):
    if "," not in line:
        return line
    name, tail = line.split(",", 1)
    clean = name.strip()

    rules = [
        (re.compile(r"上海电信", re.I), "76"),
        (re.compile(r"北京联通", re.I), "17"),
        (re.compile(r"吉林联通", re.I), "77"),
        (re.compile(r"四川电信", re.I), "70"),
        (re.compile(r"四川移动", re.I), "23"),
        (re.compile(r"四川联通", re.I), "40"),
        (re.compile(r"天津联通", re.I), "31"),
        (re.compile(r"安徽电信", re.I), "21"),
        (re.compile(r"山东电信", re.I), "78"),
        (re.compile(r"山东联通", re.I), "26"),
        (re.compile(r"山西电信", re.I), "18"),
        (re.compile(r"山西联通", re.I), "79"),
        (re.compile(r"广东电信", re.I), "14"),
        (re.compile(r"广东移动", re.I), "80"),
        (re.compile(r"广西电信", re.I), "81"),
        (re.compile(r"河北电信", re.I), "27"),
        (re.compile(r"河北联通", re.I), "32"),
        (re.compile(r"河南电信", re.I), "35"),
        (re.compile(r"河南联通", re.I), "36"),
        (re.compile(r"浙江电信", re.I), "82"),
        (re.compile(r"海南电信", re.I), "83"),
        (re.compile(r"海南联通", re.I), "84"),
        (re.compile(r"湖北电信", re.I), "15"),
        (re.compile(r"湖南电信", re.I), "16"),
        (re.compile(r"贵州电信", re.I), "85"),
        (re.compile(r"辽宁联通", re.I), "71"),
        (re.compile(r"重庆电信", re.I), "11"),
        (re.compile(r"重庆联通", re.I), "12"),
        (re.compile(r"陕西电信", re.I), "30"),
        (re.compile(r"青海电信", re.I), "13"),
        (re.compile(r"福建联通", re.I), "73"),
        (re.compile(r"ZB14", re.I), "吉林组播"),
        (re.compile(r"ZB13", re.I), "广西组播"),
        (re.compile(r"ZB12", re.I), "湖南组播"),
        (re.compile(r"ZB11", re.I), "内蒙组播"),
        (re.compile(r"ZB10", re.I), "山西组播"),
        (re.compile(r"ZB1", re.I), "辽宁组播"),
        (re.compile(r"ZB2", re.I), "青海组播"),
        (re.compile(r"ZB3", re.I), "四川组播"),
        (re.compile(r"ZB4", re.I), "山东组播"),
        (re.compile(r"ZB5", re.I), "北京组播"),
        (re.compile(r"ZB6", re.I), "福建组播"),
        (re.compile(r"ZB7", re.I), "安徽组播"),
        (re.compile(r"ZB8", re.I), "云南组播"),
        (re.compile(r"ZB9", re.I), "海南组播"),
        (re.compile(r"内蒙卫视", re.I), "内蒙古卫视"),
        (re.compile(r"福建公共", re.I), "福建乡村公共"),
        (re.compile(r"福建文体", re.I), "福建文旅体育"),
        (re.compile(r"重庆时红岩文化", re.I), "重庆红岩文化"),
        (re.compile(r"重庆影视剧", re.I), "重庆影视"),
        (re.compile(r"陕西1套", re.I), "陕西新闻资讯"),
        (re.compile(r"陕西2套", re.I), "陕西都市青春"),
        (re.compile(r"银铃", re.I), "陕西银龄"),
        (re.compile(r"陕西3套", re.I), "陕西银龄"),
        (re.compile(r"陕西5套", re.I), "陕西秦腔"),
        (re.compile(r"陕西6套", re.I), "CHC影迷电影"),
        (re.compile(r"陕西7套", re.I), "陕西体育休闲"),
        (re.compile(r"陕西8套", re.I), "陕西西部电影"),
        (re.compile(r"求索纪录", re.I), "求索纪录"),
        (re.compile(r"生态环境", re.I), "生态环境"),
        (re.compile(r"山东体育", re.I), "山东体育休闲"),
        (re.compile(r"吉林综艺", re.I), "吉林综艺文化"),
        (re.compile(r"文物宝库", re.I), "文物宝库"),
        (re.compile(r"河南收藏天下", re.I), "文物宝库"),
        (re.compile(r"河南戏曲", re.I), "梨园频道"),
        (re.compile(r"武术世界", re.I), "武术世界"),
        (re.compile(r"河南中华功夫", re.I), "武术世界"),
        (re.compile(r"河北农民", re.I), "河北三农"),
        (re.compile(r"江苏体育", re.I), "江苏体育休闲"),
        (re.compile(r"魅力足球", re.I), "魅力足球"),
        (re.compile(r"北京科教", re.I), "北京纪实科教"),
        (re.compile(r"央视精品", re.I), "CCTV文化精品"),
        (re.compile(r"靓装", re.I), "靓装"),
        (re.compile(r"国学", re.I), "国学频道"),
        (re.compile(r"天元围棋", re.I), "天元围棋"),
        (re.compile(r"茶", re.I), "茶频道"),
        (re.compile(r"书画", re.I), "书画频道"),
        (re.compile(r"精彩影视", re.I), "精彩影视"),
        (re.compile(r"动漫秀场", re.I), "动漫秀场"),
        (re.compile(r"游戏风云", re.I), "游戏风云"),
        (re.compile(r"法治天地", re.I), "法治天地"),
        (re.compile(r"都市剧场", re.I), "都市剧场"),
        (re.compile(r"多彩文体", re.I), "多彩文体"),
        (re.compile(r"金色学堂", re.I), "金色学堂"),
        (re.compile(r"生活时尚", re.I), "生活时尚"),
        (re.compile(r"第一财经", re.I), "第一财经"),
        (re.compile(r"东方影视", re.I), "东方影视"),
        (re.compile(r"财富天下", re.I), "财富天下"),
        (re.compile(r"快乐垂钓", re.I), "快乐垂钓"),
        (re.compile(r"金鹰纪实", re.I), "金鹰纪实"),
        (re.compile(r"金鹰卡通", re.I), "金鹰卡通"),
        (re.compile(r"嘉佳卡通", re.I), "嘉佳卡通"),
        (re.compile(r"哈哈炫动", re.I), "哈哈炫动"),
        (re.compile(r"五星体育", re.I), "五星体育"),
        (re.compile(r"梨园", re.I), "梨园频道"),
        (re.compile(r"农林", re.I), "中国农林卫视"),
        (re.compile(r"家庭理财", re.I), "家庭理财"),
        (re.compile(r"新动漫", re.I), "新动漫"),
        (re.compile(r"环球旅游", re.I), "环球旅游"),
        (re.compile(r"四海钓鱼", re.I), "四海钓鱼"),
        (re.compile(r"东方财经", re.I), "东方财经"),
        (re.compile(r"乐游", re.I), "乐游"),
        (re.compile(r"爱上4K", re.I), "爱上4K"),
        (re.compile(r"凤凰.*中文", re.I), "凤凰中文"),
        (re.compile(r"凤凰.*资讯", re.I), "凤凰资讯"),
        (re.compile(r"四川妇女儿童", re.I), "四川妇儿"),
        (re.compile(r"农林", re.I), "中国农林卫视"),
        (re.compile(r"旅游卫视", re.I), "海南卫视"),
        (re.compile(r"大湾区", re.I), "大湾区卫视"),
        (re.compile(r"福建卫视", re.I), "东南卫视"),
        (re.compile(r"上海卫视", re.I), "东方卫视"),
        (re.compile(r"CGTN英语", re.I), "CGTN"),
        (re.compile(r"^CCTV[-\s]*少儿$", re.I), "CCTV14少儿"),
        (re.compile(r"^CCTV[-\s]*新闻$", re.I), "CCTV13新闻"),
        (re.compile(r"^CCTV[-\s]*NEWS$", re.I), "CCTV13新闻"),
        (re.compile(r"^中国教育[- ]?1(?![\dA-Za-z]).*$", re.I), "CETV1"),
        (re.compile(r"^中国教育[- ]?2(?![\dA-Za-z]).*$", re.I), "CETV2"),
        (re.compile(r"^中国教育[- ]?3(?![\dA-Za-z]).*$", re.I), "CETV3"),
        (re.compile(r"^中国教育[- ]?4(?![\dA-Za-z]).*$", re.I), "CETV4"),
        (re.compile(r"兵器科技", re.I), "CCTV兵器科技"),
        (re.compile(r"风云音乐", re.I), "CCTV风云音乐"),
        (re.compile(r"第一剧场", re.I), "CCTV第一剧场"),
        (re.compile(r"风云足球", re.I), "CCTV风云足球"),
        (re.compile(r"风云剧场", re.I), "CCTV风云剧场"),
        (re.compile(r"怀旧剧场", re.I), "CCTV怀旧剧场"),
        (re.compile(r"女性时尚", re.I), "CCTV女性时尚"),
        (re.compile(r"世界地理", re.I), "CCTV世界地理"),
        (re.compile(r"央视台球", re.I), "CCTV央视台球"),
        (re.compile(r"高.*网", re.I), "CCTV高尔夫网球"),
        (re.compile(r"文化精品", re.I), "CCTV文化精品"),
        (re.compile(r"卫生健康", re.I), "CCTV卫生健康"),
        (re.compile(r"电视指南", re.I), "CCTV电视指南"),
        (re.compile(r"发现之旅", re.I), "发现之旅"),
        (re.compile(r"老故事", re.I), "老故事"),
        (re.compile(r"中学生", re.I), "中学生"),
        (re.compile(r"^CGTN.*录.*", re.I), "CGTN外语纪录"),
        (re.compile(r"^CGTN.*阿.*", re.I), "CGTN阿拉伯语"),
        (re.compile(r"^CGTN.*西.*", re.I), "CGTN西班牙语"),
        (re.compile(r"^CGTN.*法.*", re.I), "CGTN法语"),
        (re.compile(r"^CGTN.*俄.*", re.I), "CGTN俄语"),
        (re.compile(r"^CETV[- ]?1(?![\dA-Za-z]).*", re.I), "CETV1"),
        (re.compile(r"^CETV[- ]?2(?![\dA-Za-z]).*", re.I), "CETV2"),
        (re.compile(r"^CETV[- ]?3(?![\dA-Za-z]).*", re.I), "CETV3"),
        (re.compile(r"^CETV[- ]?4(?![\dA-Za-z]).*", re.I), "CETV4"),
        (re.compile(r"早.*教", re.I), "CETV早期教育"),
        (re.compile(r"^CCTV[- ]?4.*欧洲", re.I), "CCTV4欧洲"),
        (re.compile(r"^CCTV[- ]?4.*美洲", re.I), "CCTV4美洲"),
        (re.compile(r"^CCTV[- ]?5\+.*", re.I), "CCTV5+体育赛事"),
        (re.compile(r"^CCTV[- ]?4K.*", re.I), "CCTV4K"),
        (re.compile(r"^CCTV[- ]?8K.*", re.I), "CCTV8K"),
        (re.compile(r"动作电影", re.I), "CHC动作电影"),
        (re.compile(r"家庭影院", re.I), "CHC家庭影院"),
        (re.compile(r"影迷电影", re.I), "CHC影迷电影"),
        (re.compile(r"高清电影", re.I), "CHC影迷电影"),
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
        (re.compile(r"东南卫视", re.I), "东南卫视"),
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
        (re.compile(r"贵州卫视", re.I), "贵州卫视"),
        (re.compile(r"云南卫视", re.I), "云南卫视"),
        (re.compile(r"新疆卫视", re.I), "新疆卫视"),
        (re.compile(r"内蒙古卫视", re.I), "内蒙古卫视"),
        (re.compile(r"西藏卫视", re.I), "西藏卫视"),
    ]

    for re_obj, normalized in rules:
        if re_obj.search(clean):
            clean = normalized
            break

    return f"{clean},{tail}"


def _fetch_text(url):
    if not url:
        raise ValueError("missing url")
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        return url
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text


def _parse_source(spec):
    spec = str(spec or "").strip()
    if not spec:
        return {"url": "", "params": {}}

    if "|" in spec:
        url, rest = spec.split("|", 1)
    else:
        url, rest = spec, ""

    url = url.strip()
    rest = rest.strip()

    params = {}
    if rest:
        for part in rest.split("|"):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip().lower()] = v.strip()
            else:
                params[part.lower()] = "1"

    return {"url": url, "params": params}


def _split_sources(ext_text, fallback_url=""):
    ext_text = str(ext_text or "").strip()
    if not ext_text:
        if fallback_url:
            return [{"url": fallback_url, "params": {}}]
        return []

    items = []
    for seg in ext_text.split(","):
        seg = seg.strip()
        if seg:
            items.append(seg)

    result = []
    for item in items:
        parsed = _parse_source(item)
        if parsed["url"] or fallback_url:
            parsed["url"] = parsed["url"] or fallback_url
            result.append(parsed)
    return result


def _process_single(text, params):
    options = dict(params or {})

    # 这里是后续过滤逻辑，不再做解密
    lines = [line.rstrip() for line in str(text or "").splitlines()]

    if str(options.get("m3u", "0")).strip() == "1" or "#EXTM3U" in str(text or "").upper() or "#EXTINF" in str(text or "").upper():
        converted = _m3u_to_txt(text)
        if converted:
            text = "\n".join(converted)
            lines = [line.rstrip() for line in text.splitlines()]

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


# ============================================================
# work.js 的 urlDict
# ============================================================
URL_DICT = {
    "0": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GENRE",
    "1": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HPTYJ",
    "2": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/DLudp",
    "3": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/DLrtp",
    "4": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SYLNT",
    "5": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/template",
    "6": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/MBST",
    "7": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SHLT",
    "8": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HNLT",
    "9": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/CDDX",
    "10": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/MYDX1",
    "11": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/CQDX",
    "12": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/CQLT",
    "13": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/QHDX",
    "14": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GDDX",
    "15": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HuBDX",
    "16": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HuNDX",
    "17": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BJLT1",
    "18": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SXDX",
    "19": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SHLT1",
    "20": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HZDX1",
    "21": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/AHDX",
    "22": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JXDX",
    "23": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SCYD",
    "24": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/XJDX",
    "25": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NMGDX",
    "26": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SDLT",
    "27": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HeBDX",
    "28": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NEWL",
    "29": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BJDX",
    "30": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SSXDX1",
    "31": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/TJLT",
    "32": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HeBLT",
    "33": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HLJLT",
    "34": "https://gh-proxy.com/https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NMGDX",
    "35": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HNDX",
    "36": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HNLT1",
    "37": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JSDX",
    "38": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/KSSC",
    "39": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/KSSC1",
    "40": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SCLT",
    "41": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/KSSC2",
    "42": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HTML",
    "43": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/KSSC3",
    "44": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/TW4G",
    "45": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/XYMM",
    "46": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BJYD",
    "47": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NEWTV",
    "48": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HSJC",
    "49": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BJYD1",
    "50": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/WEBV",
    "51": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HKZB",
    "52": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HKZB1",
    "53": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/WEBV1",
    "54": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/DYZB",
    "55": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GOBK1",
    "56": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NHZB",
    "57": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JCPD",
    "58": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JCMG",
    "59": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/YSDX",
    "60": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/WSHZ",
    "61": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SZHZ",
    "62": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/DYZB1",
    "63": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BFGD",
    "64": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT1",
    "65": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT2",
    "66": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT3",
    "67": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT4",
    "68": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYWS",
    "69": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/IHOT",
    "70": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SCDX",
    "71": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SYLT",
    "72": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT5",
    "73": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/FJLT",
    "74": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT5a",
    "75": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/YNDX",
    "76": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SHDX",
    "77": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JLLT",
    "78": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SDDX",
    "79": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SXLT",
    "80": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GDYD",
    "81": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GXDX",
    "82": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/ZJDX",
    "83": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HiNDX",
    "84": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HiNLT",
    "85": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GZDX",
    "86": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/FJDX",
    "87": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NMDX",
    "88": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NMLT",
    "89": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JLDX",
    "90": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/TJDX",
    "91": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/ZJLT",
    "92": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/LNYD",
    "93": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HuBXYDX",
    "94": "https://gh-proxy.com/https://bov.lichaz.de5.net/?merge=https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/template|regex_replace=/$/&key=your_secret_key_he2026033723/",
    "95": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/FYAO",
    "96": "https://gh-proxy.com/https://bow.lichaz.de5.net/?merge=https://raw.githubusercontent.com/bankan-lichaz/qist/refs/heads/main/Dzone/D1|decrypt=1|key=youguess|regex_replace=/^\\/\\/.*//,https://raw.githubuser...",
    "97": "https://gh-proxy.com/https://bow.lichaz.de5.net/?merge=https://boz.lichaz.de5.net/?merge=https://boy.lichaz.de5.net/my_pro@multiurl&tvbox=1&tvboxKey=123456&tvboxIv=1790028633784",
    "98": "https://gh-proxy.com/https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/YSPL",
}

def _process_multiurl(raw_text, params):
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
                out.extend(template.replace("mg000", rep).splitlines())
            continue

        target_url = URL_DICT.get(key, key)
        if not target_url.startswith(("http://", "https://")):
            continue

        try:
            template_text = _fetch_text(target_url)
        except Exception:
            continue

        for rep in reps:
            out.extend(template_text.replace("mg000", rep).splitlines())

    if not out:
        return ""

    return _process_single("\n".join(out), params)


def _apply_pipeline(raw_text, params):
    # 关键顺序：
    # 1) 先解密
    # 2) 再 multiurl
    # 3) 再后续 filter / normalize / cut / regex ... 
    if str(params.get("decrypt", "0")).strip() == "1":
        key = str(params.get("key") or "").strip()
        if key:
            try:
                raw_text = _xor_charwise_decode(raw_text, key)
            except Exception:
                pass

    if str(params.get("multiurl", "0")).strip() == "1":
        return _process_multiurl(raw_text, params)

    return _process_single(raw_text, params)


class Spider(BaseSpider):
    def init(self, extend=""):
        self.extend = str(extend or "").strip()

    def getName(self):
        return "Decrypt"

    def liveContent(self, url):
        base_url = str(url or "").strip()
        sources = _split_sources(self.extend, base_url)

        if not sources:
            return ""

        outputs = []
        for src in sources:
            u = src["url"]
            params = src["params"]

            raw = _fetch_text(u)
            out = _apply_pipeline(raw, params)
            if out:
                outputs.append(out)

        return "\n".join(outputs)

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                query = dict(param)
            elif isinstance(param, str):
                try:
                    obj = json.loads(param)
                    query = dict(obj) if isinstance(obj, dict) else {"url": param}
                except Exception:
                    query = {"url": param}
            else:
                query = {}

            target = query.get("url") or query.get("u") or query.get("src") or ""
            if not target:
                return [400, "text/plain; charset=utf-8", "decrypt: missing url"]

            params = {}
            if query.get("key") or query.get("ext"):
                params["key"] = query.get("key") or query.get("ext")
                params["decrypt"] = "1"

            for k, v in query.items():
                if k.lower() in {"url", "u", "src", "key", "ext"}:
                    continue
                if v is None:
                    continue
                params[k.lower()] = str(v)

            raw = _fetch_text(target)
            out = _apply_pipeline(raw, params)
            return [200, "text/plain; charset=utf-8", out]

        except Exception as error:
            return [502, "text/plain; charset=utf-8", "decrypt: " + str(error)]
