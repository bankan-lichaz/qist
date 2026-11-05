// Cloudflare Workers module port for ys/tb.py.
// GET: /?source=<url>|include=...|normalize=1&source=<url2>|exclude=...
// Also supports repeated `url` parameters and a comma-separated source list.
// When a source has no per-source options, top-level processing options are applied.

const NORMALIZE_RULES = [
  [/上海电信/i,"76"],[/北京联通/i,"17"],[/吉林联通/i,"77"],[/四川电信/i,"70"],[/四川移动/i,"23"],[/四川联通/i,"40"],[/天津联通/i,"31"],[/安徽电信/i,"21"],[/山东电信/i,"78"],[/山东联通/i,"26"],[/山西电信/i,"18"],[/山西联通/i,"79"],[/广东电信/i,"14"],[/广东移动/i,"80"],[/广西电信/i,"81"],[/河北电信/i,"27"],[/河北联通/i,"32"],[/河南电信/i,"35"],[/河南联通/i,"36"],[/浙江电信/i,"82"],[/海南电信/i,"83"],[/海南联通/i,"84"],[/湖北电信/i,"15"],[/湖南电信/i,"16"],[/贵州电信/i,"85"],[/辽宁联通/i,"71"],[/重庆电信/i,"11"],[/重庆联通/i,"12"],[/陕西电信/i,"30"],[/青海电信/i,"13"],[/福建联通/i,"73"],
  [/ZB14/i,"吉林组播"],[/ZB13/i,"广西组播"],[/ZB12/i,"湖南组播"],[/ZB11/i,"内蒙组播"],[/ZB10/i,"山西组播"],[/ZB1/i,"辽宁组播"],[/ZB2/i,"青海组播"],[/ZB3/i,"四川组播"],[/ZB4/i,"山东组播"],[/ZB5/i,"北京组播"],[/ZB6/i,"福建组播"],[/ZB7/i,"安徽组播"],[/ZB8/i,"云南组播"],[/ZB9/i,"海南组播"],
  [/^CCTV[-\\s]*少儿$/i,"CCTV14少儿"],[/^CCTV[-\\s]*新闻$/i,"CCTV13新闻"],[/^CCTV[-\\s]*NEWS$/i,"CCTV13新闻"],[/^CCTV[- ]?5\\+.*$/i,"CCTV5+体育赛事"],[/^CCTV[- ]?4K.*$/i,"CCTV4K"],[/^CCTV[- ]?8K.*$/i,"CCTV8K"],[/^CCTV[- ]?10.*$/i,"CCTV10科教"],[/^CCTV[- ]?11.*$/i,"CCTV11戏曲"],[/^CCTV[- ]?12.*$/i,"CCTV12社会与法"],[/^CCTV[- ]?13.*$/i,"CCTV13新闻"],[/^CCTV[- ]?14.*$/i,"CCTV14少儿"],[/^CCTV[- ]?15.*$/i,"CCTV15音乐"],[/^CCTV[- ]?16.*$/i,"CCTV16奥林匹克"],[/^CCTV[- ]?17.*$/i,"CCTV17农业农村"],
  [/^CCTV[- ]?1(?![\\dA-Za-z]).*$/i,"CCTV1综合"],[/^CCTV[- ]?2(?![\\dA-Za-z]).*$/i,"CCTV2财经"],[/^CCTV[- ]?3(?![\\dA-Za-z]).*$/i,"CCTV3综艺"],[/^CCTV[- ]?4(?![\\dA-Za-z]).*$/i,"CCTV4中文国际"],[/^CCTV[- ]?5(?![\\dA-Za-z]).*$/i,"CCTV5体育"],[/^CCTV[- ]?6(?![\\dA-Za-z]).*$/i,"CCTV6电影"],[/^CCTV[- ]?7(?![\\dA-Za-z]).*$/i,"CCTV7国防军事"],[/^CCTV[- ]?8(?![\\dA-Za-z]).*$/i,"CCTV8电视剧"],[/^CCTV[- ]?9(?![\\dA-Za-z]).*$/i,"CCTV9纪录"],
  [/内蒙卫视/i,"内蒙古卫视"],[/福建公共/i,"福建乡村公共"],[/福建文体/i,"福建文旅体育"],[/重庆影视剧/i,"重庆影视"],[/陕西1套/i,"陕西新闻资讯"],[/陕西2套/i,"陕西都市青春"],[/陕西3套|银铃/i,"陕西银龄"],[/陕西5套/i,"陕西秦腔"],[/陕西6套|高清电影|影迷电影/i,"CHC影迷电影"],[/陕西7套/i,"陕西体育休闲"],[/陕西8套/i,"陕西西部电影"],[/求索纪录/i,"求索纪录"],[/山东体育/i,"山东体育休闲"],[/吉林综艺/i,"吉林综艺文化"],[/河南戏曲|梨园/i,"梨园频道"],[/河南中华功夫|武术世界/i,"武术世界"],[/江苏体育/i,"江苏体育休闲"],[/北京科教/i,"北京纪实科教"],[/央视精品|文化精品/i,"CCTV文化精品"],[/农林/i,"中国农林卫视"],[/旅游卫视/i,"海南卫视"],[/福建卫视/i,"东南卫视"],[/上海卫视/i,"东方卫视"],
  ...["北京","东方","湖南","浙江","江苏","广东","山东","东南","深圳","安徽","四川","重庆","天津","湖北","河北","河南","海南","山西","江西","广西","陕西","吉林","黑龙江","辽宁","青海","宁夏","甘肃","贵州","云南","新疆","内蒙古","西藏"].map(n=>[new RegExp(n+"卫视","i"),n+"卫视"])
];

const asText = v => v == null ? "" : String(v);
const enabled = v => asText(v).trim() === "1";

function parseSource(spec) {
  const parts = asText(spec).trim().split("|");
  const url = parts.shift().trim();
  const params = {};
  for (const part of parts) {
    const item = part.trim(); if (!item) continue;
    const eq = item.indexOf("=");
    const key = (eq < 0 ? item : item.slice(0, eq)).trim().toLowerCase();
    params[key] = eq < 0 ? "1" : item.slice(eq + 1).trim();
  }
  return { url, params };
}
function extractSources(searchParams) {
  // `source` may be repeated. `url` is kept as a backwards-compatible alias.
  const specs = [...searchParams.getAll("source"), ...searchParams.getAll("url")];
  if (!specs.length) specs.push(searchParams.get("u") || searchParams.get("src") || "");
  // Match tb.py's comma-separated source convention. Encode literal commas in URLs as %2C,
  // or use repeated `source` parameters when an upstream URL itself contains commas.
  return specs.flatMap(spec => asText(spec).split(",").map(parseSource)).filter(x => x.url);
}
function regexOr(lines, expr) {
  const regs = asText(expr).split(";").map(s => {
    const m = s.trim().match(/^\/(.*?)\/([a-z]*)$/i);
    if (!m) return null;
    try { return new RegExp(m[1], m[2].includes("i") ? "i" : ""); } catch { return null; }
  }).filter(Boolean);
  return regs.length ? lines.filter(line => regs.some(re => re.test(line))) : lines;
}
function replacements(lines, expr) {
  for (const segment of asText(expr).split(";")) {
    const m = segment.trim().match(/^\/(.*?)\/(.+?)\/$/);
    if (!m) continue;
    try { const re = new RegExp(m[1], "g"); lines = lines.map(line => line.replace(re, m[2])); } catch {}
  }
  return lines;
}
function cutLines(lines, expr) {
  const out = [];
  for (const segment of asText(expr).split(";")) {
    const m = segment.trim().match(/^\/(.*?)\/(.+?)\/$/);
    if (!m) continue;
    try {
      const a = new RegExp(m[1]), b = new RegExp(m[2]);
      const start = lines.findIndex(x => a.test(x));
      const end = start < 0 ? -1 : lines.findIndex((x, i) => i >= start && b.test(x));
      if (start >= 0 && end >= start) out.push(...lines.slice(start, end + 1));
    } catch {}
  }
  return out;
}
function m3uToTxt(text) {
  const groups = new Map(); let group = "未分组", name = null;
  for (const line of asText(text).replace(/\r/g, "").split("\n").map(x=>x.trim()).filter(Boolean)) {
    if (line.startsWith("#EXTINF")) {
      const g = line.match(/group-title="([^"]+)"/i), n = line.match(/,(.*)$/);
      group = g ? g[1].trim() : "未分组"; name = n ? n[1].trim() : "未知频道";
      if (!groups.has(group)) groups.set(group, []);
    } else if (/^https?:\/\//i.test(line) && name) {
      groups.get(group).push(`${name},${line}`); name = null;
    }
  }
  const out=[]; for (const [g, items] of groups) out.push(`${g},#genre#`,...items,""); return out;
}
function normalize(line) {
  const comma = line.indexOf(","); if (comma < 0) return line;
  const name = line.slice(0, comma).trim();
  for (const [re, value] of NORMALIZE_RULES) if (re.test(name)) return value + line.slice(comma);
  return name + line.slice(comma);
}
function processText(text, params) {
  let lines = asText(text).split(/\r?\n/).map(x=>x.replace(/\s+$/,""));
  if (enabled(params.m3u) || /#EXTM3U|#EXTINF/i.test(asText(text))) {
    const converted=m3uToTxt(text); if(converted.length) lines=converted;
  }
  if (params.include != null) { const a=asText(params.include).split(";").map(x=>x.trim()).filter(Boolean); if(a.length) lines=lines.filter(x=>a.some(v=>x.includes(v))); }
  if (params.exclude != null) { const a=asText(params.exclude).split(";").map(x=>x.trim()).filter(Boolean); if(a.length) lines=lines.filter(x=>!a.some(v=>x.includes(v))); }
  if (asText(params.group).trim()) lines=lines.filter(x=>x.includes(asText(params.group).trim()));
  if (params.cut != null) lines=cutLines(lines,params.cut);
  if (params.regex != null) lines=regexOr(lines,params.regex);
  if (params.regex_replace != null) lines=replacements(lines,params.regex_replace);
  if (enabled(params.strip)) lines=lines.map(x=>x.split("$")[0]);
  if (enabled(params.dedupe)) lines=[...new Set(lines)];
  if (asText(params.add).trim()) lines.unshift(`${asText(params.add).trim()},#genre#`);
  if (params.start != null) { const n=parseInt(params.start,10); if(n>0) lines=lines.slice(n-1); }
  if (params.end != null) { const n=parseInt(params.end,10); if(n>=0) lines=lines.slice(0,n); }
  lines=lines.filter(x=>x.trim());
  if(enabled(params.normalize)) lines=lines.map(normalize);
  return lines.join("\n");
}
function decodeXor(text, key) {
  key=asText(key).trim(); if(!key) throw new Error("missing key");
  const compact=asText(text).split(/\r?\n/).map(x=>x.trim()).filter(x=>x&&!x.startsWith("//")).join("").replace(/[\t ]/g,"");
  if(!compact) throw new Error("empty cipher");
  if(!/^[A-Za-z0-9+/=]+$/.test(compact)||compact.length%4) throw new Error("not base64");
  const bytes=Uint8Array.from(atob(compact),c=>c.charCodeAt(0));
  const decoded=new TextDecoder().decode(bytes); let out="";
  for(let i=0;i<decoded.length;i++) out+=String.fromCharCode(decoded.charCodeAt(i)^key.charCodeAt(i%key.length));
  return out;
}
async function fetchText(url) {
  let parsed; try { parsed=new URL(url); } catch { throw new Error("invalid URL"); }
  if(!["http:","https:"].includes(parsed.protocol)) throw new Error("URL must use http or https");
  const res=await fetch(parsed.toString(),{headers:{"User-Agent":"Mozilla/5.0"},redirect:"follow"});
  if(!res.ok) throw new Error(`upstream HTTP ${res.status}`);
  return res.text();
}
function getGlobalParams(searchParams) {
  const ignored=new Set(["source","url","u","src"]), params={};
  for(const [k,v] of searchParams) if(!ignored.has(k.toLowerCase())) params[k.toLowerCase()]=v;
  return params;
}

export default {
  async fetch(request) {
    if(!["GET","POST"].includes(request.method)) return new Response("Method not allowed",{status:405,headers:{Allow:"GET, POST"}});
    try {
      const url=new URL(request.url), specs=extractSources(url.searchParams), globalParams=getGlobalParams(url.searchParams);
      if(request.method==="POST" && (request.headers.get("content-type")||"").includes("application/json")) {
        const body=await request.json();
        if(body && typeof body==="object" && !Array.isArray(body)) {
          const incoming=Array.isArray(body.sources)?body.sources:[body.source||body.url||body.u||body.src].filter(Boolean);
          specs.push(...incoming.flatMap(s=>asText(s).split(",").map(parseSource)).filter(s=>s.url));
          for(const [k,v] of Object.entries(body)) if(!["sources","source","url","u","src"].includes(k.toLowerCase()) && v!=null) globalParams[k.toLowerCase()]=String(v);
        }
      }
      if(!specs.length) return new Response("decrypt: missing url/source",{status:400,headers:{"Content-Type":"text/plain; charset=utf-8"}});
      const outputs=[];
      for(const src of specs) {
        // Per-link |options override common query parameters; links are processed independently.
        const params={...globalParams,...src.params};
        let raw=await fetchText(src.url);
        if(enabled(params.decrypt) && asText(params.key).trim()) { try { raw=decodeXor(raw,params.key); } catch {} }
        const result=processText(raw,params); if(result) outputs.push(result);
      }
      return new Response(outputs.join("\n"),{status:200,headers:{"Content-Type":"text/plain; charset=utf-8","Access-Control-Allow-Origin":"*"}});
    } catch(error) {
      return new Response("decrypt: "+(error?.message||String(error)),{status:502,headers:{"Content-Type":"text/plain; charset=utf-8","Access-Control-Allow-Origin":"*"}});
    }
  }
};
