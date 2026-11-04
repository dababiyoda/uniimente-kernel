// GREG phone client core: canonical JSON and Ed25519 signing, identical to greg/founder.py.
// Pure functions over WebCrypto; runs unchanged in Safari/Chrome and in Node (for tests).
// The private key is a non-extractable CryptoKey: this code can use it, never read it.

const enc = new TextEncoder();

export const COMMAND_PREFIX = "uniimente-greg-founder-command-v1\n";
export const DEVICE_KINDS = ["DECISION", "CRITIQUE", "LIFECYCLE", "BODY_PAUSE", "BODY_RESUME", "BODY_STOP"];

export function hex(bytes) {
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

function unhex(text) {
  const out = new Uint8Array(text.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(text.slice(2 * i, 2 * i + 2), 16);
  return out;
}

// Python: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).
// JSON.stringify matches it for strings, booleans, null and safe integers; key order is made explicit.
export function canonical(value) {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) throw new Error("only safe integers are signed by the phone client");
    return String(value);
  }
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (typeof value === "object") {
    // Python sorts by code point; for the ASCII keys GREG uses this equals UTF-16 order.
    return "{" + Object.keys(value).sort().map((k) => JSON.stringify(k) + ":" + canonical(value[k])).join(",") + "}";
  }
  throw new Error("value is not canonical JSON");
}

export async function keyId(publicRaw) {
  const digest = await crypto.subtle.digest("SHA-256", publicRaw);
  return "ed25519:" + hex(digest).slice(0, 32);
}

export async function newDeviceKey() {
  const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, false, ["sign", "verify"]);
  const raw = await crypto.subtle.exportKey("raw", pair.publicKey);
  return { privateKey: pair.privateKey, publicKey: pair.publicKey, publicHex: hex(raw), keyId: await keyId(raw) };
}

function stamp(date) {
  return date.toISOString().replace(/\.\d{3}Z$/, (m) => m); // e.g. 2026-09-26T01:02:03.456Z
}

function nonce() {
  return hex(crypto.getRandomValues(new Uint8Array(16)));
}

export async function signCommand(device, { kind, body, bodyId, now = new Date(), ttlSeconds = 600 }) {
  if (!DEVICE_KINDS.includes(kind)) throw new Error(`a device key may not sign ${kind}`);
  const envelope = {
    version: 1, kind, body_id: bodyId, founder_key_id: device.keyId,
    issued_at: stamp(now), expires_at: stamp(new Date(now.getTime() + ttlSeconds * 1000)),
    nonce: nonce(), body,
  };
  const signature = await crypto.subtle.sign("Ed25519", device.privateKey, enc.encode(COMMAND_PREFIX + canonical(envelope)));
  return { ...envelope, signature: hex(signature) };
}

export async function signRead(device, { bodyId, method, path, now = new Date() }) {
  const at = stamp(now);
  const message = `uniimente-greg-read-v1\n${bodyId}\n${method}\n${path}\n${at}`;
  const signature = await crypto.subtle.sign("Ed25519", device.privateKey, enc.encode(message));
  return { "X-Greg-Key": device.keyId, "X-Greg-Time": at, "X-Greg-Signature": hex(signature) };
}

export async function verifyCommand(publicKey, envelope) { // used by tests for symmetry
  const { signature, ...unsigned } = envelope;
  return crypto.subtle.verify("Ed25519", publicKey, unhex(signature), enc.encode(COMMAND_PREFIX + canonical(unsigned)));
}

// Python's sorted() order for keys: by code point, where JavaScript's default sort compares UTF-16 units.
const codePoints = (s) => Array.from(s, (c) => c.codePointAt(0));
function byCodePoint(a, b) {
  const x = codePoints(a), y = codePoints(b);
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
}

// One ask value as every answer surface prints it; greg/console.py _shown prints the same text.
export function shownValue(v) {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return "null";
  if (Array.isArray(v)) return v.map(shownValue).join(", ");
  if (typeof v === "object") return "{" + Object.keys(v).sort(byCodePoint).map((k) => `${k}: ${shownValue(v[k])}`).join(", ") + "}";
  return String(v);
}

// What approving one APPROVAL covers: the scope its digest binds. The same sentence as greg/console.py
// approval_covers; display only, the answer binds the digest.
function approvalCovers(r) {
  const cost = (r.authority_requested || {}).cost_usd, p = r.bound_params;
  const parts = [...(r.mission_id ? [`mission ${r.mission_id}`] : []), "the capability, target, consequence class and cost above"];
  if (typeof cost === "number" && cost > 0) parts.push("the mission's spend and budget when it was asked (one paid approval funds one run)");
  if (p !== null && typeof p === "object" && typeof p.json === "string") {
    const shownLength = codePoints(p.json).length, whole = p.length === shownLength;
    const size = whole ? shownValue(p.length) : `the first ${shownLength} of ${shownValue(p.length)}`;
    parts.push(`params ${p.json}${whole ? "" : "…"} (${size} characters of canonical JSON, ${shownValue(p.sha256)})`);
  } else {
    parts.push("params: not recorded with this ask");
  }
  // A compensation ask's approve runs the compensation signed with the action, never the action again.
  const asked = !r.action_id ? "" : r.compensation === true ? ` Asked to compensate action ${r.action_id}.`
    : ` Asked for action ${r.action_id}.`;
  return "Approving covers this exact scope: " + parts.join("; ") + "." + asked;
}

// What the founder reads before answering one ask, in the console's order (greg/console.py _ask_details): a
// malformed scope first, every key the ask requests, what approving an APPROVAL covers, and what silence does.
// Pure, so node tests it without a browser.
export function askTerms(r) {
  const requested = r.authority_requested || {};
  const rest = Object.entries(requested).filter(([k]) => k !== "malformed");
  const lines = [];
  if ("malformed" in requested) lines.push("This scope is malformed: " + shownValue(requested.malformed));
  if (rest.length) lines.push("Authority requested: " + rest.map(([k, v]) => `${k}: ${shownValue(v)}`).join("; "));
  if (r.kind === "APPROVAL") lines.push(approvalCovers(r));
  if (r.consequence_of_no_response) lines.push("If you do not answer: " + r.consequence_of_no_response);
  return lines;
}

// The answers the body accepts for this ask, as [label, answer] (greg/missions.py MissionEngine.answer refuses
// approve/reject on a RECONCILIATION, and every answer on an ask no DECISION closes).
export function askAnswers(r) {
  if (r.answerable === false) return [];
  if (r.kind === "RECONCILIATION") return [["It happened", "reconcile_executed"], ["It did not happen", "reconcile_not_executed"]];
  return [["Approve", "approve"], ["Reject", "reject"]];
}
