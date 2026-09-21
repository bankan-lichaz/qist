function tvboxBytes(value) {
  return new TextEncoder().encode(value);
}

function tvboxHex(bytes) {
  return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}

function tvboxFromHex(hex) {
  if (!/^[0-9a-f]+$/i.test(hex) || hex.length % 2) {
    throw new Error("Invalid TVBox hex data");
  }
  return Uint8Array.from(hex.match(/../g), byte => parseInt(byte, 16));
}

function tvboxWord(value) {
  // Match tvbox.py: right-pad key and IV with ASCII zeroes to 16 bytes.
  return tvboxBytes((value + "0000000000000000").slice(0, 16));
}

async function tvboxKey(value) {
  return crypto.subtle.importKey(
    "raw",
    tvboxWord(value),
    { name: "AES-CBC" },
    false,
    ["encrypt", "decrypt"]
  );
}

function tvboxJsonValue(text) {
  const value = text.trim();
  try {
    return JSON.parse(value);
  } catch (_) {
    // Allow merged plain text too. It is encoded as a JSON string so the
    // output remains compatible with the TVBox AES format.
    return text;
  }
}

async function tvboxEncrypt(text, key, iv) {
  if (!key || !iv) throw new Error("TVBox encryption requires key and iv");

  const plaintext = tvboxBytes(JSON.stringify(tvboxJsonValue(text), null, 2));
  const encrypted = await crypto.subtle.encrypt(
    { name: "AES-CBC", iv: tvboxWord(iv) },
    await tvboxKey(key),
    plaintext
  );

  const header = tvboxHex(tvboxBytes(`$#${key}#$`));
  const cipher = tvboxHex(new Uint8Array(encrypted));
  const ivHex = tvboxHex(tvboxBytes(iv));
  return header + cipher + ivHex;
}

async function tvboxDecrypt(text) {
  const input = text.replace(/^\/\/.*$/gm, "").trim();
  if (!input) return input;

  // Plain JSON is already decrypted.
  try {
    return JSON.stringify(JSON.parse(input), null, 2);
  } catch (_) {
    // Continue with TVBox hex parsing.
  }

  if (!/^[0-9a-f]+$/i.test(input) || input.length % 2) {
    throw new Error("Content is neither JSON nor TVBox hex data");
  }

  const marker = input.indexOf(tvboxHex(tvboxBytes("#$")));
  if (marker < 0) throw new Error("TVBox header was not found");

  const headerEnd = marker + 4;
  const ivHex = input.slice(-26);
  const cipherHex = input.slice(headerEnd, -26);
  const realKey = new TextDecoder().decode(tvboxFromHex(input.slice(0, headerEnd))).slice(2, -2);
  const realIv = new TextDecoder().decode(tvboxFromHex(ivHex));

  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-CBC", iv: tvboxWord(realIv) },
    await tvboxKey(realKey),
    tvboxFromHex(cipherHex)
  );
  const decoded = new TextDecoder().decode(decrypted);

  try {
    const value = JSON.parse(decoded);
    return typeof value === "string" ? value : JSON.stringify(value, null, 2);
  } catch (_) {
    return decoded;
  }
}

function xorDecrypt(text, enabled, key) {
  if (!enabled || !key) return text;
  const compact = text.trim();
  if (!compact || compact.length < 8 || /\s/.test(compact) ||
      !/^[0-9A-Za-z+/]+={0,2}$/.test(compact) || compact.length % 4 !== 0) return text;
  try {
    const binary = atob(compact);
    let output = "";
    for (let i = 0; i < binary.length; i++) {
      output += String.fromCharCode(binary.charCodeAt(i) ^ key.charCodeAt(i % key.length));
    }
    return output;
  } catch (_) { return text; }
}

function sourceParams(parts) {
  const p = { decrypt:false, key:"", include:null, exclude:null, group:null, strip:false, start:1, end:null, dedupe:false, tvbox:null, tvboxKey:"", tvboxIv:"" };
  for (const item of parts.slice(1)) {
    const pos = item.indexOf("=");
    const k = pos < 0 ? item : item.slice(0, pos);
    const v = pos < 0 ? "" : item.slice(pos + 1);
    if (k === "decrypt") p.decrypt = v === "1";
    else if (k === "key") p.key = v;
    else if (k === "include") p.include = v;
    else if (k === "exclude") p.exclude = v;
    else if (k === "group") p.group = v;
    else if (k === "strip") p.strip = v === "1";
    else if (k === "start") p.start = Number.parseInt(v, 10) || 1;
    else if (k === "end") p.end = Number.parseInt(v, 10) || null;
    else if (k === "dedupe") p.dedupe = v === "1";
    else if (k === "tvbox") p.tvbox = v === "1" ? 1 : v === "0" ? 0 : null;
    else if (k === "tvboxKey" || k === "tvkey") p.tvboxKey = v;
    else if (k === "tvboxIv" || k === "tviv") p.tvboxIv = v;
  }
  return p;
}

async function processLines(text, p) {
  if (p.tvbox === 0) text = await tvboxDecrypt(text);
  text = xorDecrypt(text, p.decrypt, p.key);

  let lines = text.split(/\r?\n/);
  if (p.end !== null) lines = lines.slice(Math.max(0, p.start - 1), p.end);
  if (p.group) lines = lines.filter(x => x.includes(p.group));
  if (p.include) { const keys = p.include.split(/[;,]/).filter(Boolean); lines = lines.filter(x => keys.some(k => x.includes(k))); }
  if (p.exclude) { const keys = p.exclude.split(/[;,]/).filter(Boolean); lines = lines.filter(x => !keys.some(k => x.includes(k))); }
  if (p.strip) lines = lines.map(x => { const i = x.indexOf("$"); return i < 0 ? x : x.slice(0, i); });
  if (p.dedupe) lines = [...new Set(lines)];

  lines = lines.filter(x => x.trim());
  if (p.tvbox === 1) {
    const encrypted = await tvboxEncrypt(lines.join("\n"), p.tvboxKey || p.key, p.tvboxIv || p.key);
    return [encrypted];
  }
  return lines;
}

function globalParams(url) {
  const tvbox = url.searchParams.get("tvbox");
  return {
    include:url.searchParams.get("include"), exclude:url.searchParams.get("exclude"), group:url.searchParams.get("group"),
    strip:url.searchParams.get("strip") === "1", dedupe:url.searchParams.get("dedupe") === "1",
    start:Number.parseInt(url.searchParams.get("start"),10) || 1,
    end:url.searchParams.has("end") ? Number.parseInt(url.searchParams.get("end"),10) : null,
    decrypt:url.searchParams.get("decrypt") === "1", key:url.searchParams.get("key") || "",
    tvbox:tvbox === "1" ? 1 : tvbox === "0" ? 0 : null,
    tvboxKey:url.searchParams.get("tvboxKey") || url.searchParams.get("tvkey") || url.searchParams.get("key") || "",
    tvboxIv:url.searchParams.get("tvboxIv") || url.searchParams.get("tviv") || url.searchParams.get("key") || ""
  };
}

async function mergeResponse(request) {
  const url = new URL(request.url);
  const merge = url.searchParams.get("merge");
  if (!merge) return new Response("Missing merge parameter", { status:400 });

  const sources = merge.split(",").map(item => item.split("|")).filter(parts => parts[0]);
  let finalLines = [];
  for (const parts of sources) {
    const response = await fetch(parts[0]);
    if (!response.ok) continue;
    finalLines.push(...await processLines(await response.text(), sourceParams(parts)));
  }

  const p = globalParams(url);
  if (p.tvbox === 0) {
    const joined = finalLines.join("\n");
    try {
      finalLines = (await tvboxDecrypt(joined)).split(/\r?\n/).filter(x => x.trim());
    } catch (_) {
      const decrypted = [];
      for (const line of finalLines) {
        try { decrypted.push(await tvboxDecrypt(line)); } catch (_) { decrypted.push(line); }
      }
      finalLines = decrypted;
    }
  }

  if (p.decrypt && p.key) finalLines = finalLines.map(x => xorDecrypt(x, true, p.key));
  if (p.end !== null && Number.isFinite(p.end)) finalLines = finalLines.slice(Math.max(0, p.start - 1), p.end);
  if (p.group) finalLines = finalLines.filter(x => x.includes(p.group));
  if (p.include) { const keys = p.include.split(",").filter(Boolean); finalLines = finalLines.filter(x => keys.some(k => x.includes(k))); }
  if (p.exclude) { const keys = p.exclude.split(",").filter(Boolean); finalLines = finalLines.filter(x => !keys.some(k => x.includes(k))); }
  if (p.strip) finalLines = finalLines.map(x => { const i = x.indexOf("$"); return i < 0 ? x : x.slice(0, i); });
  if (p.dedupe) finalLines = [...new Set(finalLines)];

  finalLines = finalLines.filter(x => x.trim());
  let output = finalLines.join("\n");
  if (p.tvbox === 1) output = await tvboxEncrypt(output, p.tvboxKey, p.tvboxIv);

  return new Response(output, { headers:{"Content-Type":"text/plain; charset=utf-8","Access-Control-Allow-Origin":"*"} });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (!url.searchParams.has("merge")) return new Response("Missing merge parameter", { status:400 });
    try { return await mergeResponse(request); }
    catch (error) { return new Response("Worker error: " + error.message, { status:502 }); }
  }
};
