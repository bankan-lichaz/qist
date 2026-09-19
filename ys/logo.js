// 配置项（可根据需求修改）
const CONFIG = {
    // 远程频道列表地址，和你PHP里的完全一致
    remoteListUrl: 'https://gh-proxy.com/https://raw.githubusercontent.com/iptv-pro/iptv-pro.github.io/be258403eb120250c368622892901bac52015141/list.txt',
    // 默认台标地址
    defaultLogo: 'https://iptv-pro.github.io/logo/default.png',
    // 缓存过期时间（毫秒，10分钟，TVbox用localStorage实现缓存）
    cacheExpire: 10 * 60 * 1000,
    // 请求超时时间（毫秒）
    requestTimeout: 10000,
    // 模拟浏览器UA，避免被防火墙拦截
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    // 是否需要不区分大小写匹配频道名，默认false（和PHP逻辑一致严格匹配）
    caseInsensitiveMatch: false
};

// 主逻辑（TVbox要求导出async函数）
module.exports = async function (params) {
    // 1. 获取TVbox传递的频道ID（对应PHP里的$_GET['id']）
    // TVbox的频道变量一般是{cid}，如果你的版本不一样可以改成$url.query.id或者其他变量
    const channelName = $url.query.id?.trim() || '';
    
    // 没有传频道ID直接返回默认logo
    if (!channelName) {
        return { logo: CONFIG.defaultLogo };
    }

    // 2. 尝试读localStorage缓存（减少远程请求，旧版本TVbox不支持也不会报错）
    let listContent = null;
    try {
        const cacheStr = $storage.get('iptv_logo_cache');
        if (cacheStr) {
            const cacheObj = JSON.parse(cacheStr);
            // 缓存未过期直接使用
            if (Date.now() - cacheObj.timestamp < CONFIG.cacheExpire) {
                listContent = cacheObj.content;
            }
        }
    } catch (e) {
        // 不支持localStorage的旧版本忽略缓存逻辑
    }

    // 3. 缓存失效则请求远程列表
    if (!listContent) {
        try {
            const res = await $http.get(CONFIG.remoteListUrl, {
                headers: { 'User-Agent': CONFIG.userAgent },
                timeout: CONFIG.requestTimeout
            });

            if (res?.status === 200 && res.body) {
                let content = res.body;
                // 去除UTF-8 BOM头，避免首行匹配失败
                content = content.replace(/^\uFEFF/, '');
                // 如果远程列表是GBK编码，取消下面注释（需TVbox版本支持$iconv方法，否则请先把列表转成UTF-8）
                // content = $iconv(content, 'GBK', 'UTF-8');

                listContent = content;
                // 写回缓存
                try {
                    $storage.set('iptv_logo_cache', JSON.stringify({
                        timestamp: Date.now(),
                        content: content
                    }));
                } catch (e) {}
            } else {
                throw new Error('列表请求失败');
            }
        } catch (e) {
            // 请求失败直接返回默认logo
            return { logo: CONFIG.defaultLogo };
        }
    }

    // 4. 匹配频道台标（逻辑和PHP完全一致）
    const lines = listContent.split('\n');
    let logoUrl = '';
    for (const line of lines) {
        const trimLine = line.trim();
        if (!trimLine) continue;
        const commaIdx = trimLine.indexOf(',');
        if (commaIdx === -1) continue;
        
        const name = trimLine.substring(0, commaIdx).trim();
        const url = trimLine.substring(commaIdx + 1).trim();

        // 匹配逻辑，和PHP一致
        const match = CONFIG.caseInsensitiveMatch 
            ? name.toLowerCase() === channelName.toLowerCase() 
            : name === channelName;
        
        if (match) {
            logoUrl = url;
            break;
        }
    }

    // 5. 返回结果，TVbox会自动使用logo字段的地址
    return {
        logo: logoUrl || CONFIG.defaultLogo
    };
};
