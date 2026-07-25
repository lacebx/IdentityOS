(function () {
  'use strict';

  const DEFAULT_RUNTIME_URL = 'http://localhost:8000';

  let runtimeUrl = DEFAULT_RUNTIME_URL;
  let activeIdentityId = null;
  let identities = [];

  const statusDot = document.getElementById('status-dot');
  const runtimeUrlInput = document.getElementById('runtime-url');
  const btnSaveUrl = document.getElementById('btn-save-url');
  const identityList = document.getElementById('identity-list');
  const btnNewIdentity = document.getElementById('btn-new-identity');
  const btnOpenDashboard = document.getElementById('btn-open-dashboard');
  const btnDisconnect = document.getElementById('btn-disconnect');

  async function init() {
    const config = await loadConfig();
    runtimeUrl = config.runtimeUrl || DEFAULT_RUNTIME_URL;
    activeIdentityId = config.activeIdentityId || config.identityId || null;
    runtimeUrlInput.value = runtimeUrl;
    await checkRuntimeHealth();
    await loadIdentities();
  }

  function loadConfig() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_CONFIG' }, (resp) => {
        resolve(resp || {});
      });
    });
  }

  function saveConfig(updates) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'SET_CONFIG', updates }, (resp) => {
        resolve(resp);
      });
    });
  }

  async function checkRuntimeHealth() {
    try {
      const res = await fetch(`${runtimeUrl}/health`, { signal: AbortSignal.timeout(2000) });
      if (res.ok) {
        statusDot.classList.add('online');
        return true;
      }
    } catch (_) {}
    statusDot.classList.remove('online');
    return false;
  }

  async function loadIdentities() {
    identityList.innerHTML = '<li id="no-identities"><span class="spinner"></span> Loading...</li>';
    try {
      const res = await fetch(`${runtimeUrl}/identity`);
      const data = await res.json();
      identities = data.identities || [];
      renderIdentities();
    } catch (e) {
      identityList.innerHTML = '<li id="no-identities" style="color:#ff6688">Could not connect to runtime</li>';
    }
  }

  function renderIdentities() {
    if (identities.length === 0) {
      identityList.innerHTML = '<li id="no-identities">No identities found. Create one!</li>';
      btnDisconnect.style.display = 'none';
      return;
    }

    identityList.innerHTML = '';
    for (const identity of identities) {
      const li = document.createElement('li');
      li.dataset.id = identity.id;
      if (identity.id === activeIdentityId) {
        li.classList.add('active');
      }

      const icon = document.createElement('span');
      icon.className = 'identity-icon';
      icon.textContent = '⬡';

      const info = document.createElement('div');
      info.className = 'identity-info';

      const name = document.createElement('div');
      name.className = 'identity-name';
      name.textContent = identity.name || identity.id;

      info.appendChild(name);
      li.appendChild(icon);
      li.appendChild(info);

      if (identity.id === activeIdentityId) {
        const badge = document.createElement('span');
        badge.className = 'active-badge';
        badge.textContent = 'active';
        li.appendChild(badge);
        btnDisconnect.style.display = 'block';
      }

      li.addEventListener('click', () => selectIdentity(identity.id));
      identityList.appendChild(li);
    }
  }

  async function selectIdentity(identityId) {
    activeIdentityId = identityId;
    await saveConfig({ activeIdentityId: identityId });

    const tabs = await chrome.tabs.query({ active: true });
    for (const tab of tabs) {
      try {
        chrome.tabs.sendMessage(tab.id, { type: 'IDENTITY_CHANGED', identityId });
      } catch (_) {}
    }
    renderIdentities();
  }

  btnSaveUrl.addEventListener('click', async () => {
    const newUrl = runtimeUrlInput.value.trim().replace(/\/$/, '');
    if (!newUrl) return;
    runtimeUrl = newUrl;
    await saveConfig({ runtimeUrl });
    const healthy = await checkRuntimeHealth();
    if (healthy) await loadIdentities();
  });

  btnNewIdentity.addEventListener('click', () => {
    const name = prompt('Identity name (e.g., "Pluto"):');
    if (!name) return;
    createIdentity(name.trim());
  });

  async function createIdentity(name) {
    try {
      const id = name.toLowerCase().replace(/\s+/g, '-');
      await fetch(`${runtimeUrl}/identity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identity_id: id, name }),
      });
      await loadIdentities();
    } catch (e) {
      alert('Failed to create identity. Is the runtime running?');
    }
  }

  btnOpenDashboard.addEventListener('click', () => {
    chrome.tabs.create({ url: `${runtimeUrl}/docs` });
  });

  btnDisconnect.addEventListener('click', async () => {
    activeIdentityId = null;
    await saveConfig({ activeIdentityId: null });
    renderIdentities();
  });

  init();
})();
