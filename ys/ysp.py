class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.brandActor = "📺 央视频直播"
        self.brandDirector = "ysp-live-multi"
        self._port = LOCAL_PORT_PREFERRED
        self._live_fmt = 'm3u'

    def init(self, extend=""):
        global LOGO_MODE, LOGO_PREFETCH
        ext = _ext_json(extend)
        if ext.get('port'):
            try:
                self._port = int(ext['port'])
            except Exception:
                self._port = LOCAL_PORT_PREFERRED
        if str(ext.get('live', '')).lower() in ('txt', 'm3u'):
            self._live_fmt = str(ext['live']).lower()
        mode = str(ext.get('logo', '')).lower()
        if mode in ('local', 'remote', 'off'):
            LOGO_MODE = mode
        if ext.get('logo_prefetch') is not None:
            LOGO_PREFETCH = bool(ext.get('logo_prefetch'))
        try:
            _ensure_local_server()
        except Exception as e:
            _log('本地服务失败: %s' % e)
        try:
            _ensure_logo_source(wait=0)
        except Exception:
            pass
        return True

    def getName(self): return "央视频直播"
    def isVideoFormat(self, url): return True
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def homeContent(self, filter):
        classes = [
            {'type_id': 'cctv', 'type_name': '央视'},
            {'type_id': 'satellite', 'type_name': '卫视'},
            {'type_id': 'cgtn', 'type_name': 'CGTN'},
            {'type_id': '4k', 'type_name': '4K超清'},
            {'type_id': 'premium', 'type_name': '付费剧场'},
            {'type_id': 'other', 'type_name': '其他'},
        ]
        list_all = [_vod(CHANNEL_MAP[s]) for s in CHANNEL_ORDER if _group_of(s) == 'cctv']
        return {'class': classes, 'list': list_all, 'filters': {}}

    def homeVideoContent(self):
        return {'list': [_vod(CHANNEL_MAP[s]) for s in CHANNEL_ORDER if _group_of(s) == 'cctv']}

    def _classify(self, base_slug):
        cats = []
        if re.match(r'^cctv\d+$', base_slug) or base_slug == 'cctv5p':
            if base_slug not in TRUE_4K_CHANNELS:
                cats.append('cctv')
        if base_slug in TRUE_4K_CHANNELS or base_slug == 'cctv4kb':
            cats.append('4k')
        if base_slug in ('cctvfyjc', 'cctvdyjc', 'cctvhjjc'):
            cats.append('premium')
        if base_slug.endswith('ws') or base_slug == 'cetv1' or base_slug == 'guoxue':
            cats.append('satellite' if not base_slug == 'guoxue' else 'other')
        if base_slug.startswith('cgtn'):
            cats.append('cgtn')
        if base_slug == 'guoxue':
            cats.append('other')
        return cats

    def _make_card(self, slug, name):
        tag = ''
        if slug in TRUE_4K_CHANNELS or slug == 'cctv4kb':
            tag = '真4K'
        elif slug in BACKEND_CHANNELS:
            tag = '高码率'
        item = {'vod_id': slug, 'vod_name': name, 'vod_remarks': format_remarks('央视频', tag)}
        logo = _logo_url(slug, name)
        if logo:
            item['vod_pic'] = logo
        return item

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or '')
        cards = [_vod(CHANNEL_MAP[s]) for s in CHANNEL_ORDER if tid in self._classify(s)]
        for slug, name, gname, urls in EXTERNAL_CHANNELS:
            if _ext_group_id(gname) == tid:
                cards.append(_vod_ext(slug, name, gname))
        return {'list': cards, 'page': 1, 'pagecount': 1, 'limit': len(cards), 'total': len(cards)}

    def detailContent(self, ids):
        slug = _slug_of(ids[0] if isinstance(ids, (list, tuple)) and ids else ids)
        ch = CHANNEL_MAP.get(slug)
        if ch is None:
            ext = EXTERNAL_MAP.get(slug)
            if ext is None:
                return {'list': []}
            name, gname = ext[1], ext[2]
            item = _vod_ext(slug, name, gname)
            item['vod_content'] = '%s · 直连官方/聚合直播源（本地不转发视频流量）' % name
            item['vod_play_from'] = gname
            item['vod_play_url'] = '直播$ysp://%s' % slug
            return {'list': [item]}
        item = _vod(ch)
        item['vod_content'] = '%s · 央视频直播（插件内嵌代理，播放器直连央视 CDN）' % ch.name
        item['vod_play_from'] = '央视频'
        item['vod_play_url'] = '直播$ysp://%s' % slug
        return {'list': [item]}

    def playerContent(self, flag, id, vipFlags=None):
        slug = _slug_of(id)
        ch = CHANNEL_MAP.get(slug)
        port = _ensure_local_server() if hasattr(self, '_port') else None
        if ch is None:
            ext = EXTERNAL_MAP.get(slug)
            if ext is not None:
                return {'parse': 0, 'jx': 0, 'url': ext[3][0],
                        'format': 'application/x-mpegURL',
                        'header': {'User-Agent': UA}}
            return {'parse': 0, 'jx': 0, 'url': slug}
        ensure_channel(ch)
        if port:
            return {'parse': 0, 'jx': 0,
                    'url': 'http://127.0.0.1:%d/%s.m3u8' % (port, slug),
                    'format': 'application/x-mpegURL',
                    'header': {'User-Agent': UA}}
        try:
            now = int(time.time())
            return {'parse': 0, 'jx': 0,
                    'url': jce_timeshift_url(ch.pid, ch.sid, now - WINDOW, now + 3600 * 3, ch.defn),
                    'format': 'application/x-mpegURL',
                    'header': {'User-Agent': UA}}
        except Exception as e:
            return {'parse': 0, 'jx': 0, 'url': slug, 'desc': str(e)[:60]}

    def liveContent(self, url=None):
        """直播配置: `live` 配置里用本文件时，App 会调这里返回 M3U/TXT 列表。"""
        raw = str(url or '').strip()
        if raw.startswith('ysp://'):
            raw = raw[len('ysp://'):]
        target = None if raw in ('', 'all', '*') else raw.split('/', 1)[0].split('?', 1)[0]
        port = _ensure_local_server()
        if self._live_fmt == 'txt':
            out = []
            last = None
            for slug, name, _s, _p, _d, _y in CHANNELS:
                g = GROUP_NAMES[_group_of(slug)]
                if g != last:
                    out.append('%s,#genre#' % g)
                    last = g
                out.append('%s,http://127.0.0.1:%d/%s.m3u8' % (name, port, slug))
            for slug, name, gname, urls in EXTERNAL_CHANNELS:
                if gname != last:
                    out.append('%s,#genre#' % gname)
                    last = gname
                for u in urls:
                    out.append('%s,%s' % (name, u))
            return '\n'.join(out) + '\n'
        out = ['#EXTM3U']
        for slug, name, _s, _p, _d, _y in CHANNELS:
            if target is not None and slug != target and slug + YSPTP_SLUG_SUFFIX != target:
                continue
            out.append('#EXTINF:-1 tvg-id="%s" tvg-name="%s" group-title="%s",%s' %
                       (slug, name, GROUP_NAMES[_group_of(slug)], name))
            out.append('http://127.0.0.1:%d/%s.m3u8' % (port, slug))
        for slug, name, gname, urls in EXTERNAL_CHANNELS:
            if target is not None and slug != target:
                continue
            for u in urls:
                out.append('#EXTINF:-1 tvg-id="%s" tvg-name="%s" group-title="%s",%s' %
                           (slug, name, gname, name))
                out.append(u)
        return '\n'.join(out) + '\n'

    def searchContent(self, key, quick, pg='1'):
        key = str(key or '').strip().lower()
        cards = []
        if key:
            for slug, name, _sid, _pid, _defn, _ys in CHANNELS:
                if key in name.lower() or key in slug.lower():
                    cards.append(self._make_card(slug, name))
            for slug, name, gname, urls in EXTERNAL_CHANNELS:
                if key in name.lower() or key in slug.lower():
                    cards.append(_vod_ext(slug, name, gname))
        return {'list': cards, 'page': 1, 'pagecount': 1, 'limit': len(cards), 'total': len(cards)}

    def action(self, action): return {'msg': 'ok'}
    def localProxy(self, params): return [404, 'text/plain; charset=utf-8', 'Proxy not configured']
