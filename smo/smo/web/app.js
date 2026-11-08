// Page d'enregistrement SMO : enregistrer écran + voix, transcrire en direct (Gladia), envoyer, suivre le pipeline.
"use strict";

const $ = (id) => document.getElementById(id);
const H_AGENTS = "https://platform.hcompany.ai/agents";   // l'agent s'utilise dans H, pas dans cette page
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

// step : l'étape en cours du bandeau, ou "end" quand tout est fait.
function show(view, step) {
  for (const section of document.querySelectorAll(".view")) section.hidden = section.id !== `view-${view}`;
  $("new-demo").hidden = view !== "follow";   // dans le bandeau, sur tous les écrans de suivi
  const current = step === "end" ? STEPS.length : STEPS.indexOf(step);
  for (const li of document.querySelectorAll(".stepper li")) {
    const i = STEPS.indexOf(li.dataset.step);
    li.dataset.state = i < current ? "done" : i === current ? "current" : "todo";
  }
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function anchor(href, text, className) {
  const a = el("a", className, text);
  a.href = href; a.target = "_blank"; a.rel = "noopener";
  return a;
}

function duration(seconds) {
  const s = Math.round(seconds);
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min${s % 60 ? ` ${String(s % 60).padStart(2, "0")}` : ""}`;
}

// --- 1. préparer ---------------------------------------------------------------------------------

const form = $("prepare-form");

// Les conseils derrière le (i) : une carte courte, ouverte à la demande.
function setTips(open) {
  $("tips").hidden = !open;
  $("tips-toggle").setAttribute("aria-expanded", String(open));
}
$("tips-toggle").addEventListener("click", () => setTips($("tips").hidden));
$("tips-close").addEventListener("click", () => { setTips(false); $("tips-toggle").focus(); });

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

// Une automatisation existe déjà pour cette tâche (même nom ou proche) : l'améliorer, ou en faire une nouvelle.
// La page le demande avant d'enregistrer, sinon la démo écraserait l'agent existant sans le dire.
let existing = null;   // null : pas encore vérifié pour ce titre et ce type ; sinon la liste trouvée dans H

async function findExisting() {
  const query = new URLSearchParams({ task: form.task.value.trim(), kind: form.software_kind.value });
  const timeout = new AbortController();
  setTimeout(() => timeout.abort(), 2500);   // le partage d'écran doit partir dans la foulée du clic
  try {
    return (await api(`/api/existing?${query}`, { signal: timeout.signal })).candidates;
  } catch {
    return [];   // H injoignable : on n'empêche pas d'enregistrer
  }
}

function existingChoice(value, title, detail, checked) {
  const label = el("label", "choice");
  const radio = el("input");
  radio.type = "radio"; radio.name = "existing-choice"; radio.value = value; radio.checked = checked;
  label.append(radio, title);
  return detail ? [label, el("p", "note", detail)] : [label];
}

function showExisting(candidates) {
  const exact = candidates.find((c) => c.exact);
  const nodes = candidates.flatMap((c) => existingChoice(c.name, `Améliorer « ${c.task} »`,
    `${c.name} · ${c.has_tool ? "avec son tool" : "à l'écran, sans tool"}. La démo met à jour cet agent et sa Skill` +
    (c.has_tool ? " ; Devin met à jour son tool." : "."), c === (exact || candidates[0])));
  nodes.push(...existingChoice("", "Nouvelle tâche",
    exact ? "Changez alors le titre ci-dessus : ce nom est déjà pris." : "Un autre agent, à côté de l'existant.", false));
  $("existing-choices").replaceChildren(...nodes);
  $("existing").hidden = false;
  $("record-btn").textContent = "Continuer et enregistrer";
}

function resetExisting() {
  existing = null;
  form.improves.value = "";
  $("existing").hidden = true;
  $("record-btn").textContent = "Choisir l'écran et enregistrer";
}
form.task.addEventListener("input", resetExisting);
for (const radio of form.querySelectorAll('input[name="software_kind"]')) radio.addEventListener("change", resetExisting);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  $("prepare-error").hidden = true;
  if (!form.reportValidity()) return;
  if (existing === null) {
    existing = await findExisting();
    if (existing.length) return showExisting(existing);   // le choix d'abord ; le clic suivant lance l'enregistrement
  }
  const picked = form.querySelector('input[name="existing-choice"]:checked')?.value || "";
  const chosen = existing.find((c) => c.name === picked);
  if (chosen) {
    form.task.value = chosen.task;   // même titre, donc même agent, même Skill, même tool
  } else if (existing.some((c) => c.exact)) {
    $("prepare-error").textContent = "Nouvelle tâche : donnez-lui un autre titre, celui-ci est déjà pris.";
    $("prepare-error").hidden = false;
    return form.task.focus();
  }
  form.improves.value = chosen ? chosen.name : "";
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

// Chrome nomme la piste partagée : titre de l'onglet ou de la fenêtre, « screen:… » pour un écran entier.
function shareLabel(label) {
  if (!label || label.startsWith("screen:")) return "Écran partagé : écran entier";
  return `Écran partagé : ${label}`;
}

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
  const screen = display.getVideoTracks()[0];
  screen.addEventListener("ended", stopRecording);   // « Arrêter le partage » de Chrome
  // micro pris par une autre app ou casque déconnecté : la vidéo continue sans la voix, il faut le voir tout de suite
  const voice = mic.getAudioTracks()[0];
  voice.addEventListener("mute", () => liveStatus("micro coupé, votre voix n'est plus enregistrée", false));
  voice.addEventListener("unmute", () => liveStatus("micro rétabli", true));
  voice.addEventListener("ended", () => liveStatus("micro perdu, arrêtez et recommencez", false));
  recorder.start(1000);

  $("rec-task").textContent = [form.task.value, form.software_name.value.trim(), form.improves.value && "amélioration"]
    .filter(Boolean).join(" · ");
  $("share-label").textContent = shareLabel(screen.label);
  $("live-text").replaceChildren(el("li", "placeholder", "Parlez : vos phrases apparaissent ici."));
  $("live-count").textContent = "";
  started = Date.now();
  timerId = setInterval(tick, 250);
  tick();
  show("record", "record");
  startLive(mic).catch((err) => liveStatus(`indisponible (${err.message})`, false));
}

function clock(ms) {
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function tick() {
  $("timer").textContent = clock(Date.now() - started);
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
  const chip = $("live-status");
  chip.textContent = `Transcription : ${text}`;
  chip.dataset.ok = ok === undefined ? "" : String(ok);
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

// Une ligne par phrase, horodatée à son apparition ; la phrase en cours reste grisée jusqu'à sa version finale.
function showUtterance(data) {
  const box = $("live-text");
  box.querySelector(".placeholder")?.remove();
  let line = document.getElementById(`u-${data.id}`);
  if (!line) {
    line = el("li");
    line.id = `u-${data.id}`;
    line.append(el("span", "at", clock(Date.now() - started)), el("span", "said"));
    box.append(line);
  }
  line.querySelector(".said").textContent = data.utterance.text;
  line.classList.toggle("partial", !data.is_final);
  const finals = box.querySelectorAll("li:not(.partial):not(.placeholder)").length;
  $("live-count").textContent = finals ? `${finals} phrase${finals > 1 ? "s" : ""}` : "";
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
  for (const name of ["task", "url", "software_kind", "software_name", "improves"]) body.append(name, form[name].value);
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
let attachedFiles = [];                 // les pièces jointes déjà envoyées pour la demande d'essai

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

// Les 13 étapes du pipeline, regroupées en 5 phases lisibles ; les partenaires en étiquettes.
const PHASES = [
  { key: "learn", label: "Comprendre la démonstration", short: "Comprendre", tags: ["H", "Holo", "Gladia", "Linkup"],
    stages: ["map", "docs", "transcribe", "frames", "read", "understand", "enrich", "skill"] },
  { key: "review", label: "Relire la Skill", short: "Relire", tags: ["Vous"], stages: ["review"] },
  { key: "trial", label: "Essayer la tâche à l'écran", short: "Essayer", tags: ["H"], stages: ["provision", "trial"] },
  { key: "compile", label: "Coder le tool", short: "Coder le tool", tags: ["Devin"], stages: ["compile"] },
  { key: "upgrade", label: "Outiller l'agent", short: "Outiller l'agent", tags: ["H"], stages: ["upgrade"] },
];

function phaseOf(run, phase) {
  const sts = phase.stages.map((n) => run.status[n] || {});
  const states = sts.map((st) => st.state || "pending");
  const seconds = sts.reduce((sum, st) => sum + (st.seconds || 0), 0);
  const problem = sts.find((st) => ["failed", "blocked"].includes(st.state));
  let state = "pending";
  if (problem) state = problem.state;
  else if (states.includes("running")) state = "running";
  else if (states.includes("waiting")) state = "waiting";
  else if (states.every((s) => s === "done" || s === "skipped")) state = "done";
  else if (run.busy && states.some((s) => s === "done")) state = "running";
  const missing = problem?.missing?.length ? `à renseigner : ${problem.missing.join(", ")}` : "";
  return { ...phase, state, seconds, error: problem?.error || missing };
}

function stateText(p) {
  if (p.state === "done") return p.key === "review" ? "validée" : p.seconds ? `fait · ${duration(p.seconds)}` : "fait";
  if (p.state === "waiting") return { review: "à vous", trial: "à reprendre", compile: "en attente" }[p.key] || "en attente";
  return { running: "en cours", failed: "échec", blocked: "réglage manquant", pending: "à venir" }[p.state] || p.state;
}

function tagList(tags) {
  const box = el("span", "tags");
  for (const t of tags) box.append(el("span", "tag", t));
  return box;
}

function renderRail(phases) {
  $("rail").replaceChildren(...phases.map((p) => {
    const li = el("li");
    li.dataset.state = p.state;
    if (["running", "waiting"].includes(p.state)) li.setAttribute("aria-current", "step");
    const head = el("span", "rail-head", p.short);
    const short = p.state === "done" && p.key !== "review" && p.seconds   // la barre est étroite : « 41 s », « 16 min »
      ? (p.seconds < 60 ? `${Math.round(p.seconds)} s` : `${Math.round(p.seconds / 60)} min`) : stateText(p);
    head.append(el("span", "rail-state", short));
    li.append(el("span", "rail-bar"), head, el("span", "rail-tags", p.tags.join(" · ")));
    return li;
  }));
}

// Le détail sous une phase : ce qui se passe, et de quoi le suivre en direct.
function phaseDetail(p, run) {
  const links = run.links || {};
  const box = el("div", "phase-box");
  const actions = el("div", "actions");
  if (p.key === "trial" && p.state === "running") {
    const n = (run.attempts || []).length + 1;
    box.append(el("p", "strong", `Essai ${n} sur 3`),
               el("p", null, "L'agent lit la pièce, ouvre le logiciel et fait la tâche. Il s'arrête avant de finaliser."));
    if (links.live) actions.append(anchor(links.live, "Regarder l'agent en direct ↗", "btn primary"));
    if (run.busy) actions.append(stopButton(run.id));
  } else if (p.key === "compile" && ["running", "waiting"].includes(p.state)) {
    box.append(el("p", "strong", "Devin écrit le tool"),
               el("p", null, "Un programme qui fait la même saisie que l'essai réussi, en quelques secondes. 10 à 15 min en général."));
    const checks = el("ol", "checks");
    checks.append(check(Boolean(links.devin), "Session Devin ouverte"),
                  check(Boolean(links.pr), "Pull request ouverte : le tool et ses tests"),
                  check(Boolean(links.devin_report?.merged), "Tests verts et fusion, puis déploiement"));
    box.append(checks);
    if (links.devin) actions.append(anchor(links.devin, "Suivre Devin en direct ↗", "btn primary"));
    if (links.pr) actions.append(anchor(links.pr, "Voir la pull request ↗", "btn ghost"));
  } else if (p.key === "upgrade" && p.state === "waiting") {
    box.append(el("p", "strong", "Tool pas encore en ligne"),
               el("p", null, "En attendant, votre agent fait la tâche à l'écran : c'est plus lent, le résultat est le même."));
    for (const issue of links.devin_report?.issues || []) box.append(el("p", "note", issue));
  } else {
    return null;
  }
  if (actions.childElementCount) box.append(actions);
  return box;
}

function phaseNote(p, run) {
  const links = run.links || {};
  if (p.error) return el("span", "detail error", p.error);
  if (p.key === "trial" && p.state === "done") {
    const ok = (run.attempts || []).find((a) => a.success);
    const span = el("span", "detail", `Réussi${ok ? ` à l'essai ${ok.n}` : ""}`);
    if (links.trial_answer?.reference) span.append(` : ${links.trial_answer.reference}, sans validation`);
    if (ok?.replay) span.append(" · ", anchor(ok.replay, "revoir"));
    return span;
  }
  if (p.key === "compile" && p.state === "done" && links.pr) {
    const report = links.devin_report;
    const span = el("span", "detail", report ? `tests ${report.tests_passed ? "verts" : "rouges"} · ${report.merged ? "fusionné" : "pas fusionné"} · ` : "");
    span.append(anchor(links.pr, links.pr.replace(/^https:\/\/github\.com\//, "")));
    return span;
  }
  if (p.state === "pending") {
    const hint = { compile: "Dès qu'un essai réussit, Devin écrit un tool qui fera la même saisie en quelques secondes.",
                   upgrade: "Tool d'abord, écran en secours." }[p.key];
    return hint ? el("span", "detail", hint) : null;
  }
  return null;
}

function check(done, text) {
  const li = el("li", done ? "done" : "", text);
  li.prepend(el("span", "check", done ? "✓" : ""));
  return li;
}

function stopButton(runId) {
  const b = el("button", "btn ghost", "Arrêter");
  b.type = "button";
  b.onclick = () => stopRun(runId);
  return b;
}

function renderPhases(phases, run) {
  $("phases").replaceChildren(...phases.map((p) => {
    const li = el("li", "phase");
    li.dataset.state = p.state;
    if (["running", "waiting"].includes(p.state)) li.setAttribute("aria-current", "step");
    li.append(el("span", "dot"), el("span", "label", p.label), el("span", "state", stateText(p)), tagList(p.tags));
    const note = phaseNote(p, run);
    if (note) li.append(note);
    const box = phaseDetail(p, run);
    if (box) li.append(box);
    return li;
  }));
}

const PILL = { done: ["Agent prêt", "ok"], failed: ["Échec", "ko"], blocked: ["Réglage manquant", "ko"], idle: ["En pause", ""] };
const RUNNING = { learn: "Analyse en cours", trial: "Essai en cours", compile: "Devin code le tool", upgrade: "Mise à jour de l'agent" };

function pillFor(run, phases) {
  if (run.state === "waiting") {
    if (run.status.review?.state === "waiting" && !run.approved) return ["À relire", "act"];
    if (run.status.trial?.state === "waiting") return ["Essais sans succès", "act"];
    if (run.status.upgrade?.state === "waiting") return ["Tool en attente", "act"];
    return ["En attente", "act"];
  }
  if (run.state === "running") return [RUNNING[phases.find((p) => p.state === "running")?.key] || "En cours", "run"];
  return PILL[run.state] || [run.state, ""];
}

function render(run) {
  const phases = PHASES.map((p) => phaseOf(run, p));
  const links = run.links || {};
  const finished = run.state === "done";
  $("follow-title").textContent = run.meta.task;
  $("follow-meta").textContent = [run.meta.software_name, run.meta.software_url].filter(Boolean).join(" · ");
  const [label, tone] = pillFor(run, phases);
  $("follow-state").textContent = label;
  $("follow-state").dataset.tone = tone;
  show("follow", finished ? "end" : run.approved ? "agent" : "learn");
  renderRail(phases);

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
  attachedFiles = run.trial_request.files;
  renderFiles(attachedFiles);
  if (mode === "retry") {
    $("review-title").textContent = "L'agent n'a pas réussi en 3 essais";
    $("review-note").textContent = "Ses leçons sont à la fin de la Skill. Corrigez ce qui bloque, puis relancez les essais.";
    $("approve").textContent = "Relancer les essais";
  }

  renderReady(run, finished);
  $("work").hidden = Boolean(mode) || finished;
  renderPhases(phases, run);
  $("request-card").hidden = !run.approved;
  $("request-message").textContent = run.trial_request.message;
  $("request-files").replaceChildren(...run.trial_request.files.map((name) => fileChip(name)));
  $("agent-card").hidden = !links.agent;
  $("agent-name").textContent = links.agent || "";
  $("agent-mode").textContent = links.tool_ready ? "Tool d'abord, écran en secours."
    : run.status.trial?.state === "done" ? "Il marche déjà, à l'écran ; il passera au tool dès son déploiement."
    : "À l'écran pour l'instant ; il recevra son tool après les essais.";
  $("agent-open").href = H_AGENTS;
  $("resume").hidden = run.busy || !["failed", "waiting", "idle"].includes(run.state) || Boolean(mode);
  $("stop-run").hidden = !run.busy || phases.some((p) => p.key === "trial" && p.state === "running");

  renderLinks(links, run.attempts || []);
  $("log").textContent = run.log.length ? run.log.join("\n") : "—";
  $("approve").onclick = () => (mode === "retry" ? retry(run.id) : approve(run.id));
  $("resume").onclick = () => resume(run.id);
  $("stop-run").onclick = () => stopRun(run.id);
}

// Écran final : l'agent se fait essayer dans H (lien), avec la phrase à lui écrire et ce qu'il a déjà prouvé.
function renderReady(run, finished) {
  const links = run.links || {};
  $("ready").hidden = !finished;
  $("ready-tiles").hidden = !finished;
  if (!finished) return;
  $("ready-agent").textContent = links.agent || "";
  $("ready-request").textContent = run.trial_request.message;
  $("ready-open").href = H_AGENTS;
  const tool = $("ready-tool");
  tool.replaceChildren();
  if (links.tool_ready) {
    tool.className = "";
    tool.append(el("p", "strong", "Tool d'abord"), el("p", "note", "Il fait la tâche avec le tool codé par Devin, en quelques secondes, une pièce à la fois."));
  } else {
    tool.className = "warn";
    tool.append(el("p", "strong", "Tool pas encore en ligne"), el("p", "note", "En attendant, il fait la tâche à l'écran : c'est plus lent, le résultat est le même."));
  }
  const ok = (run.attempts || []).find((a) => a.success);
  const report = links.devin_report;
  const tiles = [
    ["H · à l'écran", ok ? `Essai réussi` : "Essai", links.trial_answer?.reference ? `${links.trial_answer.reference}, enregistré sans validation.` : "", ok?.replay && anchor(ok.replay, "Revoir l'essai")],
    ["Devin", "Tool codé", report ? `Tests ${report.tests_passed ? "verts" : "rouges"}, ${report.merged ? "fusionné" : "pas fusionné"}.` : "", links.pr && anchor(links.pr, "Voir la pull request")],
    ["En ligne", links.tool_ready ? "Tool déployé et vérifié" : "Tool en attente", links.tool_ready ? "L'interface a été contrôlée avant de donner le tool à l'agent." : "L'agent travaille à l'écran en attendant.", null],
  ];
  $("ready-tiles").replaceChildren(...tiles.map(([kicker, title, text, link]) => {
    const card = el("section", "card tile");
    card.append(el("p", "kicker", kicker), el("h3", null, title));
    if (text) card.append(el("p", "note", text));
    if (link) card.append(link);
    return card;
  }));
}

function renderLinks(links, attempts) {
  const rows = [];
  if (links.map) rows.push(["Cartographie", anchor(links.map, "revoir la session")]);
  if (links.agent) rows.push(["Agent dans H", code(links.agent)]);
  for (const a of attempts) {
    const cell = el("span");
    cell.append(a.success ? "réussi" : `raté${a.gap ? ` : ${a.gap}` : ""}`);
    if (a.replay) cell.append(" · ", anchor(a.replay, "revoir"));
    rows.push([`Essai ${a.n}`, cell]);
  }
  if (links.devin) rows.push(["Devin", anchor(links.devin, "voir la session")]);
  if (links.pr) rows.push(["Pull request", anchor(links.pr, links.pr.replace(/^https:\/\/github\.com\//, ""))]);
  for (const issue of links.devin_report?.issues || []) rows.push(["Devin signale", document.createTextNode(issue)]);
  $("link-list").hidden = rows.length === 0;
  $("link-list").replaceChildren(...rows.flatMap(([term, value]) => {
    const dd = el("dd");
    dd.append(value);
    return [el("dt", null, term), dd];
  }));
}

function code(text) { return el("code", null, text); }

function fileChip(name, size) {
  const li = el("li", "file", name);
  if (size) li.append(el("span", "note", ` ${Math.max(1, Math.round(size / 1000))} Ko`));
  return li;
}

// Pièces jointes : les nouvelles (choisies ou glissées) remplacent celles déjà envoyées, à l'enregistrement.
function renderFiles(attached) {
  const picked = [...$("trial-files").files];
  $("trial-files-list").replaceChildren(...(picked.length ? picked.map((f) => fileChip(f.name, f.size)) : attached.map((n) => fileChip(n))));
  $("trial-files-note").textContent = picked.length ? (attached.length ? "Elles remplaceront les pièces déjà jointes." : "")
                                                    : attached.length ? "Déjà jointes." : "";
}

const drop = $("dropzone");
for (const type of ["dragenter", "dragover"]) drop.addEventListener(type, (e) => { e.preventDefault(); drop.dataset.over = "true"; });
for (const type of ["dragleave", "drop"]) drop.addEventListener(type, () => { delete drop.dataset.over; });
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  if (!e.dataTransfer?.files.length) return;
  $("trial-files").files = e.dataTransfer.files;
  $("trial-files").dispatchEvent(new Event("change"));
});
$("trial-files").addEventListener("change", () => renderFiles(attachedFiles));

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
    $("trial-files").value = "";
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
    $("trial-files").value = "";
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
for (const button of document.querySelectorAll(".js-new-demo")) {
  button.addEventListener("click", () => {
    clearTimeout(pollId);
    editorMode = null;
    history.replaceState(null, "", location.pathname);
    resetExisting();   // l'agent de la démo précédente existe peut-être maintenant
    show("prepare", "prepare");
  });
}

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
