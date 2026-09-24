export default {
  async fetch(request) {
    const requestUrl = new URL(request.url);
    const { searchParams } = requestUrl;

    // merge 内部的 URL 可能包含未编码的 &，因此不能直接使用 searchParams.get("merge")。
    // 以 ~ 作为全局参数分隔符，先从原始 query 中取出完整的 merge 内容。
    const rawQuery = requestUrl.search.slice(1);
    const rawMergeMatch = rawQuery.match(/(?:^|&)merge=([^~]*)/);
    let mergeValue = rawMergeMatch
      ? rawMergeMatch[1]
      : searchParams.get("merge");

    if (mergeValue !== null) {
      try {
        // 兼容 merge 内 URL 中的 %26、%7C 等编码字符。
        mergeValue = decodeURIComponent(mergeValue.replace(/\+/g, "%20"));
      } catch (e) {
        // URL 编码不完整时保留原始值，避免整个请求失败。
      }
    }

    // 自动识别浏览器编码的 %7C → |
    const [mergeRaw, ...globalParts] = mergeValue?.split("~") || [];
    if (!mergeRaw) {
      return new Response("Missing merge parameter");
    }

    // 全局参数使用 ~ 分隔，例如：
    // ?merge=url1,url2~include=央视~dedupe=1
    const globalParams = new URLSearchParams(globalParts.join("&"));
    const g_include = globalParams.get("include");
    const g_exclude = globalParams.get("exclude");
    const g_group = globalParams.get("group");
    const g_strip = globalParams.get("strip") === "1";
    const g_dedupe = globalParams.get("dedupe") === "1";
    const g_start = parseInt(globalParams.get("start")) || 1;
    const g_end = globalParams.get("end") ? parseInt(globalParams.get("end")) : null;
    const g_decrypt = globalParams.get("decrypt") === "1";
    const g_key = globalParams.get("key") || "";
    const g_regex = globalParams.get("regex");
    const g_regex_replace = globalParams.get("regex_replace");

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

    // 从 JSON 中提取字段。json=video 会递归查找 video，
    // 因此可以处理示例中的 data.video；也支持 json=data.video。
    function extractJsonValue(text, path) {
      try {
        const data = JSON.parse(text.replace(/^\uFEFF/, "").trim());
        const keys = path.split(".").filter(Boolean);

        if (keys.length > 1) {
          let value = data;
          for (const key of keys) {
            if (value === null || value === undefined ||
                !Object.prototype.hasOwnProperty.call(Object(value), key)) {
              return "";
            }
            value = value[key];
          }
          return value === null || value === undefined
            ? ""
            : typeof value === "object" ? JSON.stringify(value) : String(value);
        }

        function findValue(value, key) {
          if (value === null || value === undefined || typeof value !== "object") {
            return undefined;
          }
          if (Object.prototype.hasOwnProperty.call(value, key)) {
            return value[key];
          }
          for (const child of Object.values(value)) {
            const found = findValue(child, key);
            if (found !== undefined) return found;
          }
          return undefined;
        }

        const value = findValue(data, keys[0]);
        return value === null || value === undefined
          ? ""
          : typeof value === "object" ? JSON.stringify(value) : String(value);
      } catch (e) {
        return "";
      }
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

      if (params.json) {
        text = extractJsonValue(text, params.json);
      }

      if (params.m3u) text = convertM3UtoTXT(text);

      let lines = text.split("\n");

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

      return lines.filter(line => line.trim() !== "");
    }

    // 解析 merge 参数
    const sources = mergeRaw.replace(/%7C/gi, "|").split(",").map(item => {
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
        m3u: false,
        json: null
      };

      for (let i = 1; i < parts.length; i++) {
        const [k, ...valueParts] = parts[i].split("=");
        const v = valueParts.join("=");
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
        if (k === "json") params.json = v;
      }

      return { url, params };
    });

    let finalLines = [];

    for (let src of sources) {
      let raw = await fetchTxt(src.url);
      let processed = processSingleSource(raw, src.params);
      finalLines.push(...processed);
    }

    // 全局处理（不包含 m3u）
    if (g_decrypt && g_key) {
      finalLines = finalLines.map(line => tryDecrypt(line, true, g_key));
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

    finalLines = finalLines.filter(line => line.trim() !== "");

    return new Response(finalLines.join("\n"), {
      headers: { "Content-Type": "text/plain; charset=utf-8" }
    });
  }
};
