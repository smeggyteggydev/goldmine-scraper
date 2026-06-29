if (!window.__callforgeEightX8BridgeInstalled) {
  window.__callforgeEightX8BridgeInstalled = true;

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.source !== "callforge-bridge") return;

    if (message.action === "ping") {
      report("connected");
    }

    if (message.action === "dial") {
      dialNumber(message.phone);
    }

    if (message.action === "end") {
      const clicked = clickByWords(["end", "hang up", "hangup", "decline"]);
      report(clicked ? "end clicked" : "could not find end button");
    }
  });
}

async function dialNumber(phone) {
  if (!phone) return;
  report("preparing 8x8 dialer");

  clickByWords(["new call", "make a call", "dial pad", "dialpad", "keypad", "call"]);

  const input = await waitForPhoneInput();
  if (input) {
    setValue(input, phone);
    await wait(300);
    if (clickByWords(["call", "dial", "place call", "start call"])) {
      report("number pasted and call clicked");
      return;
    }
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", bubbles: true }));
    report("number pasted, pressed Enter");
    return;
  }

  await navigator.clipboard?.writeText(phone).catch(() => {});
  clickByWords(["dial pad", "dialpad", "keypad", "new call", "make a call", "call"]);
  report("could not find number input, copied number");
}

async function waitForPhoneInput() {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const input = findPhoneInput();
    if (input) return input;
    await wait(450);
    if (attempt === 3 || attempt === 7) {
      clickByWords(["new call", "make a call", "dial pad", "dialpad", "keypad"]);
    }
  }
  return null;
}

function findPhoneInput() {
  const candidates = [
    'input[type="tel"]',
    'input[inputmode="tel"]',
    'input[inputmode="numeric"]',
    'input[autocomplete="tel"]',
    'input[placeholder*="number" i]',
    'input[aria-label*="number" i]',
    'input[placeholder*="phone" i]',
    'input[aria-label*="phone" i]',
    'input[placeholder*="search" i]',
    'input[aria-label*="search" i]',
    'input[placeholder*="dial" i]',
    'input[aria-label*="dial" i]',
    'input[data-testid*="dial" i]',
    'input[data-test*="dial" i]',
    '[role="textbox"]',
    'input[placeholder*="name" i]',
    'input[type="text"]',
    'textarea',
    '[contenteditable="true"]',
  ];

  for (const selector of candidates) {
    const element = queryAllDeep(selector).find(isUsable);
    if (element) return element;
  }

  return null;
}

function setValue(element, value) {
  element.focus();

  if (element.isContentEditable) {
    element.textContent = value;
  } else {
    const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter) {
      setter.call(element, value);
    } else {
      element.value = value;
    }
  }

  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

function clickByWords(words) {
  const controls = queryAllDeep('button, [role="button"], a, [aria-label], [data-testid], [data-test]').filter(isUsable);
  const target = controls.find((element) => {
    const text = `${element.innerText || ""} ${element.getAttribute("aria-label") || ""} ${element.title || ""} ${element.getAttribute("data-testid") || ""} ${element.getAttribute("data-test") || ""}`.toLowerCase();
    return words.some((word) => text.includes(word));
  });

  if (!target) return false;
  target.click();
  return true;
}

function queryAllDeep(selector, root = document) {
  const found = [];
  const visit = (node) => {
    try {
      found.push(...node.querySelectorAll(selector));
      node.querySelectorAll("*").forEach((child) => {
        if (child.shadowRoot) visit(child.shadowRoot);
      });
    } catch {
      // Cross-origin frames or transient roots can fail; skip them.
    }
  };

  visit(root);

  document.querySelectorAll("iframe").forEach((frame) => {
    try {
      if (frame.contentDocument) visit(frame.contentDocument);
    } catch {
      // Ignore cross-origin frames.
    }
  });

  return [...new Set(found)];
}

function isUsable(element) {
  const box = element.getBoundingClientRect();
  const style = getComputedStyle(element);
  return box.width > 0 && box.height > 0 && style.visibility !== "hidden" && style.display !== "none";
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function report(status) {
  chrome.runtime.sendMessage({ source: "callforge-8x8-page", status }).catch(() => {});
}
