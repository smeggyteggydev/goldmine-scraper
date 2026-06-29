const EIGHTX8_URL = "https://work.8x8.com/calls/all";
let appTabId = null;
let eightx8TabId = null;

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.source === "callforge-8x8-page") {
    report(message.status || "8x8 page action sent");
    return;
  }

  if (message?.source !== "callforge") return;
  appTabId = sender.tab?.id || appTabId;

  if (message.action === "dial") {
    open8x8AndSend({ action: "dial", phone: message.phone, business: message.business });
    return;
  }

  if (message.action === "end") {
    open8x8AndSend({ action: "end" });
  }
});

async function open8x8AndSend(command) {
  try {
    report("opening 8x8");
    const tab = await getOrCreate8x8Tab();
    eightx8TabId = tab.id;
    await chrome.tabs.update(tab.id, { active: true });

    const send = () => chrome.tabs.sendMessage(tab.id, { source: "callforge-bridge", ...command });

    await ensureContentScript(tab.id);

    for (let attempt = 1; attempt <= 4; attempt += 1) {
      try {
        await send();
        report(command.action === "dial" ? "sent number to 8x8 tab" : "sent end command to 8x8 tab");
        return;
      } catch {
        await wait(700);
      }
    }

    report("could not reach 8x8 tab script");
  } catch (error) {
    report(`failed: ${error.message}`);
  }
}

async function getOrCreate8x8Tab() {
  if (eightx8TabId) {
    try {
      const existing = await chrome.tabs.get(eightx8TabId);
      if (existing?.url?.startsWith("https://work.8x8.com/")) return existing;
    } catch {
      eightx8TabId = null;
    }
  }

  const tabs = await chrome.tabs.query({ url: "https://work.8x8.com/*" });
  if (tabs.length) {
    eightx8TabId = tabs[0].id;
    return tabs[0];
  }

  const tab = await chrome.tabs.create({ url: EIGHTX8_URL, active: true });
  eightx8TabId = tab.id;
  await waitForTabComplete(tab.id);
  return chrome.tabs.get(tab.id);
}

async function ensureContentScript(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { source: "callforge-bridge", action: "ping" });
  } catch {
    await chrome.scripting.executeScript({ target: { tabId }, files: ["eightx8-page.js"] });
    await wait(500);
  }
}

function waitForTabComplete(tabId) {
  return new Promise((resolve) => {
    const timeout = setTimeout(done, 12000);

    function done() {
      clearTimeout(timeout);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }

    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === "complete") done();
    }

    chrome.tabs.onUpdated.addListener(listener);
  });
}

function report(status) {
  if (!appTabId) return;
  chrome.tabs.sendMessage(appTabId, { source: "callforge-bridge", status }).catch(() => {});
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
