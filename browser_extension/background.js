/**
 * IdentityOS Live Browser Bridge - Background Script
 *
 * Responsibilities:
 *  1. Maintain a native-messaging connection to the bridge host (server role).
 *  2. Push the REAL Firefox tab state to the host via `sync_tabs` whenever
 *     tabs are opened/closed/updated/activated so the comet sees the truth.
 *  3. Execute host-initiated commands (navigate/click/fill/snapshot/...)
 *     against real tabs using the browser.tabs API and content scripts,
 *     returning real results to the host.
 */

const IDENTITYOS_APP = "identityos_live_bridge";

let port = null;
let isConnected = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_DELAY_MS = 2000;

// ── Tab sync ────────────────────────────────────────────────────────────

async function readRealTabs() {
  // Query all tabs across windows with titles/urls so the host mirrors the
  // user's actual browser state.
  const windows = await browser.windows.getAll({ populate: true });
  const tabs = [];
  let activeTabId = null;
  for (const win of windows) {
    for (const tab of win.tabs) {
      if (tab.active && win.focused) activeTabId = tab.id;
      tabs.push({
        id: tab.id,
        windowId: win.id,
        active: tab.active && win.focused ? true : tab.active,
        title: tab.title || "",
        url: tab.url || "about:blank",
        favIconUrl: tab.favIconUrl || "",
      });
    }
  }
  return { tabs, active_tab_id: activeTabId };
}

let syncTimer = null;

function scheduleSync() {
  if (isConnected && port) {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(syncTabs, 250);
  }
}

async function syncTabs() {
  if (!isConnected || !port) return;
  try {
    const { tabs, active_tab_id } = await readRealTabs();
    port.postMessage({ type: "sync_tabs", tabs, active_tab_id, timestamp: Date.now() });
  } catch (e) {
    console.error("[IdentityOS] Failed to sync tabs:", e);
  }
}

function registerTabListeners() {
  browser.tabs.onCreated.addListener(scheduleSync);
  browser.tabs.onRemoved.addListener(scheduleSync);
  browser.tabs.onUpdated.addListener(scheduleSync);
  browser.tabs.onActivated.addListener(scheduleSync);
  browser.windows.onFocusChanged.addListener(scheduleSync);
  // Immediate sync on connect as well (below).
}

// ── Native messaging connection ─────────────────────────────────────────

function connect() {
  try {
    port = browser.runtime.connectNative(IDENTITYOS_APP);
    isConnected = true;
    reconnectAttempts = 0;
    console.log("[IdentityOS] Connected to native host");

    port.onMessage.addListener(handleNativeMessage);
    port.onDisconnect.addListener(handleDisconnect);
    // Push the current real tab state over the fresh connection.
    syncTabs();
  } catch (e) {
    console.error("[IdentityOS] Failed to connect to native host:", e);
    scheduleReconnect();
  }
}

function handleDisconnect() {
  isConnected = false;
  console.warn("[IdentityOS] Native host disconnected");
  scheduleReconnect();
}

function scheduleReconnect() {
  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return;
  reconnectAttempts++;
  setTimeout(connect, RECONNECT_DELAY_MS);
}

// ── Host-initiated command dispatch ─────────────────────────────────────

async function executeCommand(message) {
  const type = message.type;
  const tabId = message.tabId;

  switch (type) {
    case "list_tabs": {
      const { tabs } = await readRealTabs();
      return { tabs };
    }
    case "active_tab": {
      const active = await browser.tabs.query({ active: true, currentWindow: true });
      if (active.length === 0) return { tab: null };
      return { tab: {
        id: active[0].id,
        window_id: active[0].windowId,
        active: true,
        title: active[0].title || "",
        url: active[0].url || "about:blank",
      }};
    }
    case "activate_tab": {
      if (tabId == null) throw new Error("tabId is required for activate_tab");
      const tab = await browser.tabs.update(tabId, { active: true });
      await browser.windows.update(tab.windowId, { focused: true });
      return { ok: true, tab: {
        id: tab.id,
        title: tab.title || "",
        url: tab.url || "",
      }};
    }
    case "create_tab": {
      const tab = await browser.tabs.create({ url: message.url || "about:blank" });
      return { ok: true, tab: {
        id: tab.id,
        title: tab.title || "",
        url: tab.url || "about:blank",
      }};
    }
    case "close_tab": {
      if (tabId == null) throw new Error("tabId is required for close_tab");
      await browser.tabs.remove(tabId);
      return { ok: true };
    }
    case "navigate": {
      if (tabId == null) throw new Error("tabId is required for navigate");
      const url = message.url;
      if (!url) throw new Error("url is required for navigate");
      const tab = await browser.tabs.update(tabId, { url });
      const waitUntil = message.waitUntil || "domcontentloaded";
      const status = await waitForTabLoad(tabId, waitUntil);
      return { ok: true, url, tab_id: tabId, status };
    }
    case "snapshot": {
      const maxChars = message.maxChars || 4000;
      let snapshot = null;
      try {
        snapshot = await browser.tabs.sendMessage(tabId, {
          method: "snapshot", maxChars,
        });
      } catch (e) {
        // Content script may not be injected on restricted pages.
        const tab = await browser.tabs.get(tabId);
        snapshot = {
          success: true,
          result: {
            url: tab.url || "",
            title: tab.title || "",
            text: "[Content script unavailable on this page]",
            interactive: [],
            timestamp: Date.now(),
          },
        };
      }
      return snapshot && snapshot.result
        ? snapshot.result
        : { url: "", title: "", text: "", interactive: [], timestamp: Date.now() };
    }
    case "click":
    case "fill":
    case "type":
    case "press": {
      return await runContentCommand(tabId, type, message);
    }
    default:
      throw new Error(`Unknown command type: ${type}`);
  }
}

function waitForTabLoad(tabId, waitUntil) {
  return new Promise((resolve) => {
    const started = Date.now();
    const check = async () => {
      try {
        const tab = await browser.tabs.get(tabId);
        const done =
          tab.status === "complete" ||
          (waitUntil === "domcontentloaded" && tab.status !== "loading");
        if (done) {
          resolve(tab.status);
          return;
        }
      } catch (_e) {
        /* tab closed mid-wait */
      }
      if (Date.now() - started > 30000) {
        resolve("timeout");
        return;
      }
      setTimeout(check, 200);
    };
    check();
  });
}

async function runContentCommand(tabId, type, message) {
  if (tabId == null) throw new Error("tabId is required");
  return browser.tabs.sendMessage(tabId, {
    method: type,
    selector: message.selector,
    value: message.value,
    text: message.text,
    key: message.key,
  });
}

function handleNativeMessage(message) {
  // Messages from the host are commands to be executed against the real
  // browser. Reply with the same id and a `command_result` type.
  (async () => {
    try {
      const result = await executeCommand(message);
      port.postMessage({ id: message.id, type: "command_result", result });
    } catch (err) {
      port.postMessage({ id: message.id, type: "command_result", error: String(err && err.message || err) });
    }
  })();
}

// ── Popup / content script request handling ─────────────────────────────

const IdentityOSBridge = {
  async status() {
    // Real status: report from authoritative host connection.
    return { connected: isConnected };
  },
  async listTabs() {
    const { tabs } = await readRealTabs();
    return tabs;
  },
  async getActiveTab() {
    const active = await browser.tabs.query({ active: true, currentWindow: true });
    return active.length ? active[0] : null;
  },
  async activateTab(tabId) {
    await browser.tabs.update(tabId, { active: true });
    return { ok: true };
  },
  async createTab(url) {
    return browser.tabs.create({ url });
  },
  async closeTab(tabId) {
    await browser.tabs.remove(tabId);
    return { ok: true };
  },
  async snapshot(tabId, maxChars = 4000) {
    const res = await browser.tabs.sendMessage(tabId, { method: "snapshot", maxChars });
    return res && res.result ? res.result : {};
  },
  async navigate(tabId, url) {
    await browser.tabs.update(tabId, { url });
    return { ok: true };
  },
};

// Connect, register tab watchers, and expose to the popup/content scripts.
connect();
registerTabListeners();

if (typeof browser !== "undefined") {
  browser.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message && message.target === "identityos_bridge") {
      IdentityOSBridge[message.method](...(message.args || []))
        .then((result) => sendResponse({ success: true, result }))
        .catch((err) => sendResponse({ success: false, error: String(err && err.message || err) }));
      return true; // async response
    }
  });
}

if (typeof module !== "undefined") {
  module.exports = { IdentityOSBridge };
}