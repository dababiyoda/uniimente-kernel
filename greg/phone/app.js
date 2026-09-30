// GREG phone client UI. Holds one non-extractable device key in IndexedDB and talks to
// `greg serve` over the same origin. Every read and every command is signed on the phone;
// the body re-verifies everything and remains the only writer of its history.
import { newDeviceKey, signCommand, signRead } from "./core.js";

const $ = (id) => document.getElementById(id);
let device = null;
let bodyId = null;

function db() {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open("greg-phone", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("keys");
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(open.error);
  });
}

async function loadKey() {
  const store = (await db()).transaction("keys").objectStore("keys");
  return new Promise((resolve) => { const get = store.get("device"); get.onsuccess = () => resolve(get.result || null); });
}

async function saveKey(key) {
  const tx = (await db()).transaction("keys", "readwrite");
  tx.objectStore("keys").put(key, "device");
  return new Promise((resolve, reject) => { tx.oncomplete = resolve; tx.onerror = () => reject(tx.error); });
}

async function api(path) {
  const headers = await signRead(device, { bodyId, method: "GET", path });
  const response = await fetch(path, { headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.status);
  return data;
}

async function send(kind, body) {
  const envelope = await signCommand(device, { kind, body, bodyId });
  const response = await fetch("/api/command", { method: "POST", body: JSON.stringify(envelope),
                                                 headers: { "Content-Type": "application/json" } });
  const data = await response.json();
  note(response.ok ? `${kind} signed on this phone and delivered; the body verifies it next.` : `Refused: ${data.error}`);
  setTimeout(refresh, 1500);
  return data;
}

function note(text) { $("note").textContent = text; }

function el(tag, text, cls) { const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; }

function renderDecisions(list) {
  const box = $("decisions");
  box.replaceChildren();
  if (!list.length) { box.append(el("p", "Nothing needs your decision.", "muted")); return; }
  for (const r of list) {
    const card = el("article", null, "card");
    card.dataset.requestId = r.request_id;
    card.append(el("h3", `${r.kind} · ${r.mission_id}`), el("p", r.why_now), el("p", "Recommendation: " + r.recommendation, "muted"));
    const reason = el("input"); reason.placeholder = "reason (optional)"; reason.setAttribute("aria-label", "reason");
    const approve = el("button", "Approve"); approve.className = "approve";
    const reject = el("button", "Reject"); reject.className = "reject";
    approve.onclick = () => send("DECISION", { request_id: r.request_id, answer: "approve", reason: reason.value });
    reject.onclick = () => send("DECISION", { request_id: r.request_id, answer: "reject", reason: reason.value });
    card.append(reason, el("div", null, "row")); card.lastChild.append(approve, reject);
    box.append(card);
  }
}

async function refresh() {
  try {
    const status = (await api("/api/status")).data;
    const hb = status.background || {};
    $("state").textContent = `${hb.state || "unknown"} · boots ${status.boots} · chain ${status.security.chain_verified ? "verified" : "BROKEN"}`;
    $("goals").replaceChildren(...status.goals.map((g) => el("li", `${g.mission_id}: ${g.achieved ? "achieved" : g.closure}`)));
    renderDecisions((await api("/api/decisions")).data);
    const v = await api("/api/vepmc");
    $("vepmc").textContent = `VEPMC ${v.VEPMC}` + v.missions.map((m) => ` · ${m.mission_id} missing ${m.missing.join(", ") || "nothing"}`).join("");
    $("who").textContent = "Signed in as " + (await api("/api/commands")).principal;
  } catch (e) {
    $("state").textContent = "Not authorized yet: " + e.message;
  }
}

async function main() {
  bodyId = (await (await fetch("/api/hello")).json()).body_id;
  device = await loadKey();
  if (!device) { device = await newDeviceKey(); await saveKey(device); }
  $("pubkey").textContent = device.publicHex;
  $("enroll").textContent = `greg device enroll --pubkey ${device.publicHex} --label phone --key ~/.greg-founder.pem`;
  $("pause").onclick = () => send("BODY_PAUSE", {});
  $("resume").onclick = () => send("BODY_RESUME", {});
  $("stop").onclick = () => { if (confirm("Stop GREG? It stays stopped until restarted on the Mac.")) send("BODY_STOP", {}); };
  $("refresh").onclick = refresh;
  document.body.dataset.ready = "true";
  await refresh();
}

main().catch((e) => { note("Startup failed: " + e.message); });
