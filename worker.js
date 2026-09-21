const HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TVBox Merge Worker</title>
<style>
body{font:15px system-ui,sans-serif;background:#101827;color:#e5e7eb;max-width:1100px;margin:25px auto;padding:0 14px}section{background:#182235;border:1px solid #334155;border-radius:10px;padding:18px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}label{display:block;font-weight:600;margin:8px 0 5px}input,textarea,button{width:100%;box-sizing:border-box;padding:10px;border:1px solid #475569;border-radius:6px;background:#0f172a;color:#e5e7eb;font:inherit}textarea{min-height:130px;resize:vertical}.checks{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}.checks label{font-weight:400;margin:0}.checks input{width:auto;margin-right:5px}button{background:#2563eb;border:0;cursor:pointer;font-weight:700;margin-top:12px}button:hover{background:#1d4ed8}iframe{width:100%;height:350px;background:#fff;border:1px solid #475569;border-radius:6px}code{color:#93c5fd}@media(max-width:700px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>TVBox merge worker</h1>
<p>Enter one source per line. Per-source options use <code>URL|group=News|strip=1</code>. Global options apply after all sources are merged.</p>
<section>
<label for="sources">Sources</label>
<textarea id="sources" placeholder="https://example.com/one.txt\nhttps://example.com/two.txt|group=News|strip=1"></textarea>
<div class="grid">
<div><label for="include">Global include</label><input id="include" placeholder="News,HD"></div>
<div><label for="exclude">Global exclude</label><input id="exclude" placeholder="広告,测试"></div>
<div><label for="group">Global group</label><input id="group"></div>
<div><label for="key">Global decrypt key</label><input id="key"></div>
<div><label for="start">Global start</label><input id="start" type="number" min="1" value="1"></div>
<div><label for="end">Global end</label><input id="end" type="number" min="1" placeholder="optional"></div>
</div>
<div class="checks">
<label><input id="strip" type="checkbox"> Global strip after $</label>
<label><input id="dedupe" type="checkbox"> Global deduplicate</label>
<label><input id="decrypt" type="checkbox"> Global XOR decrypt</label>
</div>
<button id="run" type="button">Merge and show result</button>
<div id="status">Ready.</div>
</section>
<section>
<label for="result">Result</label>
<textarea id="result" readonly></textarea>
<label>Result frame</label>
<iframe id="frame" sandbox></iframe>
</section>
<script>
const $=id=>document.getElementById(id);
function add(p,k,v){if(v!==null&&v!==undefined&&v!==''&&v!==false)p.set(k,String(v));}
function makeUrl(){
 const p=new URLSearchParams();
 const sources=$("sources").value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);
 if(!sources.length)throw Error('Enter at least one source URL');
 p.set('merge',sources.join(','));
 add(p,'include',$("include").value.trim()); add(p,'exclude',$("exclude").value.trim()); add(p,'group',$("group").value.trim());
 add(p,'key',$("key").value); add(p,'start',$("start").value||'1'); add(p,'end',$("end").value);
 if($("strip").checked)p.set('strip','1'); if($("dedupe").checked)p.set('dedupe','1'); if($("decrypt").checked)p.set('decrypt','1');
 return '?' + p.toString();
}
$("run").onclick=async()=>{try{$("status").textContent='Fetching and processing...';const r=await fetch(makeUrl());const t=await r.text();if(!r.ok)throw Error(t||r.statusText);$("result").value=t;const esc=t.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');$("frame").srcdoc='<pre style="white-space:pre-wrap;overflow-wrap:anywhere;padding:14px">'+esc+'</pre>';$('status').textContent='Done: '+t.split(/\\n/).filter(Boolean).length+' lines';}catch(e){$('status').textContent='Error: '+e.message;$('result').value='';$('frame').srcdoc='';}};
</script>
</body>
</html>`;

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
  const p = { decrypt:false, key:"", include:null, exclude:null, group:null, strip:false, start:1, end:null, dedupe:false };
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
  }
  return p;
}

function processLines(text, p) {
  let lines = xorDecrypt(text, p.decrypt, p.key).split(/\r?\n/);
  if (p.end !== null) lines = lines.slice(Math.max(0, p.start - 1), p.end);
  if (p.group) lines = lines.filter(x => x.includes(p.group));
  if (p.include) { const keys = p.include.split(/[;,]/).filter(Boolean); lines = lines.filter(x => keys.some(k => x.includes(k))); }
  if (p.exclude) { const keys = p.exclude.split(/[;,]/).filter(Boolean); lines = lines.filter(x => !keys.some(k => x.includes(k))); }
  if (p.strip) lines = lines.map(x => { const i = x.indexOf("$"); return i < 0 ? x : x.slice(0, i); });
  if (p.dedupe) lines = [...new Set(lines)];
  return lines.filter(x => x.trim());
}

function globalParams(url) {
  return {
    include:url.searchParams.get("include"), exclude:url.searchParams.get("exclude"), group:url.searchParams.get("group"),
    strip:url.searchParams.get("strip") === "1", dedupe:url.searchParams.get("dedupe") === "1",
    start:Number.parseInt(url.searchParams.get("start"),10) || 1,
    end:url.searchParams.has("end") ? Number.parseInt(url.searchParams.get("end"),10) : null,
    decrypt:url.searchParams.get("decrypt") === "1", key:url.searchParams.get("key") || ""
  };
}

async function mergeResponse(request) {
  const url = new URL(request.url);
  const merge = url.searchParams.get("merge");
  if (!merge) return new Response("Missing merge parameter", { status:400 });
  const sources = merge.split(",").map(item => item.split("|")).filter(parts => parts[0]);
  const finalLines = [];
  for (const parts of sources) {
    const response = await fetch(parts[0]);
    if (!response.ok) continue;
    finalLines.push(...processLines(await response.text(), sourceParams(parts)));
  }
  const p = globalParams(url);
  let lines = p.decrypt && p.key ? finalLines.map(x => xorDecrypt(x, true, p.key)) : finalLines;
  if (p.end !== null && Number.isFinite(p.end)) lines = lines.slice(Math.max(0, p.start - 1), p.end);
  if (p.group) lines = lines.filter(x => x.includes(p.group));
  if (p.include) { const keys = p.include.split(",").filter(Boolean); lines = lines.filter(x => keys.some(k => x.includes(k))); }
  if (p.exclude) { const keys = p.exclude.split(",").filter(Boolean); lines = lines.filter(x => !keys.some(k => x.includes(k))); }
  if (p.strip) lines = lines.map(x => { const i = x.indexOf("$"); return i < 0 ? x : x.slice(0, i); });
  if (p.dedupe) lines = [...new Set(lines)];
  return new Response(lines.filter(x => x.trim()).join("\n"), { headers:{"Content-Type":"text/plain; charset=utf-8","Access-Control-Allow-Origin":"*"} });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.searchParams.has("merge")) {
      try { return await mergeResponse(request); }
      catch (error) { return new Response("Worker error: " + error.message, { status:502 }); }
    }
    return new Response(HTML, { headers:{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store"} });
  }
};
