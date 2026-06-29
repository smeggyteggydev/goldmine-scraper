window.postMessage({ source: "callforge-bridge", status: "connected" }, window.location.origin);

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  if (event.origin !== window.location.origin) return;
  const data = event.data || {};
  if (data.source !== "callforge") return;
  chrome.runtime.sendMessage(data);
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.source !== "callforge-bridge") return;
  window.postMessage(message, window.location.origin);
});
