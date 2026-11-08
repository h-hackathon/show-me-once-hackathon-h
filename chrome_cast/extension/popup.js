const $ = (id) => document.getElementById(id);

(async () => {
  const state = await chrome.runtime.sendMessage({ type: "get-state" });
  $("idle").hidden = !!state?.recording;
  $("rec").hidden = !state?.recording;
  const s = await chrome.storage.local.get(["backendUrl", "apiKey"]);
  $("backendUrl").value = s.backendUrl || "http://localhost:8000";
  $("apiKey").value = s.apiKey || "";
})();

$("open").onclick = async () => { await chrome.runtime.sendMessage({ type: "open-recorder" }); window.close(); };
$("stop").onclick = async () => { await chrome.runtime.sendMessage({ type: "stop-recording" }); window.close(); };
$("save").onclick = async () => {
  await chrome.storage.local.set({ backendUrl: $("backendUrl").value.trim(), apiKey: $("apiKey").value.trim() });
  $("save").textContent = "Enregistré ✓";
};
