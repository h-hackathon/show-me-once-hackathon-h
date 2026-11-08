// Page d'enregistrement SMO : enregistrer écran + voix, transcrire en direct (Gladia), envoyer, suivre le pipeline.
"use strict";

const $ = (id) => document.getElementById(id);
const STATE_LABEL = { pending: "à venir", running: "en cours", done: "fait", waiting: "en attente",
                      failed: "échec", skipped: "sauté", blocked: "bloqué" };
let config = { stages: [], live: false, site_url: null };
let token = "";
try { token = localStorage.getItem("smo-token") || ""; } catch { /* stockage indisponible */ }

// --- API ---------------------------------------------------------------------------------------

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers["X-SMO-Token"] = token;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) { $("token-box").hidden = false; throw new Error("Jeton SMO requis"); }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* réponse non JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

$("token-box").addEventListener("submit", (e) => {
  e.preventDefault();
  token = $("token").value.trim();
  try { localStorage.setItem("smo-token", token); } catch { /* stockage indisponible */ }
  location.reload();
});

// --- vues ----------------------------------------------------------------------------------------

const STEPS = ["prepare", "record", "learn", "agent"];

function show(view, step) {
  for (const section of document.querySelectorAll(".view")) section.hidden = section.id !== `view-${view}`;
  const current = STEPS.indexOf(step);
  for (const li of document.querySelectorAll(".stepper li")) {
    const i = STEPS.indexOf(li.dataset.step);
    li.dataset.state = i < current ? "done" : i === current ? "current" : "todo";
  }
}

// --- 1. préparer ---------------------------------------------------------------------------------

const form = $("prepare-form");

// Site web : son adresse ; appli de bureau : le nom de la fenêtre déjà ouverte (un agent H différent par type).
function syncKind() {
  const desktop = form.software_kind.value === "desktop";
  $("url-label").textContent = desktop ? "Nom de l'application ouverte" : "Adresse du logiciel";
  form.url.type = desktop ? "text" : "url";
  form.url.placeholder = desktop ? "COMPTAREX Cabinet 6.2" : "https://…";
  if (desktop && form.url.value === config.site_url) form.url.value = "";
  if (!desktop && !form.url.value && config.site_url) form.url.value = config.site_url;
}
for (const radio of form.querySelectorAll('input[name="software_kind"]')) radio.addEventListener("change", syncKind);

form.addEventListener("submit", (e) => {
  e.preventDefault();
  $("prepare-error").hidden = true;
  if (!form.reportValidity()) return;
  startRecording().catch((err) => fail(`Impossible de démarrer : ${err.message}`));
});

function fail(message) {
  show("prepare", "prepare");
  $("prepare-error").textContent = message;
  $("prepare-error").hidden = false;
}

// --- 2. enregistrer ------------------------------------------------------------------------------

let recorder = null, chunks = [], tracks = [], cancelled = false, timerId = null, started = 0;
let live = { ws: null, ctx: null, proc: null };

async function startRecording() {
  let display, mic;
  try {
    display = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 15 }, audio: false });
  } catch {
    return fail("Partage d'écran refusé : choisissez l'écran ou la fenêtre du logiciel, puis « Partager ».");
  }
  try {
    mic = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  } catch {
    display.getTracks().forEach((t) => t.stop());
    return fail("Micro refusé : autorisez le micro pour que votre voix soit enregistrée.");
  }
  tracks = [...display.getTracks(), ...mic.getTracks()];
  const stream = new MediaStream([...display.getVideoTracks(), ...mic.getAudioTracks()]);
  const mimeType = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"]
    .find((m) => MediaRecorder.isTypeSupported(m));
  recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 2_500_000 });
  chunks = [];
  cancelled = false;
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = () => { stopLive(); tracks.forEach((t) => t.stop()); if (!cancelled) upload(); };
  display.getVideoTracks()[0].addEventListener("ended", stopRecording);   // « Arrêter le partage » de Chrome
  // micro pris par une autre app ou casque déconnecté : la vidéo continue sans la voix, il faut le voir tout de suite
  const voice = mic.getAudioTracks()[0];
  voice.addEventListener("mute", () => liveStatus("micro coupé : votre voix n'est plus enregistrée", false));
  voice.addEventListener("unmute", () => liveStatus("micro rétabli", true));
  voice.addEventListener("ended", () => liveStatus("micro perdu : arrêtez et recommencez l'enregistrement", false));
  recorder.start(1000);

  $("rec-task").textContent = form.task.value;
  $("live-text").innerHTML = '<p class="placeholder">Parlez : vos phrases apparaissent ici.</p>';
  started = Date.now();
  timerId = setInterval(tick, 250);
  tick();
  show("record", "record");
  startLive(mic).catch((err) => liveStatus(`indisponible : ${err.message}`, false));
}

function tick() {
  const s = Math.floor((Date.now() - started) / 1000);
  $("timer").textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function stopRecording() {
  clearInterval(timerId);
  if (recorder && recorder.state !== "inactive") recorder.stop();
}

$("stop").addEventListener("click", stopRecording);
$("cancel").addEventListener("click", () => { cancelled = true; stopRecording(); show("prepare", "prepare"); });

// Transcription en direct : le serveur ouvre la session Gladia, le navigateur envoie le son du micro
// (PCM 16 bits, 16 kHz, mono) à l'URL à jeton renvoyée ; la clé Gladia reste sur le serveur.
function liveStatus(text, ok) {
  const el = $("live-status");
  el.textContent = text;
  el.dataset.ok = ok === undefined ? "" : String(ok);
}

async function startLive(mic) {
  if (!config.live) return liveStatus("désactivée (GLADIA_API_KEY absente)", false);
  const { url } = await api("/api/live", { method: "POST" });
  const ws = new WebSocket(url);
  const ctx = new AudioContext({ sampleRate: 16000 });
  const source = ctx.createMediaStreamSource(new MediaStream(mic.getAudioTracks()));
  const proc = ctx.createScriptProcessor(4096, 1, 1);
  proc.onaudioprocess = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const input = e.inputBuffer.getChannelData(0);
    const pcm = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const v = Math.max(-1, Math.min(1, input[i]));
      pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
    }
    ws.send(pcm.buffer);
  };
  source.connect(proc);
  proc.connect(ctx.destination);   // nécessaire pour que le traitement tourne ; la sortie reste silencieuse
  ws.onopen = () => liveStatus("connectée", true);
  ws.onerror = () => liveStatus("connexion perdue", false);
  ws.onmessage = (event) => {
    let message;
    try { message = JSON.parse(event.data); } catch { return; }
    if (message.type === "transcript" && message.data?.utterance) showUtterance(message.data);
  };
  live = { ws, ctx, proc };
}

function showUtterance(data) {
  const box = $("live-text");
  box.querySelector(".placeholder")?.remove();
  let line = document.getElementById(`u-${data.id}`);
  if (!line) {
    line = document.createElement("p");
    line.id = `u-${data.id}`;
    box.append(line);
  }
  line.textContent = data.utterance.text;
  line.classList.toggle("partial", !data.is_final);
  box.scrollTop = box.scrollHeight;
}

function stopLive() {
  try { if (live.ws?.readyState === WebSocket.OPEN) live.ws.send(JSON.stringify({ type: "stop_recording" })); } catch { /* déjà fermée */ }
  live.proc?.disconnect();
  live.ctx?.close().catch(() => {});
  live = { ws: null, ctx: null, proc: null };
}

// --- envoi -----------------------------------------------------------------------------------

function upload() {
  const blob = new Blob(chunks, { type: "video/webm" });
  const body = new FormData();
  body.append("video", blob, "capture.webm");
  for (const name of ["task", "url", "software_kind", "software_name"]) body.append(name, form[name].value);
  show("upload", "record");
  $("upload-note").textContent = `${(blob.size / 1e6).toFixed(1)} Mo`;

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/captures");
  if (token) xhr.setRequestHeader("X-SMO-Token", token);
  xhr.upload.onprogress = (e) => {
    if (!e.lengthComputable) return;
    const pct = Math.round((e.loaded / e.total) * 100);
    $("upload-bar").style.width = `${pct}%`;
    $("upload-note").textContent = `${pct} % · ${(e.loaded / 1e6).toFixed(1)} / ${(e.total / 1e6).toFixed(1)} Mo`;
  };
  xhr.onload = () => {
    if (xhr.status >= 300) return fail(`Envoi refusé par le serveur (HTTP ${xhr.status}).`);
    follow(JSON.parse(xhr.responseText).run_id);
  };
  xhr.onerror = () => fail("Envoi impossible : le serveur SMO ne répond pas.");
  xhr.send(body);
}

// --- 3-4. suivre ---------------------------------------------------------------------------------

let pollId = null, editorMode = null;   // editorMode : "review" ou "retry" une fois la Skill chargée dans l'éditeur

function follow(runId) {
  history.replaceState(null, "", `?run=${encodeURIComponent(runId)}`);
  editorMode = null;
  show("follow", "learn");
  poll(runId);
}

async function poll(runId) {
  clearTimeout(pollId);
  let run;
  try {
    run = await api(`/api/runs/${encodeURIComponent(runId)}`);
  } catch (err) {
    $("log").textContent = `Suivi impossible : ${err.message}`;
    pollId = setTimeout(() => poll(runId), 5000);
    return;
  }
  render(run);
  if (run.busy || run.state === "running") pollId = setTimeout(() => poll(runId), 2000);
}

const PILL = {
  running: ["En cours", "run"], done: ["Agent prêt", "ok"], failed: ["Échec", "ko"],
  blocked: ["Réglage manquant", "ko"], idle: ["En pause", ""],
};

function waitingLabel(run) {
  if (run.status.review?.state === "waiting" && !run.approved) return ["À relire", "act"];
  if (run.status.trial?.state === "waiting") return ["Essais sans succès", "act"];
  if (run.status.upgrade?.state === "waiting") return ["PR à fusionner", "act"];
  return ["En attente", "act"];
}

function render(run) {
  $("follow-title").textContent = run.meta.task;
  $("follow-meta").textContent = [run.meta.software_name, run.meta.software_url].filter(Boolean).join(" · ");
  const [label, tone] = run.state === "waiting" ? waitingLabel(run) : PILL[run.state] || [run.state, ""];
  const pill = $("follow-state");
  pill.textContent = label;
  pill.dataset.tone = tone;
  show("follow", run.approved ? "agent" : "learn");

  const list = $("stages");
  list.replaceChildren(...config.stages.map(({ name, label }) => {
    const st = run.status[name] || {};
    const state = st.state || "pending";
    const li = document.createElement("li");
    li.className = "stage";
    li.dataset.state = state;
    li.innerHTML = '<span class="dot"></span><span class="label"></span><span class="state"></span>';
    li.querySelector(".label").textContent = label;
    li.querySelector(".state").textContent = STATE_LABEL[state] || state;
    const missing = st.missing && (state === "skipped" ? `optionnelle (${st.missing.join(", ")} absente)`
                                                       : `à renseigner : ${st.missing.join(", ")}`);
    const detail = st.error || missing || (st.seconds && `${st.seconds} s`);
    if (detail) {
      const d = document.createElement("span");
      d.className = "detail";
      d.textContent = detail;
      li.append(d);
    }
    return li;
  }));

  // Éditeur de Skill : à la relecture, ou après 3 essais ratés (la Skill contient alors les leçons des essais).
  const reviewing = run.status.review?.state === "waiting" && !run.approved && run.skill;
  const retrying = !run.busy && run.status.trial?.state === "waiting" && run.skill;
  const mode = reviewing ? "review" : retrying ? "retry" : null;
  $("review").hidden = !mode;
  if (mode && editorMode !== mode) {
    $("skill").value = run.skill;
    $("trial-message").value = run.trial_request.message;
    $("trial-files").value = "";
    editorMode = mode;
  }
  const attached = run.trial_request.files;
  $("trial-files-note").textContent = attached.length ? `Déjà jointes : ${attached.join(", ")}` : "";
  if (mode === "retry") {
    $("review-title").textContent = "L'agent n'a pas réussi en 3 essais";
    $("review-note").textContent = "Ses leçons sont à la fin de la Skill. Corrigez ce qui bloque, puis relancez les essais.";
    $("approve").textContent = "Relancer les essais";
  }
  $("resume").hidden = run.busy || !["failed", "waiting", "idle"].includes(run.state) || Boolean(mode);
  $("stop-run").hidden = !run.busy;

  renderLinks(run.links || {}, run.attempts || []);
  $("log").textContent = run.log.length ? run.log.join("\n") : "—";
  $("approve").onclick = () => (mode === "retry" ? retry(run.id) : approve(run.id));
  $("resume").onclick = () => resume(run.id);
  $("stop-run").onclick = () => stopRun(run.id);
}

function renderLinks(links, attempts) {
  const rows = [];
  if (links.map) rows.push(["Cartographie", anchor(links.map, "revoir la session")]);
  if (links.agent) rows.push(["Agent dans H", code(links.agent)]);
  if (links.agent) rows.push(["Mode", document.createTextNode(links.tool_ready ? "tool + reprise à l'écran" : "à l'écran (tool en préparation)")]);
  for (const a of attempts) {
    const cell = document.createElement("span");
    cell.append(a.success ? "réussi" : `raté${a.gap ? ` : ${a.gap}` : ""}`);
    if (a.replay) cell.append(" · ", anchor(a.replay, "revoir"));
    rows.push([`Essai ${a.n}`, cell]);
  }
  if (links.devin) rows.push(["Devin", anchor(links.devin, "voir la session")]);
  if (links.pr) rows.push(["Pull request", anchor(links.pr, links.pr.replace(/^https:\/\/github\.com\//, ""))]);
  const report = links.devin_report;
  if (report) {
    const verdict = `tests ${report.tests_passed ? "verts" : "rouges"} · ${report.merged ? "fusionné, déploiement en cours" : "pas fusionné"}`;
    rows.push(["Devin", document.createTextNode(report.issues?.length ? `${verdict} · ${report.issues.join(" ; ")}` : verdict)]);
  }
  $("links").hidden = rows.length === 0;
  $("link-list").replaceChildren(...rows.flatMap(([term, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.append(value);
    return [dt, dd];
  }));
}

function code(text) { const c = document.createElement("code"); c.textContent = text; return c; }
function anchor(href, text) {
  const a = document.createElement("a");
  a.href = href; a.textContent = text; a.target = "_blank"; a.rel = "noopener";
  return a;
}

// La Skill et la demande d'essai (texte + pièces jointes) relues, avant de lancer ou relancer les essais.
async function saveReview(runId) {
  await api(`/api/runs/${encodeURIComponent(runId)}/skill`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ skill: $("skill").value }),
  });
  const body = new FormData();
  body.append("message", $("trial-message").value);
  for (const file of $("trial-files").files) body.append("files", file);
  await api(`/api/runs/${encodeURIComponent(runId)}/trial-request`, { method: "PUT", body });
}

async function approve(runId) {
  const button = $("approve");
  button.disabled = true;
  try {
    await saveReview(runId);
    await api(`/api/runs/${encodeURIComponent(runId)}/approve`, { method: "POST" });
    poll(runId);
  } catch (err) {
    $("log").textContent = `Validation impossible : ${err.message}`;
  } finally {
    button.disabled = false;
  }
}

async function retry(runId) {
  const button = $("approve");
  button.disabled = true;
  try {
    await saveReview(runId);
    editorMode = null;
    await resume(runId);
  } catch (err) {
    $("log").textContent = `Relance impossible : ${err.message}`;
  } finally {
    button.disabled = false;
  }
}

async function resume(runId) {
  try { await api(`/api/runs/${encodeURIComponent(runId)}/resume`, { method: "POST" }); poll(runId); }
  catch (err) { $("log").textContent = `Relance impossible : ${err.message}`; }
}

async function stopRun(runId) {
  if (!confirm("Arrêter ce run ? La session H en cours est annulée ; « Relancer » reprendra où il en était.")) return;
  try { await api(`/api/runs/${encodeURIComponent(runId)}/stop`, { method: "POST" }); poll(runId); }
  catch (err) { $("log").textContent = `Arrêt impossible : ${err.message}`; }
}

// Retour au formulaire : le run suivi reste tel quel (son lien ?run=… le rouvre).
$("new-demo").addEventListener("click", () => {
  clearTimeout(pollId);
  editorMode = null;
  history.replaceState(null, "", location.pathname);
  show("prepare", "prepare");
});

// --- démarrage -----------------------------------------------------------------------------------

(async function boot() {
  show("prepare", "prepare");
  try {
    config = await api("/api/config");
  } catch (err) {
    return fail(`Serveur SMO injoignable : ${err.message}`);
  }
  if (config.site_url && !form.url.value) form.url.value = config.site_url;
  const runId = new URLSearchParams(location.search).get("run");
  if (runId) follow(runId);
})();
