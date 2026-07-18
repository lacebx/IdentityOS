/**
 * Identity Runtime Bridge - Background Service Worker
 *
 * Handles communication between content scripts and the Identity Runtime API.
 * Acts as the central message broker for the extension.
 */

const RUNTIME_URL = 'http://localhost:8000';
const STORAGE_KEY_IDENTITY = 'active_identity_id';
const STORAGE_KEY_USER = 'user_id';
const STORAGE_KEY_ENABLED = 'bridge_enabled';

// Default config
const DEFAULT_IDENTITY_ID = 'startup-mentor-v1';
const DEFAULT_USER_ID = 'local-user';


// --- Storage helpers ---

async function getConfig() {
  const result = await chrome.storage.local.get([
    STORAGE_KEY_IDENTITY,
    STORAGE_KEY_USER,
    STORAGE_KEY_ENABLED
  ]);
  return {
    identityId: result[STORAGE_KEY_IDENTITY] || DEFAULT_IDENTITY_ID,
    userId: result[STORAGE_KEY_USER] || DEFAULT_USER_ID,
    enabled: result[STORAGE_KEY_ENABLED] !== false  // default: enabled
  };
}

async function setConfig(updates) {
  await chrome.storage.local.set(updates);
}


// --- Runtime API calls ---

async function fetchContext(message, identityId, userId) {
  try {
    const response = await fetch(`${RUNTIME_URL}/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        identity_id: identityId,
        user_id: userId
      })
    });

    if (!response.ok) {
      console.warn('[IdentityRuntime] Context API error:', response.status);
      return null;
    }

    return await response.json();
  } catch (err) {
    console.warn('[IdentityRuntime] Runtime not reachable. Running without identity layer.', err.message);
    return null;
  }
}

async function submitEvaluation(message, response, identityId, userId) {
  try {
    await fetch(`${RUNTIME_URL}/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        response,
        identity_id: identityId,
        user_id: userId
      })
    });
  } catch (err) {
    console.warn('[IdentityRuntime] Eval submission failed:', err.message);
  }
}

async function fetchIdentities() {
  try {
    const response = await fetch(`${RUNTIME_URL}/identity`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.identities || [];
  } catch (err) {
    return [];
  }
}

async function checkRuntimeHealth() {
  try {
    const response = await fetch(`${RUNTIME_URL}/health`, { signal: AbortSignal.timeout(2000) });
    return response.ok;
  } catch {
    return false;
  }
}


// --- Message handler ---

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Handle async responses
  (async () => {
    const config = await getConfig();

    switch (message.type) {

      case 'GET_CONTEXT': {
        if (!config.enabled) {
          sendResponse({ success: false, reason: 'Bridge disabled' });
          return;
        }
        const result = await fetchContext(
          message.message,
          config.identityId,
          config.userId
        );
        sendResponse({ success: !!result, data: result });
        break;
      }

      case 'SUBMIT_EVAL': {
        if (!config.enabled) return;
        await submitEvaluation(
          message.message,
          message.response,
          config.identityId,
          config.userId
        );
        sendResponse({ success: true });
        break;
      }

      case 'GET_CONFIG': {
        const health = await checkRuntimeHealth();
        sendResponse({ ...config, runtimeOnline: health });
        break;
      }

      case 'SET_CONFIG': {
        await setConfig(message.updates);
        sendResponse({ success: true });
        break;
      }

      case 'LIST_IDENTITIES': {
        const identities = await fetchIdentities();
        sendResponse({ identities });
        break;
      }

      default:
        sendResponse({ success: false, reason: 'Unknown message type' });
    }
  })();

  return true;  // Keep channel open for async response
});

console.log('[IdentityRuntime] Background service worker initialized.');
