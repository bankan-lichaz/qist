export default {
  async fetch(request) {
    const { searchParams } = new URL(request.url);

    // 自动识别浏览器编码的 %7C → |
    const mergeRaw = searchParams.get("merge")?.replace(/%7C/gi, "|");
    if (!mergeRaw) {
      return new Response("Missing merge parameter");
    }

    // 全局参数
    const g_include = searchParams.get("include");
    const g_exclude = searchParams.get("exclude");
    const g_group = searchParams.get("group");
    const g_strip = searchParams.get("strip") === "1";
    const g_dedupe = searchParams.get("dedupe") === "1";
    const g_start = parseInt(searchParams.get("start")) || 1;
    const g_end = searchParams.get("end") ? parseInt(searchParams.get("end")) : null;
    const g_decrypt = searchParams.get("decrypt") === "1";
    const g_key = searchParams.get("key") || "";
    const g_regex = searchParams.get("regex");
    const g_regex_replace = searchParams.get("regex_replace");
    const g_cut = searchParams.get("cut"); // 新增：截取关键字区间
    const g_add = searchParams.get("add");
    const g_normalize = searchParams.get("normalize") === "1";  // ⭐ 全局频道名标准化开关

// ⭐ 频道名标准化映射表
const CHANNEL_MAP = [
// ⭐ 特殊名称
{ reg: /上海电信/i, norm: "76" },
{ reg: /北京联通/i, norm: "17" },
{ reg: /吉林联通/i, norm: "77" },
{ reg: /四川电信/i, norm: "70" },
{ reg: /四川移动/i, norm: "23" },
{ reg: /四川联通/i, norm: "40" },
{ reg: /天津联通/i, norm: "31" },
{ reg: /安徽电信/i, norm: "21" },
{ reg: /山东电信/i, norm: "78" },
{ reg: /山东联通/i, norm: "26" },
{ reg: /山西电信/i, norm: "18" },
{ reg: /山西联通/i, norm: "79" },
{ reg: /广东电信/i, norm: "14" },
{ reg: /广东移动/i, norm: "80" },
{ reg: /广西电信/i, norm: "81" },
{ reg: /河北电信/i, norm: "27" },
{ reg: /河北联通/i, norm: "32" },
{ reg: /河南电信/i, norm: "35" },
{ reg: /河南联通/i, norm: "36" },
{ reg: /浙江电信/i, norm: "82" },
{ reg: /海南电信/i, norm: "83" },
{ reg: /海南联通/i, norm: "84" },
{ reg: /湖北电信/i, norm: "15" },
{ reg: /湖南电信/i, norm: "16" },
{ reg: /贵州电信/i, norm: "85" },
{ reg: /辽宁联通/i, norm: "71" },
{ reg: /重庆电信/i, norm: "11" },
{ reg: /重庆联通/i, norm: "12" },
{ reg: /陕西电信/i, norm: "30" },
{ reg: /青海电信/i, norm: "13" },
{ reg: /福建联通/i, norm: "73" },
{ reg: /ZB1/i, norm: "辽宁组播" },
{ reg: /ZB2/i, norm: "青海组播" },
{ reg: /ZB3/i, norm: "四川组播" },
{ reg: /ZB4/i, norm: "山东组播" },
{ reg: /ZB5/i, norm: "北京组播" },
{ reg: /ZB6/i, norm: "福建组播" },
{ reg: /ZB7/i, norm: "安徽组播" },
{ reg: /ZB8/i, norm: "云南组播" },
{ reg: /ZB9/i, norm: "海南组播" },
{ reg: /内蒙卫视/i, norm: "内蒙古卫视" },
{ reg: /福建公共/i, norm: "福建乡村公共" },
{ reg: /福建文体/i, norm: "福建文旅体育" },
{ reg: /重庆时红岩文化/i, norm: "重庆红岩文化" },
{ reg: /重庆影视剧/i, norm: "重庆影视" },
{ reg: /陕西1套/i, norm: "陕西新闻资讯" },
{ reg: /陕西2套/i, norm: "陕西都市青春" },
{ reg: /银铃/i, norm: "陕西银龄" },
{ reg: /陕西3套/i, norm: "陕西银龄" },
{ reg: /陕西5套/i, norm: "陕西秦腔" },
{ reg: /陕西6套/i, norm: "CHC影迷电影" },
{ reg: /陕西7套/i, norm: "陕西体育休闲" },
{ reg: /陕西8套/i, norm: "陕西西部电影" },
{ reg: /求索纪录/i, norm: "求索纪录" },
{ reg: /生态环境/i, norm: "生态环境" },
{ reg: /山东体育/i, norm: "山东体育休闲" },
{ reg: /吉林综艺/i, norm: "吉林综艺文化" },
{ reg: /文物宝库/i, norm: "文物宝库" },
{ reg: /河南收藏天下/i, norm: "文物宝库" },
{ reg: /河南戏曲/i, norm: "梨园频道" },
{ reg: /武术世界/i, norm: "武术世界" },
{ reg: /河南中华功夫/i, norm: "武术世界" },
{ reg: /河北农民/i, norm: "河北三农" },
{ reg: /江苏体育/i, norm: "江苏体育休闲" },
{ reg: /魅力足球/i, norm: "魅力足球" },
{ reg: /北京科教/i, norm: "北京纪实科教" },
{ reg: /央视精品/i, norm: "CCTV文化精品" },
{ reg: /靓装/i, norm: "靓装" },
{ reg: /国学/i, norm: "国学频道" },
{ reg: /天元围棋/i, norm: "天元围棋" },
{ reg: /茶/i, norm: "茶频道" },
{ reg: /书画/i, norm: "书画频道" },
{ reg: /精彩影视/i, norm: "精彩影视" },
{ reg: /动漫秀场/i, norm: "动漫秀场" },
{ reg: /游戏风云/i, norm: "游戏风云" },
{ reg: /法治天地/i, norm: "法治天地" },
{ reg: /都市剧场/i, norm: "都市剧场" },
{ reg: /多彩文体/i, norm: "多彩文体" },
{ reg: /金色学堂/i, norm: "金色学堂" },
{ reg: /生活时尚/i, norm: "生活时尚" },
{ reg: /第一财经/i, norm: "第一财经" },
{ reg: /东方影视/i, norm: "东方影视" },
{ reg: /财富天下/i, norm: "财富天下" },
{ reg: /快乐垂钓/i, norm: "快乐垂钓" },
{ reg: /金鹰纪实/i, norm: "金鹰纪实" },
{ reg: /金鹰卡通/i, norm: "金鹰卡通" },
{ reg: /嘉佳卡通/i, norm: "嘉佳卡通" },
{ reg: /哈哈炫动/i, norm: "哈哈炫动" },
{ reg: /五星体育/i, norm: "五星体育" },
{ reg: /梨园/i, norm: "梨园频道" },
{ reg: /农林/i, norm: "中国农林卫视" },
{ reg: /家庭理财/i, norm: "家庭理财" },
{ reg: /新动漫/i, norm: "新动漫" },
{ reg: /环球旅游/i, norm: "环球旅游" },
{ reg: /四海钓鱼/i, norm: "四海钓鱼" },
{ reg: /东方财经/i, norm: "东方财经" },
{ reg: /乐游/i, norm: "乐游" },
{ reg: /爱上4K/i, norm: "爱上4K" },
{ reg: /凤凰.*中文/i, norm: "凤凰中文" },
{ reg: /凤凰.*资讯/i, norm: "凤凰资讯" },
{ reg: /四川妇女儿童/i, norm: "四川妇儿" },
{ reg: /农林/i, norm: "中国农林卫视" },
{ reg: /旅游卫视/i, norm: "海南卫视" },
{ reg: /大湾区/i, norm: "大湾区卫视" },
{ reg: /福建卫视/i, norm: "东南卫视" },
{ reg: /上海卫视/i, norm: "东方卫视" },
{ reg: /CGTN英语/i, norm: "CGTN" },
{ reg: /^CCTV[-\s]*少儿$/i, norm: "CCTV14少儿" },
{ reg: /^CCTV[-\s]*新闻$/i, norm: "CCTV13新闻" },
{ reg: /^CCTV[-\s]*NEWS$/i, norm: "CCTV13新闻" },
{ reg: /^中国教育[- ]?1(?![\dA-Za-z]).*$/i, norm: "CETV1" },
{ reg: /^中国教育[- ]?2(?![\dA-Za-z]).*$/i, norm: "CETV2" },
{ reg: /^中国教育[- ]?3(?![\dA-Za-z]).*$/i, norm: "CETV3" },
{ reg: /^中国教育[- ]?4(?![\dA-Za-z]).*$/i, norm: "CETV4" },

  // ⭐ 特殊频道必须放最前面
{ reg: /兵器科技/i, norm: "CCTV兵器科技" },
{ reg: /风云音乐/i, norm: "CCTV风云音乐" },
{ reg: /第一剧场/i, norm: "CCTV第一剧场" },
{ reg: /风云足球/i, norm: "CCTV风云足球" },
{ reg: /风云剧场/i, norm: "CCTV风云剧场" },
{ reg: /怀旧剧场/i, norm: "CCTV怀旧剧场" },
{ reg: /女性时尚/i, norm: "CCTV女性时尚" },
{ reg: /世界地理/i, norm: "CCTV世界地理" },
{ reg: /央视台球/i, norm: "CCTV央视台球" },
{ reg: /高.*网/i, norm: "CCTV高尔夫网球" },
{ reg: /文化精品/i, norm: "CCTV文化精品" },
{ reg: /卫生健康/i, norm: "CCTV卫生健康" },
{ reg: /电视指南/i, norm: "CCTV电视指南" },
{ reg: /发现之旅/i, norm: "发现之旅" },
{ reg: /老故事/i, norm: "老故事" },
{ reg: /中学生/i, norm: "中学生" },

// CGTN
{ reg: /^CGTN.*录.*/i, norm: "CGTN外语纪录" },
{ reg: /^CGTN.*阿.*/i, norm: "CGTN阿拉伯语" },
{ reg: /^CGTN.*西.*/i, norm: "CGTN西班牙语" },
{ reg: /^CGTN.*法.*/i, norm: "CGTN法语" },
{ reg: /^CGTN.*俄.*/i, norm: "CGTN俄语" },

// CETV
{ reg: /^CETV[- ]?1(?![\dA-Za-z]).*/i, norm: "CETV1" },
{ reg: /^CETV[- ]?2(?![\dA-Za-z]).*/i, norm: "CETV2" },
{ reg: /^CETV[- ]?3(?![\dA-Za-z]).*/i, norm: "CETV3" },
{ reg: /^CETV[- ]?4(?![\dA-Za-z]).*/i, norm: "CETV4" },
{ reg: /早.*教/i, norm: "CETV早期教育" },

// CCTV4 地区版
{ reg: /^CCTV[- ]?4.*欧洲/i, norm: "CCTV4欧洲" },
{ reg: /^CCTV[- ]?4.*美洲/i, norm: "CCTV4美洲" },

// CCTV 特殊频道
{ reg: /^CCTV[- ]?5\+.*/i, norm: "CCTV5+体育赛事" },
{ reg: /^CCTV[- ]?4K.*/i, norm: "CCTV4K" },
{ reg: /^CCTV[- ]?8K.*/i, norm: "CCTV8K" },

// CHC
{ reg: /动作电影/i, norm: "CHC动作电影" },
{ reg: /家庭影院/i, norm: "CHC家庭影院" },
{ reg: /影迷电影/i, norm: "CHC影迷电影" },
{ reg: /高清电影/i, norm: "CHC影迷电影" },

  // ⭐ 两位数频道（避免 CCTV10 被 CCTV1 吃掉）
  { reg: /^CCTV[- ]?10.*$/i, norm: "CCTV10科教" },
  { reg: /^CCTV[- ]?11.*$/i, norm: "CCTV11戏曲" },
  { reg: /^CCTV[- ]?12.*$/i, norm: "CCTV12社会与法" },
  { reg: /^CCTV[- ]?13.*$/i, norm: "CCTV13新闻" },
  { reg: /^CCTV[- ]?14.*$/i, norm: "CCTV14少儿" },
  { reg: /^CCTV[- ]?15.*$/i, norm: "CCTV15音乐" },
  { reg: /^CCTV[- ]?16.*$/i, norm: "CCTV16奥林匹克" },
  { reg: /^CCTV[- ]?17.*$/i, norm: "CCTV17农业农村" },

  // ⭐ 一位数频道（必须禁止后面跟数字或字母）
  { reg: /^CCTV[- ]?1(?![\dA-Za-z]).*$/i, norm: "CCTV1综合" },
  { reg: /^CCTV[- ]?2(?![\dA-Za-z]).*$/i, norm: "CCTV2财经" },
  { reg: /^CCTV[- ]?3(?![\dA-Za-z]).*$/i, norm: "CCTV3综艺" },
  { reg: /^CCTV[- ]?4(?![\dA-Za-z]).*$/i, norm: "CCTV4中文国际" },
  { reg: /^CCTV[- ]?5(?![\dA-Za-z]).*$/i, norm: "CCTV5体育" },
  { reg: /^CCTV[- ]?6(?![\dA-Za-z]).*$/i, norm: "CCTV6电影" },
  { reg: /^CCTV[- ]?7(?![\dA-Za-z]).*$/i, norm: "CCTV7国防军事" },
  { reg: /^CCTV[- ]?8(?![\dA-Za-z]).*$/i, norm: "CCTV8电视剧" },
  { reg: /^CCTV[- ]?9(?![\dA-Za-z]).*$/i, norm: "CCTV9纪录" },

  // ⭐ 全国卫视
  { reg: /北京卫视/i, norm: "北京卫视" },
  { reg: /东方卫视/i, norm: "东方卫视" },
  { reg: /湖南卫视/i, norm: "湖南卫视" },
  { reg: /浙江卫视/i, norm: "浙江卫视" },
  { reg: /江苏卫视/i, norm: "江苏卫视" },
  { reg: /广东卫视/i, norm: "广东卫视" },
  { reg: /山东卫视/i, norm: "山东卫视" },
  { reg: /东南卫视/i, norm: "东南卫视" },
  { reg: /深圳卫视/i, norm: "深圳卫视" },
  { reg: /安徽卫视/i, norm: "安徽卫视" },
  { reg: /四川卫视/i, norm: "四川卫视" },
  { reg: /重庆卫视/i, norm: "重庆卫视" },
  { reg: /天津卫视/i, norm: "天津卫视" },
  { reg: /湖北卫视/i, norm: "湖北卫视" },
  { reg: /河北卫视/i, norm: "河北卫视" },
  { reg: /河南卫视/i, norm: "河南卫视" },
  { reg: /海南卫视/i, norm: "海南卫视" },
  { reg: /山西卫视/i, norm: "山西卫视" },
  { reg: /江西卫视/i, norm: "江西卫视" },
  { reg: /广西卫视/i, norm: "广西卫视" },
  { reg: /陕西卫视/i, norm: "陕西卫视" },
  { reg: /吉林卫视/i, norm: "吉林卫视" },
  { reg: /黑龙江卫视/i, norm: "黑龙江卫视" },
  { reg: /辽宁卫视/i, norm: "辽宁卫视" },
  { reg: /青海卫视/i, norm: "青海卫视" },
  { reg: /宁夏卫视/i, norm: "宁夏卫视" },
  { reg: /甘肃卫视/i, norm: "甘肃卫视" },
  { reg: /贵州卫视/i, norm: "贵州卫视" },
  { reg: /云南卫视/i, norm: "云南卫视" },
  { reg: /新疆卫视/i, norm: "新疆卫视" },
  { reg: /内蒙古卫视/i, norm: "内蒙古卫视" },
  { reg: /西藏卫视/i, norm: "西藏卫视" },
];



// ⭐ 标准化频道名函数
function normalizeChannelName(line) {
  if (!line.includes(",")) return line;

  const [name, url] = line.split(",");
  let clean = name.trim();

  for (const { reg, norm } of CHANNEL_MAP) {
    if (reg.test(clean)) {
      clean = norm;
      break;
    }
  }

  return `${clean},${url}`;
}



    // ⭐ TVBox UA 模拟
    async function fetchTxt(u) {
      const res = await fetch(u, {
        headers: {
          "User-Agent": "okhttp/3.12.1",
          "Accept": "*/*",
          "Connection": "close"
        }
      });
      return await res.text();
    }

    // 智能解密
    function tryDecrypt(text, decrypt, key) {
      if (!decrypt || !key) return text;
      const base64Regex = /^[0-9A-Za-z+/]+={0,2}$/;
      const compact = text.trim();
      if (!compact || compact.length < 8 || compact.includes("\n") ||
          !base64Regex.test(compact) || compact.length % 4 !== 0) {
        return text;
      }
      try {
        const binary = atob(compact);
        const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
        let decoded = new TextDecoder().decode(bytes);
        let output = "";
        for (let i = 0; i < decoded.length; i++) {
          output += String.fromCharCode(
            decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length)
          );
        }
        return output;
      } catch (e) {
        return text;
      }
    }

    // ⭐ 增强版 m3u → txt 转换
    function convertM3UtoTXT(text) {
      text = text.replace(/\uFEFF/g, "").replace(/\r/g, "").trim();
      const lines = text.split("\n").map(l => l.trim()).filter(l => l !== "");

      let groups = {};
      let lastName = null;
      let lastGroup = "未分组";

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.startsWith("#EXTINF")) {
          const groupMatch = line.match(/group-title="([^"]+)"/);
          const nameMatch = line.match(/,(.*)$/);
          lastGroup = groupMatch ? groupMatch[1].trim() : "未分组";
          lastName = nameMatch ? nameMatch[1].trim() : "未知频道";
          if (!groups[lastGroup]) groups[lastGroup] = [];
        }

        if (line.match(/^\s*https?:\/\//i)) {
          if (lastName) {
            groups[lastGroup].push(`${lastName},${line.trim()}`);
            lastName = null;
          }
        }
      }

      let out = [];
      for (const g in groups) {
        out.push(`${g},#genre#`);
        out.push(...groups[g]);
        out.push("");
      }

      return out.join("\n");
    }

    // 多正则过滤（OR）
    function applyRegexOR(lines, regexList) {
      return lines.filter(line => regexList.some(reg => reg.test(line)));
    }

    // 多正则替换（顺序执行）
    function applyRegexReplace(lines, replaceList) {
      return lines.map(line => {
        let out = line;
        for (let { reg, replacement } of replaceList) {
          out = out.replace(reg, replacement);
        }
        return out;
      });
    }

    // 单源独立处理
    function processSingleSource(text, params) {
      text = tryDecrypt(text, params.decrypt, params.key);
      if (params.m3u) text = convertM3UtoTXT(text);

      let lines = text.split("\n");

// ⭐ 单源增强版 cut：格式 /正则1/正则2/;/正则3/正则4/
if (params.cut) {
  const segments = params.cut.split(";");   // 多段区间
  let result = [];

  for (const seg of segments) {
    if (!seg.trim()) continue;

    // 匹配 /正则1/正则2/
    const m = seg.match(/^\/(.+)\/(.+)\/$/);
    if (!m) continue;

    const r1 = new RegExp(m[1]);
    const r2 = new RegExp(m[2]);

    let startIndex = lines.findIndex(line => r1.test(line));
    let endIndex   = lines.findIndex(line => r2.test(line));

    if (startIndex !== -1 && endIndex !== -1 && endIndex >= startIndex) {
      result.push(...lines.slice(startIndex, endIndex + 1));
    }
  }

  lines = result.length > 0 ? result : [];
}


      if (params.end !== null) {
        lines = lines.slice((params.start || 1) - 1, params.end);
      }

      if (params.group) {
        lines = lines.filter(line => line.includes(params.group));
      }

      if (params.include) {
        const keys = params.include.split(";");
        lines = lines.filter(line => keys.some(k => line.includes(k)));
      }

      if (params.exclude) {
        const keys = params.exclude.split(";");
        lines = lines.filter(line => !keys.some(k => line.includes(k)));
      }

      if (params.regex) {
        const regexList = params.regex.split(";").map(r => {
          const m = r.match(/^\/(.+)\/(.*)$/);
          return new RegExp(m[1], m[2]);
        });
        lines = applyRegexOR(lines, regexList);
      }

      if (params.regex_replace) {
        const replaceList = params.regex_replace.split(";").map(r => {
          const m = r.match(/^\/(.+)\/(.*)\/$/);
          return { reg: new RegExp(m[1]), replacement: m[2] };
        });
        lines = applyRegexReplace(lines, replaceList);
      }

      if (params.strip) {
        lines = lines.map(line => {
          const idx = line.indexOf("$");
          return idx !== -1 ? line.substring(0, idx) : line;
        });
      }

      if (params.dedupe) {
        lines = [...new Set(lines)];
      }

    // ⭐ 单源新增第一行：自定义文本 + ",#genre#"
    if (params.add) {
      const newLine = `${params.add},#genre#`;
      lines.unshift(newLine);   // 插入到第一行
    }

    let out = lines.filter(line => line.trim() !== "");

    // ⭐ 单源频道名标准化（仅在 normalize=1 时启用）
    if (params.normalize) {
    out = out.map(normalizeChannelName);
    }

    // ⭐⭐⭐ multi 模式：避免重复 add，只加一次
    if (params.multi) {
      const ids = params.multi.split(";").map(s => s.trim()).filter(s => s !== "");

      // ⭐ 移除单源 add（如果存在）
      let cleaned = out.filter(line => !line.startsWith(`${params.add},#genre#`));

      let multiOut = [];

      for (const id of ids) {
        for (const line of cleaned) {
          multiOut.push(line.replace(/mg000/g, id));
        }
        multiOut.push("");
      }

      // ⭐ multi 模式下 add 只加一次
      if (params.add) {
        multiOut.unshift(`${params.add},#genre#`);
      }

      return multiOut;
    }



    return out;


    }

    // 解析 merge 参数
    const sources = mergeRaw.split(",").map(item => {
      const parts = item.split("|");
      const url = parts[0];
      let params = {
        decrypt: false,
        key: "",
        include: null,
        exclude: null,
        group: null,
        strip: false,
        start: 1,
        end: null,
        dedupe: false,
        regex: null,
        regex_replace: null,
    add: null,
    cut: null,
    normalize: false,
        m3u: false
      };

      for (let i = 1; i < parts.length; i++) {
        const [k, v] = parts[i].split("=");
        if (k === "decrypt") params.decrypt = v === "1";
        if (k === "key") params.key = v;
        if (k === "include") params.include = v;
        if (k === "exclude") params.exclude = v;
        if (k === "group") params.group = v;
        if (k === "strip") params.strip = v === "1";
        if (k === "start") params.start = parseInt(v);
        if (k === "end") params.end = parseInt(v);
        if (k === "dedupe") params.dedupe = v === "1";
        if (k === "regex") params.regex = v;
        if (k === "regex_replace") params.regex_replace = v;
        if (k === "m3u") params.m3u = v === "1";
    if (k === "add") params.add = v;   // ⭐ 单源新增行
    if (k === "cut") params.cut = v;   // ⭐ 新增：单源截取
    if (k === "normalize") params.normalize = v === "1";   // ⭐ 单源频道名标准化开关
    if (k === "multi") params.multi = v;   // ⭐ 新增：多重替换
    if (k === "multiurl") params.multiurl = true;   // ⭐ 新增：列表文件模式，无需 =xxx


      }

      return { url, params };
    });

let finalLines = [];

for (let src of sources) {

  // 读取单源 URL 内容
  let raw = await fetchTxt(src.url);

  // ⭐⭐⭐ multiurl 模式：把 raw 当作列表文件
  if (src.params.multiurl) {

    const listLines = raw.split(/\r?\n/).filter(l => l.trim() !== "");

    // ⭐ 字典（与你原来的 worker 完全一致）
    const urlDict = {
      "0": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GENRE",
      "1": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HPTYJ",
      "2": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/DLudp",
      "3": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/DLrtp",
      "4": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SYLNT",
      "5": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/template",
      "6": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/MBST",
      "7": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SHLT",
      "8": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HNLT",
      "9": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/CDDX",
      "10": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/MYDX1",
      "11": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/CQDX",
      "12": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/CQLT",
      "13": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/QHDX",
      "14": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GDDX",
      "15": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HuBDX",
      "16": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HuNDX",
      "17": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BJLT1",
      "18": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SXDX",
      "19": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SHLT1",
      "20": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HZDX1",
      "21": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/AHDX",
      "22": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JXDX",
      "23": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SCYD",
      "24": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/XJDX",
      "25": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NMGDX",
      "26": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SDLT",
      "27": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HeBDX",
      "28": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NEWL",
      "29": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BJDX",
      "30": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SSXDX1",
      "31": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/TJLT",
      "32": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HeBLT",
      "33": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HLJLT",
      "34": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NMGDX",
      "35": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HNDX",
      "36": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HNLT1",
      "37": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JSDX",
      "38": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/KSSC",
      "39": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/KSSC1",
      "40": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SCLT",
      "41": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/KSSC2",
      "42": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HTML",
      "43": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/KSSC3",
      "44": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/TW4G",
      "45": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/XYMM",
      "46": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BJYD",
      "47": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NEWTV",
      "48": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HSJC",
      "49": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BJYD1",
      "50": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/WEBV",
      "51": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HKZB",
      "52": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HKZB1",
      "53": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/WEBV1",
      "54": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/DYZB",
      "55": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GOBK1",
      "56": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/NHZB",
      "57": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JCPD",
      "58": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JCMG",
      "59": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/YSDX",
      "60": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/WSHZ",
      "61": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SZHZ",
      "62": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/DYZB1",
      "63": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/BFGD",
      "64": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT1",
      "65": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT2",
      "66": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT3",
      "67": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT4",
      "68": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYWS",
      "69": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/IHOT",
      "70": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SCDX",
      "71": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SYLT",
      "72": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT5",
      "73": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/FJLT",
      "74": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/EYHT5a",
      "75": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/YNDX",
      "76": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SHDX",
      "77": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/JLLT",
      "78": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SDDX",
      "79": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/SXLT",
      "80": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GDYD",
      "81": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GXDX",
      "82": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/ZJDX",
      "83": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HiNDX",
      "84": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/HiNLT",
      "85": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/GZDX",
      "86": "https://raw.githubusercontent.com/bankan-lichaz/Ku9-IPTV-source/refs/heads/main/zubo/FJDX"
    };

    // ⭐ 模板缓存（大幅减少 fetch 次数）
    const templateCache = {};

    let multiOutLines = [];

    for (const line of listLines) {
      const parts = line.split(",").map(s => s.trim());
      if (parts.length < 2) continue;

      const key = parts[0];
      const reps = parts.slice(1);

      // ⭐⭐⭐ 新增：特殊处理key为0的情况，直接跳过fetch逻辑
      if (key === '0') {
        const fixedTemplate = "mg000,#genre#"; // 你需要的固定内容
        // 后续替换逻辑和普通模板完全一致
        for (const rep of reps) {
          const replaced = fixedTemplate.split("mg000").join(rep);
          multiOutLines.push(...replaced.split(/\r?\n/));
        }
        continue; // 处理完当前行的所有替换后，直接处理下一行
      }

      // ⭐ 字典快捷词或直接 URL
      const targetUrl = urlDict[key] || key;

      // ⭐ 缓存模板文件，避免重复 fetch
      if (!templateCache[targetUrl]) {
        try {
          templateCache[targetUrl] = await fetchTxt(targetUrl);
        } catch (e) {
          multiOutLines.push(`# Failed to fetch ${targetUrl}`);
          continue;
        }
      }

      const templateText = templateCache[targetUrl];

      // ⭐ 对每个替换值执行 mg000 替换
      for (const rep of reps) {
        // 更快的替换方式（性能提升 3～5 倍）
        const replaced = templateText.split("mg000").join(rep);

        // 按行追加
        multiOutLines.push(...replaced.split(/\r?\n/));
      }
    }

    // ⭐ multiurl 生成的内容继续走单源处理链
    const newParams = { ...src.params };
    delete newParams.multiurl;   // 防止递归

    const generatedText = multiOutLines.join("\n");
    const processed = processSingleSource(generatedText, newParams);

    finalLines.push(...processed);
    continue;   // 进入下一个源
  }

  // ⭐ 普通单源模式
  let processed = processSingleSource(raw, src.params);
  finalLines.push(...processed);
}


    // 全局处理（不包含 m3u）
    if (g_decrypt && g_key) {
      finalLines = finalLines.map(line => tryDecrypt(line, true, g_key));
    }

// ⭐ 全局增强版 cut：格式 /正则1/正则2/;/正则3/正则4/
if (g_cut) {
  const segments = g_cut.split(";");
  let result = [];

  for (const seg of segments) {
    if (!seg.trim()) continue;

    const m = seg.match(/^\/(.+)\/(.+)\/$/);
    if (!m) continue;

    const r1 = new RegExp(m[1]);
    const r2 = new RegExp(m[2]);

    let startIndex = finalLines.findIndex(line => r1.test(line));
    let endIndex   = finalLines.findIndex(line => r2.test(line));

    if (startIndex !== -1 && endIndex !== -1 && endIndex >= startIndex) {
      result.push(...finalLines.slice(startIndex, endIndex + 1));
    }
  }

  finalLines = result.length > 0 ? result : [];
}


    if (g_end !== null) {
      finalLines = finalLines.slice(g_start - 1, g_end);
    }

    if (g_group) {
      finalLines = finalLines.filter(line => line.includes(g_group));
    }

    if (g_include) {
      const keys = g_include.split(",");
      finalLines = finalLines.filter(line => keys.some(k => line.includes(k)));
    }

    if (g_exclude) {
      const keys = g_exclude.split(",");
      finalLines = finalLines.filter(line => !keys.some(k => line.includes(k)));
    }

    if (g_regex) {
      const regexList = g_regex.split(";").map(r => {
        const m = r.match(/^\/(.+)\/(.*)$/);
        return new RegExp(m[1], m[2]);
      });
      finalLines = applyRegexOR(finalLines, regexList);
    }

    if (g_regex_replace) {
      const replaceList = g_regex_replace.split(";").map(r => {
        const m = r.match(/^\/(.+)\/(.*)\/$/);
        return { reg: new RegExp(m[1]), replacement: m[2] };
      });
      finalLines = applyRegexReplace(finalLines, replaceList);
    }

    if (g_strip) {
      finalLines = finalLines.map(line => {
        const idx = line.indexOf("$");
        return idx !== -1 ? line.substring(0, idx) : line;
      });
    }

    if (g_dedupe) {
      finalLines = [...new Set(finalLines)];
    }

// ⭐ 全局新增第一行：自定义文本 + ",#genre#"
if (g_add) {
  const newLine = `${g_add},#genre#`;
  finalLines.unshift(newLine);
}

finalLines = finalLines.filter(line => line.trim() !== "");

// ⭐ 全局频道名标准化（仅在 normalize=1 时启用）
if (g_normalize) {
  finalLines = finalLines.map(normalizeChannelName);
}


    return new Response(finalLines.join("\n"), {
      headers: { "Content-Type": "text/plain; charset=utf-8" }
    });
  }
};
