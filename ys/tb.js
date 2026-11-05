// Cloudflare Worker entry point: tb.py processing plus wk.js-compatible TVBox AES-CBC.
// TVBox parameters are global query parameters:
//   ?source=<url>|...&tvbox=1&tvboxKey=<key>&tvboxIv=<iv>  encrypt response
//   ?source=<url>|...&tvbox=0                              decrypt response (key/IV are read from payload)
// Core source fetching/filtering remains in tb-worker.js.
import core from "./tb-worker.js";

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function word(value) {
  return encoder.encode((String(value) + "0000000000000000").slice(0, 16));
}
function toHex(bytes) {
  return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
}
function fromHex(hex) {
  if (!/^[\da-f]+$/i.test(hex) || hex.length % 2) throw new Error("Invalid TVBox hex data");
  return Uint8Array.from(hex.match(/../g), pair => parseInt(pair, 16));
}
async function importAesKey(key) {
  return crypto.subtle.importKey("raw", word(key), { name: "AES-CBC" }, false, ["encrypt", "decrypt"]);
}
function jsonValue(value) {
  try { return JSON.parse(value.trim()); } catch { return value; }
}
async function tvboxEncrypt(value, key, iv) {
  if (!key || !iv) throw new Error("TVBox encryption requires tvboxKey and tvboxIv");
  const plain = JSON.stringify(jsonValue(value), null, 2);
  const encrypted = await crypto.subtle.encrypt({ name: "AES-CBC", iv: word(iv) }, await importAesKey(key), encoder.encode(plain));
  return toHex(encoder.encode(`$#${key}#$`)) + toHex(new Uint8Array(encrypted)) + toHex(encoder.encode(iv));
}
async function tvboxDecrypt(input) {
  const value = String(input).replace(/^\/\/.*$/gm, "").trim();
  if (!value) return value;
  try { return JSON.stringify(JSON.parse(value), null, 2); } catch {}
  if (!/^[\da-f]+$/i.test(value) || value.length % 2) throw new Error("Content is neither JSON nor TVBox hex data");
  const marker = value.indexOf(toHex(encoder.encode("#$")));
  if (marker < 0) throw new Error("TVBox header was not found");
  const headerEnd = marker + 4;
  // wk.js TVBox payloads append a 13-character timestamp/IV value as hex.
  const ivHexLength = 26;
  if (value.length < headerEnd + ivHexLength) throw new Error("Invalid TVBox payload");
  const key = decoder.decode(fromHex(value.slice(0, headerEnd))).slice(2, -2);
  const iv = decoder.decode(fromHex(value.slice(-ivHexLength)));
  const cipher = fromHex(value.slice(headerEnd, -ivHexLength));
  const plain = await crypto.subtle.decrypt({ name: "AES-CBC", iv: word(iv) }, await importAesKey(key), cipher);
  const decoded = decoder.decode(plain);
  try {
    const parsed = JSON.parse(decoded);
    return typeof parsed === "string" ? parsed : JSON.stringify(parsed, null, 2);
  } catch { return decoded; }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const mode = url.searchParams.get("tvbox");
    const key = url.searchParams.get("tvboxKey") || "";
    const iv = url.searchParams.get("tvboxIv") || "";

    const response = await core.fetch(request, env, ctx);
    if (!response.ok || (mode !== "0" && mode !== "1")) return response;

    try {
      const body = await response.text();
      let output;
      if (mode === "1") {
        output = await tvboxEncrypt(body, key, iv);
      } else {
        try {
          output = await tvboxDecrypt(body);
        } catch (wholeBodyError) {
          // Match wk.js fallback: attempt to decode each line independently.
          const decodedLines = [];
          for (const line of body.split(/\r?\n/)) {
            try { decodedLines.push(await tvboxDecrypt(line)); }
            catch { decodedLines.push(line); }
          }
          output = decodedLines.join("\n");
          if (output === body) throw wholeBodyError;
        }
      }
      return new Response(output, {
        status: response.status,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Access-Control-Allow-Origin": "*"
        }
      });
    } catch (error) {
      return new Response("tvbox: " + (error?.message || String(error)), {
        status: 400,
        headers: { "Content-Type": "text/plain; charset=utf-8", "Access-Control-Allow-Origin": "*" }
      });
    }
  }
};
