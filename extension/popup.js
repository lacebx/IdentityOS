(function () {
  'use strict';

  let config = {};
  let identities = [];
  const statusDot = document.getElementById('status-dot');
  const runtimeUrlInput = document.getElementById('runtime-url');
  const apiKeyInput = document.getElementById('api-key');
  const identityList = document.getElementById('identity-list');
  const btnDisconnect = document.getElementById('btn-disconnect');

  function send(message) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(message, (response) => resolve(response || {}));
    });
  }

  async function save(updates) {
    await send({ type: 'SET_CONFIG', updates });
    config = { ...config, ...updates };
  }

  async function initialize() {
    config = await send({ type: 'GET_CONFIG' });
    runtimeUrlInput.value = config.runtimeUrl || 'http://localhost:8000';
    apiKeyInput.value = config.apiKey || '';
    statusDot.classList.toggle('online', Boolean(config.runtimeOnline));
    document.getElementById('partition-platform').checked = config.partitionByPlatform !== false;
    for (const checkbox of document.querySelectorAll('[data-site]')) {
      checkbox.checked = config.siteAccess?.[checkbox.dataset.site] === true;
    }
    await send({ type: 'FLUSH_QUEUE' });
    await loadIdentities();
  }

  async function loadIdentities() {
    identityList.innerHTML = '<li id="no-identities"><span class="spinner"></span> Loading...</li>';
    const result = await send({ type: 'LIST_IDENTITIES' });
    identities = result.identities || [];
    renderIdentities();
  }

  function renderIdentities() {
    if (!identities.length) {
      identityList.innerHTML = '<li id="no-identities">No identities found. Create one.</li>';
      btnDisconnect.style.display = 'none';
      return;
    }
    identityList.innerHTML = '';
    for (const identity of identities) {
      const li = document.createElement('li');
      li.dataset.id = identity.id;
      if (identity.id === config.activeIdentityId) li.classList.add('active');
      li.innerHTML = `<span class="identity-icon">⬡</span><div class="identity-info"><div class="identity-name"></div></div>`;
      li.querySelector('.identity-name').textContent = identity.name || identity.id;
      if (identity.id === config.activeIdentityId) {
        const badge = document.createElement('span');
        badge.className = 'active-badge';
        badge.textContent = 'active';
        li.appendChild(badge);
      }
      li.addEventListener('click', () => selectIdentity(identity.id));
      identityList.appendChild(li);
    }
    btnDisconnect.style.display = config.activeIdentityId ? 'block' : 'none';
  }

  async function notifyTabs(identityId) {
    const tabs = await chrome.tabs.query({ active: true });
    for (const tab of tabs) {
      if (tab.id) chrome.tabs.sendMessage(tab.id, { type: 'IDENTITY_CHANGED', identityId });
    }
  }

  async function selectIdentity(identityId) {
    await save({ activeIdentityId: identityId });
    await notifyTabs(identityId);
    renderIdentities();
  }

  document.getElementById('btn-save-url').addEventListener('click', async () => {
    await save({
      runtimeUrl: runtimeUrlInput.value.trim().replace(/\/$/, ''),
      apiKey: apiKeyInput.value.trim(),
    });
    await initialize();
  });

  document.getElementById('btn-new-identity').addEventListener('click', async () => {
    const name = prompt('Identity name:');
    if (!name?.trim()) return;
    const result = await send({ type: 'CREATE_IDENTITY', name: name.trim() });
    if (!result.success) {
      alert(`Failed to create identity: ${result.reason || 'unknown error'}`);
      return;
    }
    await loadIdentities();
    await selectIdentity(result.identity.id);
  });

  document.getElementById('btn-open-dashboard').addEventListener('click', () => {
    chrome.tabs.create({ url: `${config.runtimeUrl}/playground` });
  });

  btnDisconnect.addEventListener('click', async () => {
    await save({ activeIdentityId: null });
    await notifyTabs(null);
    renderIdentities();
  });

  document.getElementById('partition-platform').addEventListener('change', async (event) => {
    await save({ partitionByPlatform: event.target.checked });
  });

  for (const checkbox of document.querySelectorAll('[data-site]')) {
    checkbox.addEventListener('change', async () => {
      const siteAccess = { ...(config.siteAccess || {}) };
      siteAccess[checkbox.dataset.site] = checkbox.checked;
      await save({ siteAccess });
    });
  }

  initialize();
})();
