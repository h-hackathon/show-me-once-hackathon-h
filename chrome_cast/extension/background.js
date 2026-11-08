// Show Me Once — service worker.
// Rôle : orchestrer l'enregistrement, horodater les événements, prendre une capture d'écran
// à chaque clic, et tout transmettre à l'onglet "recorder" (qui garde les données en mémoire).

const RECORDER_URL = chrome.runtime.getURL("recorder.html");
const SCREENSHOT_MIN_INTERVAL_MS = 550; // Chrome limite captureVisibleTab à ~2 appels/s

let state = { recording: false, recorderTabId: null, t0: null };
let lastShotAt = 0;
let seq = 0;

// Le service worker peut être endormi par Chrome : on persiste l'état minimal.
const ready = chrome.storage.session.get("state").then((r) => { if (r.state) state = r.state; });
const save = () => chrome.storage.session.set({ state });

// Les onglets ouverts avant l'installation (ou un rechargement) de l'extension n'ont pas le
// content script : on l'injecte au démarrage de chaque enregistrement.
async function injectIntoOpenTabs(tabs) {
  await Promise.all(tabs
    .filter((t) => t.id !== state.recorderTabId && /^https?:/.test(t.url || ""))
    .map((t) => chrome.scripting.executeScript({ target: { tabId: t.id, allFrames: true }, files: ["content.js"] }).catch(() => {})));
}

async function toRecorder(msg) {
  if (!state.recorderTabId) return;
  try { await chrome.runtime.sendMessage({ target: "recorder", ...msg }); } catch (_) {}
}

async function pushEvent(event, { screenshot = false, windowId = null } = {}) {
  await ready;
  if (!state.recording) return;
  event.id = `e${Date.now()}_${seq++}`;
  event.t = (event.ts - state.t0) / 1000; // secondes depuis le début de la vidéo
  if (screenshot) {
    const now = Date.now();
    if (now - lastShotAt >= SCREENSHOT_MIN_INTERVAL_MS) {
      lastShotAt = now;
      try {
        event.screenshot = await chrome.tabs.captureVisibleTab(windowId, { format: "jpeg", quality: 70 });
      } catch (e) { event.screenshot_error = String(e.message || e); }
    }
  }
  await toRecorder({ type: "event", event });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    await ready;
    switch (msg.type) {
      case "dom-event": {
        if (!state.recording || sender.tab?.id === state.recorderTabId) break;
        const ev = { ...msg.event, tab_id: sender.tab?.id, frame_id: sender.frameId };
        await pushEvent(ev, { screenshot: ev.kind === "click", windowId: sender.tab?.windowId });
        break;
      }
      case "open-recorder": {
        const existing = state.recorderTabId && (await chrome.tabs.get(state.recorderTabId).catch(() => null));
        if (existing) await chrome.tabs.update(existing.id, { active: true });
        else {
          const tab = await chrome.tabs.create({ url: RECORDER_URL, pinned: true, active: true });
          state.recorderTabId = tab.id;
          await save();
        }
        sendResponse({ ok: true });
        return;
      }
      case "recording-started": {
        state = { recording: true, recorderTabId: sender.tab.id, t0: msg.t0 };
        seq = 0;
        await save();
        chrome.action.setBadgeText({ text: "REC" });
        chrome.action.setBadgeBackgroundColor({ color: "#d93025" });
        // Événement initial : l'onglet actif au moment du démarrage
        const tabs = await chrome.tabs.query({});
        await injectIntoOpenTabs(tabs);
        // l'onglet de travail = le plus récemment utilisé hors recorder
        const active = tabs.filter((t) => t.id !== state.recorderTabId).sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0))[0];
        await pushEvent({
          kind: "start", ts: msg.t0,
          open_tabs: tabs.filter((t) => t.id !== state.recorderTabId).map((t) => ({ id: t.id, url: t.url, title: t.title })),
          url: active?.url, title: active?.title, tab_id: active?.id,
        });
        break;
      }
      case "stop-recording": {
        await toRecorder({ type: "stop" });
        sendResponse({ ok: true });
        return;
      }
      case "recording-stopped": {
        state.recording = false;
        await save();
        chrome.action.setBadgeText({ text: "" });
        break;
      }
      case "get-state": {
        sendResponse(state);
        return;
      }
    }
    sendResponse({ ok: true });
  })();
  return true; // réponse asynchrone
});

// Changement d'onglet (ex : Stripe → suivi de commandes → Shopify)
chrome.tabs.onActivated.addListener(async ({ tabId, windowId }) => {
  await ready;
  if (!state.recording || tabId === state.recorderTabId) return;
  const tab = await chrome.tabs.get(tabId).catch(() => null);
  // petit délai pour que l'onglet soit peint avant la capture
  setTimeout(() => pushEvent({ kind: "tab_switch", ts: Date.now(), tab_id: tabId, url: tab?.url, title: tab?.title }, { screenshot: true, windowId }), 300);
});

// Navigation (rechargement complet ou SPA via pushState) dans n'importe quel onglet
chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
  await ready;
  if (!state.recording || tabId === state.recorderTabId) return;
  if (info.url) pushEvent({ kind: "navigation", ts: Date.now(), tab_id: tabId, url: info.url, title: tab.title });
  if (info.status === "complete" && tab.active) {
    pushEvent({ kind: "page_loaded", ts: Date.now(), tab_id: tabId, url: tab.url, title: tab.title }, { screenshot: true, windowId: tab.windowId });
  }
});

chrome.tabs.onCreated.addListener(async (tab) => {
  await ready;
  if (!state.recording) return;
  pushEvent({ kind: "tab_opened", ts: Date.now(), tab_id: tab.id, url: tab.pendingUrl || tab.url, opener_tab_id: tab.openerTabId });
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  await ready;
  if (tabId === state.recorderTabId) {
    state = { recording: false, recorderTabId: null, t0: null };
    await save();
    chrome.action.setBadgeText({ text: "" });
    return;
  }
  if (state.recording) pushEvent({ kind: "tab_closed", ts: Date.now(), tab_id: tabId });
});
