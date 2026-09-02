/** IdentityOS browser bridge: configuration, privacy, cache, and API broker. */

const DEFAULTS = {
  runtimeUrl: 'http://localhost:8000',
  activeIdentityId: null,
  userId: 'extension-user',
  enabled: true,
  partitionByPlatform: true,
  apiKey: '',
  siteAccess: {
    chatgpt: true,
    claude: true,
    gemini: true,
    github: false,
    reddit: false,
    youtube: false,
    grok: true,
  },
};

const CACHE_KEY = 'identity_context_cache';
const QUEUE_KEY = 'pending_evaluations';

async function getConfig() {
  const stored = await chrome.storage.local.get(Object.keys(DEFAULTS));
  return {
    ...DEFAULTS,
    ...stored,
    siteAccess: { ...DEFAULTS.siteAccess, ...(stored.siteAccess || {}) },
  };
}

async function setConfig(updates) {
  const safe = { ...updates };
  if (safe.runtimeUrl) safe.runtimeUrl = safe.runtimeUrl.replace(/\/$/, '');
  await chrome.storage.local.set(safe);
}

function headers(config) {
  const result = { 'Content-Type': 'application/json' };
  if (config.apiKey) result['X-API-Key'] = config.apiKey;
  return result;
}

function platformUser(config, platform) {
  return config.partitionByPlatform
    ? `${config.userId}:platform:${platform}`
    : config.userId;
}

function allowed(config, platform) {
  return config.enabled && config.siteAccess[platform] === true;
}

function cacheId(config, platform) {
  return `${config.activeIdentityId || ''}:${platform}`;
}

async function readCache() {
  const result = await chrome.storage.local.get(CACHE_KEY);
  return result[CACHE_KEY] || {};
}

async function cacheContext(config, platform, context) {
  const cache = await readCache();
  cache[cacheId(config, platform)] = {
    context,
    cachedAt: new Date().toISOString(),
  };
  await chrome.storage.local.set({ [CACHE_KEY]: cache });
}

async function fetchContext(config, platform, message) {
  if (!config.activeIdentityId || !allowed(config, platform)) return null;
  try {
    const response = await fetch(`${config.runtimeUrl}/context`, {
      method: 'POST',
      headers: headers(config),
      body: JSON.stringify({
        message,
        identity_id: config.activeIdentityId,
        user_id: platformUser(config, platform),
        session_id: `${platform}:${config.activeIdentityId}`,
      }),
    });
    if (!response.ok) throw new Error(`context API returned ${response.status}`);
    const data = await response.json();
    const result = {
      context: data.augmented_context || '',
      identityName: data.identity_name || config.activeIdentityId,
      offline: false,
    };
    await cacheContext(config, platform, result);
    return result;
  } catch (error) {
    const cache = await readCache();
    const cached = cache[cacheId(config, platform)];
    return cached ? { ...cached.context, offline: true, cachedAt: cached.cachedAt } : null;
  }
}

async function queueEvaluation(entry) {
  const result = await chrome.storage.local.get(QUEUE_KEY);
  const queue = result[QUEUE_KEY] || [];
  queue.push(entry);
  await chrome.storage.local.set({ [QUEUE_KEY]: queue.slice(-200) });
}

async function submitEvaluation(config, platform, message, response) {
  if (!config.activeIdentityId || !allowed(config, platform)) return false;
  const payload = {
    message,
    response,
    identity_id: config.activeIdentityId,
    user_id: platformUser(config, platform),
    session_id: `${platform}:${config.activeIdentityId}`,
  };
  try {
    const result = await fetch(`${config.runtimeUrl}/evaluate`, {
      method: 'POST',
      headers: headers(config),
      body: JSON.stringify(payload),
    });
    if (!result.ok) throw new Error(`evaluate API returned ${result.status}`);
    return true;
  } catch (error) {
    await queueEvaluation({ ...payload, platform, queuedAt: new Date().toISOString() });
    return false;
  }
}

async function flushEvaluations(config) {
  const result = await chrome.storage.local.get(QUEUE_KEY);
  const queue = result[QUEUE_KEY] || [];
  const retained = [];
  for (const entry of queue) {
    if (!allowed(config, entry.platform)) {
      retained.push(entry);
      continue;
    }
    try {
      const response = await fetch(`${config.runtimeUrl}/evaluate`, {
        method: 'POST',
        headers: headers(config),
        body: JSON.stringify(entry),
      });
      if (!response.ok) retained.push(entry);
    } catch (error) {
      retained.push(entry);
    }
  }
  await chrome.storage.local.set({ [QUEUE_KEY]: retained });
  return { flushed: queue.length - retained.length, pending: retained.length };
}

async function fetchIdentities(config) {
  try {
    const response = await fetch(`${config.runtimeUrl}/identity`, {
      headers: headers(config),
    });
    if (!response.ok) return [];
    const data = await response.json();
    return (data.identities || []).map((identity) =>
      typeof identity === 'string' ? { id: identity, name: identity } : identity
    );
  } catch (error) {
    return [];
  }
}

async function createIdentity(config, name) {
  const identityId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const response = await fetch(`${config.runtimeUrl}/identity`, {
    method: 'POST',
    headers: headers(config),
    body: JSON.stringify({ identity_id: identityId, name }),
  });
  if (!response.ok) throw new Error(`identity API returned ${response.status}`);
  return response.json();
}

async function checkRuntimeHealth(config) {
  try {
    const response = await fetch(`${config.runtimeUrl}/health`, {
      signal: AbortSignal.timeout(2000),
    });
    return response.ok;
  } catch (error) {
    return false;
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    const config = await getConfig();
    switch (message.type) {
      case 'GET_CONTEXT': {
        const data = await fetchContext(
          config,
          message.platform || 'unknown',
          message.message || '',
        );
        sendResponse({ success: Boolean(data), data });
        break;
      }
      case 'SUBMIT_EVAL': {
        const saved = await submitEvaluation(
          config,
          message.platform || 'unknown',
          message.message || '',
          message.response || '',
        );
        sendResponse({ success: saved, queued: !saved });
        break;
      }
      case 'GET_CONFIG': {
        const runtimeOnline = await checkRuntimeHealth(config);
        sendResponse({ ...config, runtimeOnline });
        break;
      }
      case 'SET_CONFIG':
        await setConfig(message.updates || {});
        sendResponse({ success: true });
        break;
      case 'LIST_IDENTITIES':
        sendResponse({ identities: await fetchIdentities(config) });
        break;
      case 'CREATE_IDENTITY':
        try {
          sendResponse({ success: true, identity: await createIdentity(config, message.name || '') });
        } catch (error) {
          sendResponse({ success: false, reason: error.message });
        }
        break;
      case 'FLUSH_QUEUE':
        sendResponse(await flushEvaluations(config));
        break;
      default:
        sendResponse({ success: false, reason: 'Unknown message type' });
    }
  })();
  return true;
});

console.log('[IdentityOS] Browser bridge initialized.');
