/**
 * IdentityOS Live Browser Bridge - Popup Script
 */

const LOG_LINES = [];

function log(msg, type = "info") {
  const timestamp = new Date().toLocaleTimeString();
  const prefix = type === "error" ? "❌ " : type === "warn" ? "⚠️ " : "✅ ";
  const line = `[${timestamp}] ${prefix}${msg}`;
  LOG_LINES.push(line);
  if (LOG_LINES.length > 100) LOG_LINES.shift();
  renderLog();
}

function renderLog() {
  const logEl = document.getElementById("log");
  if (logEl) {
    logEl.textContent = LOG_LINES.join("\n");
    logEl.scrollTop = logEl.scrollHeight;
  }
}

function setStatus(connected) {
  const statusEl = document.getElementById("status");
  const connectBtn = document.getElementById("btnConnect");
  const disconnectBtn = document.getElementById("btnDisconnect");
  
  if (connected) {
    statusEl.textContent = "Connected to IdentityOS";
    statusEl.className = "status connected";
    connectBtn.classList.add("hidden");
    disconnectBtn.classList.remove("hidden");
    enableButtons(true);
  } else {
    statusEl.textContent = "Disconnected";
    statusEl.className = "status disconnected";
    connectBtn.classList.remove("hidden");
    disconnectBtn.classList.add("hidden");
    enableButtons(false);
  }
}

function enableButtons(enabled) {
  const buttons = [
    "btnListTabs", "btnActiveTab", "btnSnapshot", "btnNavigate"
  ];
  for (const id of buttons) {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = !enabled;
  }
}

async function connect() {
  log("Connecting to IdentityOS native host...");
  try {
    // Send connect message to background
    const response = await browser.runtime.sendMessage({
      target: "identityos_bridge",
      method: "status"
    });
    
    if (response.success) {
      log("Connected to IdentityOS");
      setStatus(true);
    } else {
      log("Connection failed: " + (response.error || "Unknown error"), "error");
      setStatus(false);
    }
  } catch (err) {
    log("Connection error: " + err.message, "error");
    setStatus(false);
  }
}

function disconnect() {
  log("Disconnecting...");
  // Native messaging doesn't support explicit disconnect from extension side
  // The connection is managed by the background script
  setStatus(false);
  log("Disconnected");
}

async function listTabs() {
  log("Listing tabs...");
  try {
    const response = await browser.runtime.sendMessage({
      target: "identityos_bridge",
      method: "listTabs"
    });
    
    if (response.success) {
      log(`Found ${response.result.length} tabs`);
      renderTabs(response.result);
    } else {
      log("Failed to list tabs: " + (response.error || "Unknown error"), "error");
    }
  } catch (err) {
    log("Error listing tabs: " + err.message, "error");
  }
}

async function getActiveTab() {
  log("Getting active tab...");
  try {
    const response = await browser.runtime.sendMessage({
      target: "identityos_bridge",
      method: "getActiveTab"
    });
    
    if (response.success) {
      log("Active tab: " + response.result.title);
      renderTabs([response.result], true);
    } else {
      log("Failed to get active tab: " + (response.error || "Unknown error"), "error");
    }
  } catch (err) {
    log("Error getting active tab: " + err.message, "error");
  }
}

async function activateTab(tabId) {
  log(`Activating tab ${tabId}...`);
  try {
    const response = await browser.runtime.sendMessage({
      target: "identityos_bridge",
      method: "activateTab",
      args: [tabId]
    });
    
    if (response.success) {
      log("Tab activated");
      listTabs(); // Refresh list
    } else {
      log("Failed to activate tab: " + (response.error || "Unknown error"), "error");
    }
  } catch (err) {
    log("Error activating tab: " + err.message, "error");
  }
}

function renderTabs(tabs, highlightActive = false) {
  const container = document.getElementById("tabsList");
  container.innerHTML = "";
  
  for (const tab of tabs) {
    const div = document.createElement("div");
    div.className = "tab-item" + (tab.active && highlightActive ? " active" : "");
    div.innerHTML = `
      <div class="title">${escapeHtml(tab.title || "(no title)")}</div>
      <div class="url">${escapeHtml(tab.url)}</div>
    `;
    div.onclick = () => activateTab(tab.id);
    container.appendChild(div);
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

async function takeSnapshot() {
  log("Taking page snapshot...");
  try {
    const response = await browser.runtime.sendMessage({
      target: "identityos_bridge",
      method: "snapshot",
      args: [4000]
    });
    
    if (response.success) {
      log("Snapshot taken: " + response.result.text.length + " chars");
      console.log("Snapshot:", response.result);
    } else {
      log("Snapshot failed: " + (response.error || "Unknown error"), "error");
    }
  } catch (err) {
    log("Snapshot error: " + err.message, "error");
  }
}

async function promptNavigate() {
  const url = prompt("Enter URL to navigate to:");
  if (!url) return;
  
  log(`Navigating to ${url}...`);
  try {
    const response = await browser.runtime.sendMessage({
      target: "identityos_bridge",
      method: "navigate",
      args: [url, "domcontentloaded"]
    });
    
    if (response.success) {
      log("Navigation successful");
    } else {
      log("Navigation failed: " + (response.error || "Unknown error"), "error");
    }
  } catch (err) {
    log("Navigation error: " + err.message, "error");
  }
}

// Initialize popup
document.addEventListener("DOMContentLoaded", () => {
  // Check initial connection status
  browser.runtime.sendMessage({
    target: "identityos_bridge",
    method: "status"
  }).then(response => {
    if (response.success) {
      setStatus(true);
      log("Already connected to IdentityOS");
    } else {
      setStatus(false);
    }
  }).catch(() => {
    setStatus(false);
  });
});