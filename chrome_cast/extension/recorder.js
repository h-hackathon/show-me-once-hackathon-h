// Show Me Once — page recorder (onglet épinglé).
// Capture l'écran (getDisplayMedia) + micro, garde les événements reçus du service worker,
// puis envoie le tout au backend FastAPI à l'arrêt.

const $ = (id) => document.getElementById(id);
const log = (m) => { $("log").textContent = `[${new Date().toLocaleTimeString()}] ${m}\n` + $("log").textContent; };

let displayStream, micStream, mixedStream, audioCtx;
let videoRec, audioRec;
let videoChunks = [], audioChunks = [];
let events = [];
let t0 = null;

function pickMime(candidates) { return candidates.find((m) => MediaRecorder.isTypeSupported(m)) || ""; }

async function getSettings() {
  const { backendUrl = "http://localhost:8000", apiKey = "" } = await chrome.storage.local.get(["backendUrl", "apiKey"]);
  return { backendUrl: backendUrl.replace(/\/$/, ""), apiKey };
}

async function start() {
  $("start").disabled = true;
  try {
    displayStream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: 15, width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: $("sysaudio").checked,
      selfBrowserSurface: "exclude",
      surfaceSwitching: "include",
      monitorTypeSurfaces: "include",
    });
  } catch (e) {
    log("Partage d'écran annulé : " + e.message);
    $("start").disabled = false;
    return;
  }

  if ($("mic").checked) {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      log("Micro refusé (" + e.message + "). On continue sans narration.");
    }
  }

  // Mixage micro + son système dans une seule piste audio
  audioCtx = new AudioContext();
  const dest = audioCtx.createMediaStreamDestination();
  let hasAudio = false;
  for (const s of [micStream, displayStream]) {
    if (s && s.getAudioTracks().length) { audioCtx.createMediaStreamSource(s).connect(dest); hasAudio = true; }
  }

  const tracks = [...displayStream.getVideoTracks()];
  if (hasAudio) tracks.push(...dest.stream.getAudioTracks());
  mixedStream = new MediaStream(tracks);

  $("preview").srcObject = displayStream;
  $("preview").style.display = "block";

  videoChunks = []; audioChunks = []; events = [];
  videoRec = new MediaRecorder(mixedStream, {
    mimeType: pickMime(["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"]),
    videoBitsPerSecond: 2_500_000,
  });
  videoRec.ondataavailable = (e) => e.data.size && videoChunks.push(e.data);

  if (hasAudio) {
    // Piste audio séparée et légère : c'est elle qu'on envoie à Gladia
    audioRec = new MediaRecorder(dest.stream, { mimeType: pickMime(["audio/webm;codecs=opus", "audio/webm"]) });
    audioRec.ondataavailable = (e) => e.data.size && audioChunks.push(e.data);
  }

  displayStream.getVideoTracks()[0].addEventListener("ended", () => stop()); // bouton "Arrêter le partage" de Chrome

  t0 = Date.now();
  videoRec.start(1000);
  audioRec?.start(1000);
  await chrome.runtime.sendMessage({ type: "recording-started", t0 });

  $("status").textContent = "● enregistrement"; $("status").className = "rec";
  $("stop").disabled = false;
  document.title = "● REC — Show Me Once";
  log("Enregistrement démarré. Va faire ta tâche dans tes onglets.");
}

function stopRecorder(rec) {
  return new Promise((resolve) => {
    if (!rec || rec.state === "inactive") return resolve();
    rec.onstop = resolve;
    rec.stop();
  });
}

let stopping = false;
async function stop() {
  if (stopping || !videoRec) return;
  stopping = true;
  $("stop").disabled = true;
  await Promise.all([stopRecorder(videoRec), stopRecorder(audioRec)]);
  const duration = (Date.now() - t0) / 1000;
  for (const s of [displayStream, micStream]) s?.getTracks().forEach((t) => t.stop());
  audioCtx?.close();
  await chrome.runtime.sendMessage({ type: "recording-stopped" });
  document.title = "Show Me Once — Recorder";
  $("status").textContent = "envoi…"; $("status").className = "";
  log(`Arrêt. Durée ${duration.toFixed(1)} s, ${events.length} événements.`);
  await upload(duration);
  stopping = false;
  $("start").disabled = false;
}

function dataUrlToBlob(dataUrl) {
  const [head, b64] = dataUrl.split(",");
  const mime = head.match(/:(.*?);/)[1];
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], { type: mime });
}

function buildBundle(duration) {
  const video = new Blob(videoChunks, { type: "video/webm" });
  const audio = audioChunks.length ? new Blob(audioChunks, { type: "audio/webm" }) : null;
  const screenshots = [];
  const cleanEvents = events.map((e) => {
    const { screenshot, ...rest } = e;
    if (screenshot) { rest.screenshot_file = `${e.id}.jpg`; screenshots.push({ name: rest.screenshot_file, blob: dataUrlToBlob(screenshot) }); }
    return rest;
  });
  const meta = {
    started_at: new Date(t0).toISOString(), duration_s: duration,
    user_agent: navigator.userAgent, screen: { w: screen.width, h: screen.height, dpr: devicePixelRatio },
    extension_version: chrome.runtime.getManifest().version,
    title: document.getElementById("taskTitle").value.trim() || undefined,
    goal: document.getElementById("taskGoal").value.trim() || undefined,
  };
  return { video, audio, screenshots, cleanEvents, meta };
}

async function upload(duration) {
  const b = buildBundle(duration);
  const { backendUrl, apiKey } = await getSettings();
  const fd = new FormData();
  fd.append("video", b.video, "video.webm");
  if (b.audio) fd.append("audio", b.audio, "audio.webm");
  fd.append("events", JSON.stringify(b.cleanEvents));
  fd.append("meta", JSON.stringify(b.meta));
  for (const s of b.screenshots) fd.append("screenshots", s.blob, s.name);

  try {
    const res = await fetch(`${backendUrl}/recordings`, { method: "POST", body: fd, headers: apiKey ? { "X-ShowMeOnce-Key": apiKey } : {} });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    const data = await res.json();
    $("status").textContent = "envoyé ✓"; $("status").className = "ok";
    const viewer = `${backendUrl}/viewer/${data.id}`;
    $("result").innerHTML = `Enregistrement <b>${data.id}</b> reçu. Transcription Gladia en cours…<br><a href="${viewer}" target="_blank">Ouvrir la timeline →</a>`;
    log("Upload OK : " + data.id);
  } catch (e) {
    $("status").textContent = "échec de l'envoi — téléchargement local"; $("status").className = "rec";
    log("Upload impossible (" + e.message + "). Je télécharge le bundle en local.");
    downloadLocally(b);
  }
}

function download(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
}

function downloadLocally(b) {
  const stamp = new Date(t0).toISOString().replace(/[:.]/g, "-");
  download(b.video, `show-me-once-${stamp}-video.webm`);
  if (b.audio) download(b.audio, `show-me-once-${stamp}-audio.webm`);
  // events avec captures inline pour pouvoir ré-importer plus tard
  download(new Blob([JSON.stringify({ meta: b.meta, events })], { type: "application/json" }), `show-me-once-${stamp}-events.json`);
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.target !== "recorder") return;
  if (msg.type === "event") {
    events.push(msg.event);
    $("counter").textContent = `${events.length} événement${events.length > 1 ? "s" : ""}`;
    const e = msg.event;
    const what = e.kind === "click" ? `clic « ${e.target?.text || e.target?.aria_label || e.target?.selector} »` :
                 e.kind === "input" ? `saisie ${e.target?.label || e.target?.name || ""} = ${e.value}` : (e.url || "");
    log(`${e.t.toFixed(1)}s ${e.kind} ${what}`);
  }
  if (msg.type === "stop") stop();
});

$("start").onclick = start;
$("stop").onclick = stop;
window.addEventListener("beforeunload", (e) => { if (videoRec?.state === "recording") { e.preventDefault(); e.returnValue = ""; } });
